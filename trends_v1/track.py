#!/usr/bin/env python3
"""競馬場ごとの傾向（枠・脚質・馬場・開催の進み・年ごとの変化）。公開するのは集計だけ。
  python3 -m trends_v1.track --data <非公開 data_v2> --out docs/data/track_trends_v1.json
指標：A/E＝実際の勝ち数÷オッズから作った期待の勝ち数（人気どおりなら1.00。人気の影響を除いた『傾向』）。
安定性：前半期間（〜2021年）と後半期間（2022年〜）でA/Eがそろうか（相関）。"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .parse import iter_races
from .stats import BANDS, S, band, corr, draw_of, race_probs, style_of

SPLIT_YEAR = 2022
MIN_N = 300
GOINGS = ["稍重", "重", "不良"]


def build(data_dir: Path) -> dict:
    acc = defaultdict(S)                 # (venue, surface, band, dim, group, period) -> S
    win_times = defaultdict(list)        # (venue, surface, dist, inout, klass, going) -> [勝ちタイム]
    races_n = defaultdict(int)
    wins_by_style = defaultdict(lambda: defaultdict(int))
    n_races = n_rows = 0
    years = set()
    for race, rows in iter_races(data_dir):
        if race["surface"] not in ("芝", "ダート") or not race["venue"]:
            continue
        n_races += 1
        years.add(race["year"])
        v, sf, b = race["venue"], race["surface"], band(race["dist"])
        races_n[(v, sf)] += 1
        w = next((r for r in rows if r["finish"] == 1 and r["time"]), None)
        if w:
            win_times[(v, sf, race["dist"], race["inout"], race["klass"], race["going"])].append(w["time"])
        wr = next((r for r in rows if r["finish"] == 1), None)
        wst = style_of(wr, len(rows)) if wr else None
        if wst:                                   # そのレースの勝ち馬の脚質（1レース1回数える）
            for vv in (v, "全場"):
                for bb in (b, "全距離"):
                    wins_by_style[(vv, sf, bb)][wst] += 1
        probs = race_probs(rows)
        if probs is None:
            continue
        half = "h1" if race["year"] < SPLIT_YEAR else "h2"
        nrun = len(rows)
        prog = "序盤(1〜3日目)" if race["nichi"] <= 3 else ("中盤(4〜6日目)" if race["nichi"] <= 6 else "終盤(7日目〜)")
        for r, p in zip(rows, probs):
            if p is None:
                continue
            n_rows += 1
            dg, st = draw_of(r["frame"]), style_of(r, nrun)
            front = st in ("逃げ", "先行") if st else None
            for vv in (v, "全場"):
                for bb in (b, "全距離"):
                    for per in ("all", half):
                        if dg:
                            acc[(vv, sf, bb, "draw", dg, per)].add(p, r["finish"], r["odds"])
                        if st:
                            acc[(vv, sf, bb, "style", st, per)].add(p, r["finish"], r["odds"])
            if dg:
                for vv in (v, "全場"):
                    acc[(vv, sf, "全距離", "progress_" + dg, prog, "all")].add(p, r["finish"], r["odds"])
            if front is not None:
                acc[(v, sf, "全距離", "year_front", str(race["year"]), "all")].add(p, r["finish"], r["odds"]) if front else None
            if dg == "内枠(1〜2枠)":
                acc[(v, sf, "全距離", "year_inner", str(race["year"]), "all")].add(p, r["finish"], r["odds"])

    def get(*k):
        s = acc.get(k)
        return s.out() if s and s.n else None

    def winners(v, sf, bb):
        c = wins_by_style.get((v, sf, bb))
        t = sum(c.values()) if c else 0
        return {"n": t, **{g: round(c[g] / t, 3) for g in ("逃げ", "先行", "差し", "追込")}} if t else None

    def persistence(v, sf, bb, dim, groups):
        """競馬場ごとの『全場平均との差』が前半・後半でそろうか（全場共通の脚質の差は除く）"""
        pairs = []
        for g in groups:
            a, c = acc.get((v, sf, bb, dim, g, "h1")), acc.get((v, sf, bb, dim, g, "h2"))
            a0, c0 = acc.get(("全場", sf, bb, dim, g, "h1")), acc.get(("全場", sf, bb, dim, g, "h2"))
            if a and c and a.n >= 100 and c.n >= 100 and a.exp > 0 and c.exp > 0 and a0 and c0:
                pairs.append((a.win / a.exp - a0.win / a0.exp, c.win / c.exp - c0.win / c0.exp, min(a.n, c.n)))
        return pairs

    tracks = {}
    persist_pairs = {"draw": [], "style": []}
    base = {}
    for sf in ("芝", "ダート"):
        base[sf] = {"draw": {g: get("全場", sf, "全距離", "draw", g, "all") for g in ("内枠(1〜2枠)", "中枠(3〜6枠)", "外枠(7〜8枠)")},
                    "style": {g: get("全場", sf, "全距離", "style", g, "all") for g in ("逃げ", "先行", "差し", "追込")},
                    "winners": winners("全場", sf, "全距離"),
                    "progress": {g: {p: get("全場", sf, "全距離", "progress_" + g, p, "all") for p in ("序盤(1〜3日目)", "中盤(4〜6日目)", "終盤(7日目〜)")}
                                 for g in ("内枠(1〜2枠)", "外枠(7〜8枠)")}}
    for (v, sf), nr in sorted(races_n.items()):
        if nr < 150:
            continue
        item = {"races": nr, "bands": {}}
        for bb in ["全距離"] + BANDS:
            draw = {g: get(v, sf, bb, "draw", g, "all") for g in ("内枠(1〜2枠)", "中枠(3〜6枠)", "外枠(7〜8枠)")}
            style = {g: get(v, sf, bb, "style", g, "all") for g in ("逃げ", "先行", "差し", "追込")}
            if not any(x and x["n"] >= MIN_N for x in draw.values()):
                continue
            item["bands"][bb] = {"draw": draw, "style": style, "winners": winners(v, sf, bb)}
            if bb != "全距離":
                for dim, groups in (("draw", list(draw)), ("style", list(style))):
                    persist_pairs[dim] += persistence(v, sf, bb, dim, groups)
        # 馬場：同じ競馬場・芝ダ・距離・コース・クラスの『良』の勝ちタイムと比べた、勝ちタイムの差（％）
        going = {}
        for g in GOINGS:
            diffs, cnt = [], 0
            for (vv, ss, dist, io, kl, gg), ts in win_times.items():
                if vv != v or ss != sf or gg != g or len(ts) < 3:
                    continue
                bt = win_times.get((vv, ss, dist, io, kl, "良"))
                if not bt or len(bt) < 5:
                    continue
                m = sum(ts) / len(ts)
                bm = sum(bt) / len(bt)
                diffs.append(((m / bm - 1) * 100, len(ts)))
                cnt += len(ts)
            if cnt >= 30:
                going[g] = {"races": cnt, "time_diff_pct": round(sum(d * w for d, w in diffs) / sum(w for _, w in diffs), 2)}
        item["going"] = going
        item["progress"] = {g: {p: get(v, sf, "全距離", "progress_" + g, p, "all") for p in ("序盤(1〜3日目)", "中盤(4〜6日目)", "終盤(7日目〜)")}
                            for g in ("内枠(1〜2枠)", "外枠(7〜8枠)")}
        item["years"] = {str(y): {"front": get(v, sf, "全距離", "year_front", str(y), "all"),
                                  "inner": get(v, sf, "全距離", "year_inner", str(y), "all")} for y in sorted(years)}
        tracks[f"{v}|{sf}"] = item
    pers = {}
    for dim, pr in persist_pairs.items():
        r, npair = corr(pr)
        pers[dim] = {"corr": r, "pairs": npair}
    jst = timezone(timedelta(hours=9))
    return {"version": 1, "generated": datetime.now(jst).strftime("%Y-%m-%d %H:%M"), "races": n_races, "starts": n_rows,
            "years": [min(years), max(years)], "split_year": SPLIT_YEAR, "min_n": MIN_N,
            "persistence": pers, "base": base, "tracks": tracks}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = build(Path(a.data))
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("tracks", len(out["tracks"]), "races", out["races"], "persistence", out["persistence"], "bytes", Path(a.out).stat().st_size)
