#!/usr/bin/env python3
"""騎手・調教師の条件別の成績（公開するのは集計だけ）。
  python3 -m trends_v1.people --data <非公開 data_v2> --out docs/data/people_trends_v1.json
A/E＝実際の勝ち数÷オッズから作った期待の勝ち数。得意条件は『続くか』も測る：前半期間（〜2021年）と後半期間（2022年〜）で
『その条件のA/E − その人の全体のA/E』がそろうか（相関）。"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .parse import iter_races
from .stats import S, band, corr, race_probs

SPLIT_YEAR = 2022
MIN_PERSON = 300       # 公開する最小の出走数
MIN_COND = 60          # 条件別に載せる最小の出走数


def pop_group(pop):
    if pop is None:
        return None
    return "1〜3番人気" if pop <= 3 else ("4〜9番人気" if pop <= 9 else "10番人気以下")


def conds(race, r):
    out = [("面", race["surface"]), ("場", race["venue"]), ("人", pop_group(r["pop"])),
           ("距離", f'{race["surface"]}・{band(race["dist"])}')]
    return [(k, v) for k, v in out if v]


def build(data_dir: Path) -> dict:
    acc = defaultdict(S)                      # (kind, id, 種類, 値, 期間) -> S
    names, span = {}, {}
    for race, rows in iter_races(data_dir):
        if race["surface"] not in ("芝", "ダート") or not race["venue"]:
            continue
        probs = race_probs(rows)
        if probs is None:
            continue
        half = "h1" if race["year"] < SPLIT_YEAR else "h2"
        for r, p in zip(rows, probs):
            if p is None:
                continue
            for kind, pid, nm in (("jockey", r["jockey"], r["jockey_name"]), ("trainer", r["trainer"], r["trainer_name"])):
                if not pid:
                    continue
                names[(kind, pid)] = nm
                lo, hi = span.get((kind, pid), (race["year"], race["year"]))
                span[(kind, pid)] = (min(lo, race["year"]), max(hi, race["year"]))
                for per in ("all", half):
                    acc[(kind, pid, "全体", "全体", per)].add(p, r["finish"], r["odds"])
                    for k, v in conds(race, r):
                        acc[(kind, pid, k, v, per)].add(p, r["finish"], r["odds"])

    def ae(s):
        return s.win / s.exp if s and s.exp > 0 else None

    people = {"jockey": [], "trainer": []}
    pair_overall = {"jockey": [], "trainer": []}
    pair_cond = {"jockey": [], "trainer": []}
    ids = sorted({(k, i) for (k, i, *_rest) in acc})
    for kind, pid in ids:
        tot = acc[(kind, pid, "全体", "全体", "all")]
        h1, h2 = acc.get((kind, pid, "全体", "全体", "h1")), acc.get((kind, pid, "全体", "全体", "h2"))
        if h1 and h2 and h1.n >= 150 and h2.n >= 150:
            pair_overall[kind].append((ae(h1), ae(h2), min(h1.n, h2.n)))
        if tot.n < MIN_PERSON:
            continue
        people[kind].append((pid, tot, h1, h2))
    # 条件別（人ごとにまとめる）
    by_person = defaultdict(list)
    for (kind, pid, k, v, per), s in acc.items():
        if per == "all" and k != "全体":
            by_person[(kind, pid)].append((k, v, s))
    out = {"jockey": [], "trainer": []}
    for kind in ("jockey", "trainer"):
        for pid, tot, h1, h2 in people[kind]:
            o_all = ae(tot)
            cl = []
            for k, v, s in by_person[(kind, pid)]:
                if s.n < MIN_COND:
                    continue
                d = s.out()
                d.update({"k": k, "v": v})
                cl.append(d)
                a, c = acc.get((kind, pid, k, v, "h1")), acc.get((kind, pid, k, v, "h2"))
                if a and c and a.n >= 50 and c.n >= 50 and h1 and h2 and ae(h1) and ae(h2):
                    pair_cond[kind].append((ae(a) - ae(h1), ae(c) - ae(h2), min(a.n, c.n)))
            cl.sort(key=lambda d: (d["k"], -d["n"]))
            lo, hi = span[(kind, pid)]
            rec = {"id": pid, "name": names[(kind, pid)], "years": [lo, hi], "all": tot.out(), "conds": cl}
            out[kind].append(rec)
        out[kind].sort(key=lambda r: -r["all"]["n"])
    persistence = {}
    for kind in ("jockey", "trainer"):
        r1, n1 = corr(pair_overall[kind])
        r2, n2 = corr(pair_cond[kind])
        persistence[kind] = {"overall": {"corr": r1, "pairs": n1}, "condition": {"corr": r2, "pairs": n2}}
    jst = timezone(timedelta(hours=9))
    return {"version": 1, "generated": datetime.now(jst).strftime("%Y-%m-%d %H:%M"), "split_year": SPLIT_YEAR,
            "min_person": MIN_PERSON, "min_cond": MIN_COND, "persistence": persistence, "jockey": out["jockey"], "trainer": out["trainer"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = build(Path(a.data))
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("jockeys", len(d["jockey"]), "trainers", len(d["trainer"]), "persistence", json.dumps(d["persistence"], ensure_ascii=False), "bytes", Path(a.out).stat().st_size)
