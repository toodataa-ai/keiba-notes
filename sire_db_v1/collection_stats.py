#!/usr/bin/env python3
"""集めたデータの量（件数）を、公開してよい集計だけで書き出す。サイトの「データ収集の状況」ページが読む。

入力：非公開リポジトリの data_v2（--data）。数えるだけで、馬名・1頭ずつの記録・レースの中身は出さない。
出力：docs/data/collection_status_v1.json（いまの件数）／docs/data/collection_history_v1.json（1日1点の推移、直近90日）。
Claudeの使用量は使わない（GitHub Actions の collection-status-v1.yml が6時間おきに実行）。
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = dt.timezone(dt.timedelta(hours=9))
HISTORY_DAYS = 90


def _lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]


def total_races_by_year(root=ROOT):
    """取得の目標（JRA公式の馬場ラベルにある全レース）を年ごとに数える。"""
    out = {}
    for f in glob.glob(os.path.join(root, "baba_models_v2", "going_labels", "jra_going_*.csv")):
        m = re.search(r"jra_going_(\d{4})\.csv$", f)
        if not m:
            continue
        with open(f, encoding="utf-8") as fh:
            out[int(m.group(1))] = max(0, sum(1 for _ in csv.reader(fh)) - 1)
    return out


def _leaves(o):
    if isinstance(o, dict):
        return sum(_leaves(v) for v in o.values())
    if isinstance(o, list):
        return sum(_leaves(v) for v in o)
    return 0 if o is None or o == "" else 1


def count_horses(data_dir):
    horses = rows = values = 0
    sires, dams, jockeys = set(), set(), set()
    first = last = None
    for f in sorted(glob.glob(os.path.join(data_dir, "horses_*.jsonl"))):
        with open(f, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    h = json.loads(ln)
                except ValueError:
                    continue
                horses += 1
                ped = h.get("ped") or {}
                if ped.get("sire"):
                    sires.add(ped["sire"])
                if ped.get("dam"):
                    dams.add(ped["dam"])
                for r in h.get("history") or []:
                    rows += 1
                    values += sum(1 for v in r.values() if v is not None and v != "")
                    if r.get("jockey_id"):
                        jockeys.add(r["jockey_id"])
                    d = r.get("date")
                    if d:
                        first = d if first is None or d < first else first
                        last = d if last is None or d > last else last
    return {"horses": horses, "run_rows": rows, "data_values": values, "sires": len(sires),
            "dams": len(dams), "jockeys": len(jockeys), "first_date": first, "last_date": last}


def count_race_pages(data_dir):
    pages = size = cells = chars = 0
    for f in glob.glob(os.path.join(data_dir, "race_pages", "*.jsonl")):
        size += os.path.getsize(f)
        with open(f, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except ValueError:
                    continue
                pages += 1
                for p in (rec.get("pages") or {}).values():
                    cells += _leaves(p.get("tables"))
                    chars += len(p.get("text") or "")
    return {"pages": pages, "bytes": size, "cells": cells, "chars": chars}


def build(data_dir, now=None, root=ROOT):
    now = now or dt.datetime.now(JST)
    totals = total_races_by_year(root)
    done_codes = _lines(os.path.join(data_dir, "races_done.txt"))
    done_by_year = {}
    for c in done_codes:
        if len(c) >= 2 and c[:2].isdigit():
            y = 2000 + int(c[:2])
            done_by_year[y] = done_by_year.get(y, 0) + 1
    races_total = sum(totals.values())
    h = count_horses(data_dir)
    rp = count_race_pages(data_dir)
    rp_done = len(_lines(os.path.join(data_dir, "race_pages_done.txt")))
    return {
        "schema": "collection_status_v1",
        "generated_at": now.isoformat(timespec="seconds"),
        "note": "件数だけを公開しています。馬名・1頭ずつの記録・レースの中身は非公開の保管場所に置いています。",
        "past_races": {"done": len(done_codes), "total": races_total,
                       "frac": round(len(done_codes) / races_total, 4) if races_total else 0.0},
        "by_year": [{"year": y, "done": done_by_year.get(y, 0), "total": totals[y]} for y in sorted(totals)],
        "horses": h["horses"], "run_rows": h["run_rows"], "data_values": h["data_values"],
        "sires": h["sires"], "dams": h["dams"], "jockeys": h["jockeys"],
        "first_date": h["first_date"], "last_date": h["last_date"],
        "race_pages": {"done": rp_done, "total": races_total,
                       "frac": round(rp_done / races_total, 4) if races_total else 0.0,
                       "bytes": rp["bytes"], "cells": rp["cells"], "chars": rp["chars"]},
    }


def update_history(history, snap):
    """1日1点（同じ日は上書き）。直近 HISTORY_DAYS 日だけ残す。"""
    day = snap["generated_at"][:10]
    point = {"date": day, "races_done": snap["past_races"]["done"], "horses": snap["horses"],
             "run_rows": snap["run_rows"], "data_values": snap["data_values"],
             "race_pages_done": snap["race_pages"]["done"]}
    pts = [p for p in history.get("points", []) if p.get("date") != day]
    pts.append(point)
    pts.sort(key=lambda p: p["date"])
    return {"schema": "collection_history_v1", "points": pts[-HISTORY_DAYS:]}


def growth(history, snap):
    """直近7日の増え方と、このペースでの残り日数の目安。2点以上・1日以上の間隔があるときだけ。"""
    pts = history.get("points", [])
    if len(pts) < 2:
        return None
    last = pts[-1]
    last_d = dt.date.fromisoformat(last["date"])
    base = next((p for p in pts if (last_d - dt.date.fromisoformat(p["date"])).days <= 7), pts[0])
    span = (last_d - dt.date.fromisoformat(base["date"])).days
    if span < 1:
        return None
    per_day = {k: round((last[k] - base[k]) / span) for k in ("races_done", "run_rows", "horses", "race_pages_done")}
    eta = None
    if per_day["races_done"] > 0:
        eta = max(0, round((snap["past_races"]["total"] - last["races_done"]) / per_day["races_done"]))
    eta_pages = None
    if per_day["race_pages_done"] > 0:
        eta_pages = max(0, round((snap["race_pages"]["total"] - last["race_pages_done"]) / per_day["race_pages_done"]))
    return {"days": span, "per_day": per_day, "eta_days_past_races": eta, "eta_days_race_pages": eta_pages}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"), required=not os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "data", "collection_status_v1.json"))
    ap.add_argument("--history", default=os.path.join(ROOT, "docs", "data", "collection_history_v1.json"))
    a = ap.parse_args(argv)
    snap = build(a.data)
    hist = {}
    if os.path.exists(a.history):
        with open(a.history, encoding="utf-8") as f:
            hist = json.load(f)
    hist = update_history(hist, snap)
    snap["growth"] = growth(hist, snap)
    for path, obj in ((a.out, snap), (a.history, hist)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
    print(json.dumps({k: snap[k] for k in ("past_races", "horses", "run_rows", "data_values", "growth")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
