#!/usr/bin/env python3
"""要素の検証（研究のみ）：出走1行の表を作る。入力は非公開リポジトリの data_v2（公開しない）。
出力はこの表（作業用・公開しない）。公開するのは screen.py が作る集計だけ。
  python3 -m factor_screen_v1.build_table --data <data_v2> --out <表.pkl>
使える要素は『発走前に分かること』だけ（当日の結果・位置取りは使わない）。前走などは、その馬の履歴のうち当日より前のものだけから作る。"""
from __future__ import annotations

import argparse
import bisect
import pickle
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from sire_db_v1.debut_common import load_horses, mb
from sire_db_v1.lineage import grp, lineage_map
from trends_v1.parse import iter_races
from trends_v1.stats import race_probs


def style_prev(passing, heads):
    """前走の脚質（最初のコーナーの位置÷頭数）"""
    if not passing or not heads:
        return None
    try:
        pos = int(str(passing).split("-")[0])
    except ValueError:
        return None
    if pos == 1:
        return "逃げ"
    rel = pos / heads
    return "先行" if rel <= 0.35 else ("差し" if rel <= 0.7 else "追込")


def finish_band(f):
    if f is None or not isinstance(f, int):
        return "中止・除外"
    return "1着" if f == 1 else ("2〜3着" if f <= 3 else ("4〜5着" if f <= 5 else ("6〜9着" if f <= 9 else "10着以下")))


def build(data_dir: Path) -> pd.DataFrame:
    hs = load_horses(data_dir)
    LM, _ = lineage_map(hs)
    hist = {}
    for hid, h in hs.items():
        rows = [r for r in (h.get("history") or []) if r.get("date")]
        rows.sort(key=lambda r: r["date"])
        hist[hid] = ([r["date"] for r in rows], rows, h)
    out = []
    for race, rows in iter_races(data_dir):
        if race["surface"] not in ("芝", "ダート") or not race["venue"]:
            continue
        probs = race_probs(rows)
        if probs is None:
            continue
        n = len(rows)
        d0 = date.fromisoformat(race["date"])
        for r, p in zip(rows, probs):
            if p is None or r["frame"] is None:
                continue
            rec = {
                "date": race["date"], "year": race["year"], "month": int(race["date"][5:7]), "code": race["code"],
                "venue": race["venue"], "surface": race["surface"], "dist": race["dist"], "inout": race["inout"] or "",
                "going": race["going"], "klass": race["klass"], "nichi": race["nichi"], "heads": n,
                "frame": r["frame"], "no": r["no"], "sex": r["sex"], "age": r["age"], "weight": r["weight"], "wdiff": r["wdiff"],
                "pop": r["pop"], "odds": r["odds"], "p": p, "finish": r["finish"],
                "jockey": r["jockey"], "trainer": r["trainer"], "horse": r["horse"],
                "jockey_name": r["jockey_name"], "trainer_name": r["trainer_name"],
                "fair": 1.0 / n,
            }
            h = hist.get(r["horse"])
            prev = None
            if h:
                dates, hrows, hd = h
                i = bisect.bisect_left(dates, race["date"])      # 当日より前の履歴だけ
                rec["starts"] = i
                prev = hrows[i - 1] if i > 0 else None
                rec["sire_line"] = grp(LM.get((hd.get("ped") or {}).get("sire")))
                rec["age_m"] = mb(hd["birth"], race["date"]) if hd.get("birth") else None
            else:
                rec["starts"] = None
            if prev:
                rec["prev_finish"] = finish_band(prev.get("finish"))
                pf, pn = prev.get("finish"), prev.get("ninki")
                rec["prev_vs_pop"] = None if not (isinstance(pf, int) and pn) else ("人気より好走" if pf < pn - 1 else ("人気より凡走" if pf > pn + 1 else "人気どおり"))
                rec["prev_style"] = style_prev(prev.get("passing"), prev.get("heads"))
                days = (d0 - date.fromisoformat(prev["date"])).days
                rec["interval"] = "連闘〜1週" if days <= 10 else ("2〜3週" if days <= 24 else ("4〜8週" if days <= 62 else ("9〜25週" if days <= 180 else "半年以上")))
                pd_, pdist = prev.get("surface"), prev.get("dist")
                rec["surf_change"] = None if not pd_ else ("同じ芝ダ" if (pd_ == "ダート") == (race["surface"] == "ダート") else "芝ダ替わり")
                rec["dist_change"] = None if not pdist else ("同距離" if abs(pdist - race["dist"]) <= 100 else ("延長" if race["dist"] > pdist else "短縮"))
                rec["jockey_change"] = None if not prev.get("jockey_id") or not r["jockey"] else ("同じ騎手" if str(prev["jockey_id"]) == str(r["jockey"]) else "乗り替わり")
            out.append(rec)
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    df = build(Path(a.data))
    df.to_pickle(a.out)
    print("rows", len(df), "races", df["code"].nunique(), "years", sorted(df["year"].unique()))
    print(df.isna().mean().round(3).to_string())


if __name__ == "__main__":
    main()
