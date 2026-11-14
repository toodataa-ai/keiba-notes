#!/usr/bin/env python3
"""騎手のレーダーチャート【相対評価】（研究のみ・公開するのは集計だけ）。
  python3 -m trends_v1.jockey_radar_rel --data <非公開 data_v2> --out docs/data/jockey_radar_rel_v1.json
絶対評価（jockey_radar.py）と同じ7つの軸を、『人気（オッズ）から見て期待される水準』に対してどれだけ上か、で測る。
  勝率 → 単勝回収率 …… 勝率×単勝オッズの平均（1.00＝100円買って平均100円戻る。人気に見合った強さなら約0.8）
  連対率 → 連対率の期待比 …… 実際の2着内の数 ÷ オッズから見て期待される数
  複勝率 → 複勝回収率 …… 複勝率×複勝オッズの平均
  着順・先行力・末脚 → 期待との差 …… 実際の値 − 同じ人気（そのレースでの単勝オッズ由来の勝つ確率が同じくらい）の馬の平均
  上級戦 → オープン・重賞での複勝率の期待比
期待＝そのレースの単勝オッズ由来の勝つ確率（(1/オッズ)÷そのレースの合計）を40の幅に分け、2018年以降の全出走の平均。
得点は絶対評価と同じ作り：軸ごとに、騎手の値（走数が少ない分は平均に寄せる）の下位2%〜最高を0〜100に直す。
注意：人気の高い馬に乗る騎手は、人気が過剰になりやすい（市場の偏り）ため、相対評価でも『続く度』は絶対評価より低い。"""
from __future__ import annotations

import argparse
import bisect
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .parse import parse_race
from .stats import corr

SPLIT_YEAR = 2022
MIN_PERSON = 300
MIN_YEAR = 100
NB = 40
AXES = [
    ("win", "単勝回収率", "勝率×単勝オッズの平均（100円ずつ買い続けたときの戻り。人気に見合う強さなら0.8前後）。"),
    ("p2", "連対率の期待比", "2着以内の実際の数 ÷ オッズから見て期待される数（1.00＝人気どおり）。"),
    ("p3", "複勝回収率", "複勝率×複勝オッズの平均（100円ずつ複勝を買い続けたときの戻り）。"),
    ("rank", "着順（人気比）", "平均着順の点（1着＝100、最下位＝0）が、同じ人気の馬の平均より何点上か。"),
    ("front", "先行力（人気比）", "最初のコーナーでの位置の前め度が、同じ人気の馬の平均より何点前か。"),
    ("kick", "末脚（人気比）", "上がり3Fの速さの順位の点が、同じ人気の馬の平均より何点上か。"),
    ("top", "上級戦（人気比）", "オープン・重賞での複勝率の期待比（1.00＝人気どおり）。"),
]
KIND = {"win": "mean", "p2": "ratio", "p3": "mean", "rank": "diff", "front": "diff", "kick": "diff", "top": "ratio"}
SHR = {"win": 1500, "p2": 250, "p3": 600, "rank": 150, "front": 100, "kick": 100, "top": 80}
AX = [a for a, *_ in AXES]


def place_pay(res):
    """複勝の払戻（馬番 -> 倍率）"""
    out, on = {}, False
    for t in res["tables"]:
        if not t or not t[0] or "払戻金" not in t[0]:
            continue
        for r in t[1:]:
            if len(r) >= 4:
                on = r[0] == "複勝"
                if not on:
                    continue
                key, pay = r[1], r[2]
            elif on and len(r) == 3:
                key, pay = r[0], r[1]
            else:
                continue
            try:
                out[int(key)] = int(pay.replace(",", "").replace("円", "")) / 100
            except ValueError:
                pass
    return out


def load(data_dir: Path):
    runs = []                       # 1出走＝1行
    names, span = {}, {}
    for p in sorted((Path(data_dir) / "race_pages").glob("*.jsonl")):
        with p.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                out = parse_race(rec)
                if not out:
                    continue
                race, rows = out
                if race["surface"] not in ("芝", "ダート") or not race["venue"]:
                    continue
                n = len(rows)
                inv = [1 / r["odds"] if r["odds"] else None for r in rows]
                tot = sum(x for x in inv if x)
                if not tot or n < 5:
                    continue
                pp = place_pay(rec["pages"]["result"])
                l3s = sorted(r["last3"] for r in rows if r["last3"])
                for r, iv in zip(rows, inv):
                    jid = r["jockey"]
                    if not jid or iv is None or r["finish"] is None:
                        continue
                    names[jid] = r["jockey_name"]
                    fin = r["finish"]
                    fr = 100 * (1 - (r["pass"][0] - 1) / (n - 1)) if r["pass"] else None
                    kk = None
                    if r["last3"] and len(l3s) >= 5:
                        rank = sum(1 for x in l3s if x < r["last3"]) + 1
                        kk = 100 * (1 - (rank - 1) / (len(l3s) - 1))
                    runs.append((jid, race["year"], iv / tot, fin,
                                 r["odds"] if fin == 1 else 0.0,
                                 pp.get(r["no"], 0.0) if fin <= 3 else 0.0,
                                 100 * (1 - (fin - 1) / (n - 1)), fr, kk, race["klass"] == "OP・重賞"))
                    lo, hi = span.get(jid, (race["year"],) * 2)
                    span[jid] = (min(lo, race["year"]), max(hi, race["year"]))
    return runs, names, span


def build(data_dir: Path) -> dict:
    runs, names, span = load(data_dir)
    ps = sorted(r[2] for r in runs)
    cuts = [ps[int(len(ps) * i / NB)] for i in range(1, NB)]
    # 期待：同じ『勝つ確率の幅』の全出走の平均
    S = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0.0, 0, 0.0])
    for jid, y, p, fin, wr, pr, rk, fr, kk, op in runs:
        s = S[bisect.bisect(cuts, p)]
        s[0] += 1; s[1] += fin <= 2; s[2] += rk
        if fr is not None: s[4] += 1; s[3] += fr
        if kk is not None: s[6] += 1; s[5] += kk
    # 上級戦の複勝の期待は別に集計
    T = defaultdict(lambda: [0, 0])
    for jid, y, p, fin, wr, pr, rk, fr, kk, op in runs:
        if op:
            t = T[bisect.bisect(cuts, p)]; t[0] += 1; t[1] += fin <= 3
    E = {b: {"p2": s[1] / s[0], "rank": s[2] / s[0], "front": (s[3] / s[4]) if s[4] else None,
             "kick": (s[5] / s[6]) if s[6] else None, "top": (T[b][1] / T[b][0]) if T[b][0] else None} for b, s in S.items()}

    class Acc:
        __slots__ = ("n", "v", "e", "c")
        def __init__(self):
            self.n = {a: 0 for a in AX}; self.v = {a: 0.0 for a in AX}; self.e = {a: 0.0 for a in AX}

    acc = defaultdict(Acc)
    for jid, y, p, fin, wr, pr, rk, fr, kk, op in runs:
        e = E[bisect.bisect(cuts, p)]
        half = "h1" if y < SPLIT_YEAR else "h2"
        for per in ("all", half, y):
            a = acc[(jid, per)]
            a.n["win"] += 1; a.v["win"] += wr
            a.n["p2"] += 1; a.v["p2"] += fin <= 2; a.e["p2"] += e["p2"]
            a.n["p3"] += 1; a.v["p3"] += pr
            a.n["rank"] += 1; a.v["rank"] += rk - e["rank"]
            if fr is not None and e["front"] is not None:
                a.n["front"] += 1; a.v["front"] += fr - e["front"]
            if kk is not None and e["kick"] is not None:
                a.n["kick"] += 1; a.v["kick"] += kk - e["kick"]
            if op and e["top"] is not None:
                a.n["top"] += 1; a.v["top"] += fin <= 3; a.e["top"] += e["top"]

    def vals(a):
        o = {}
        for ax in AX:
            if not a.n[ax]:
                o[ax] = None
            elif KIND[ax] == "ratio":
                o[ax] = a.v[ax] / a.e[ax] if a.e[ax] else None
            else:
                o[ax] = a.v[ax] / a.n[ax]
        return o

    def scored(people, per):
        raw = {j: vals(acc[(j, per)]) for j in people}
        cn = {j: dict(acc[(j, per)].n) for j in people}
        shr, score = {}, {}
        for ax in AX:
            xs = [(raw[j][ax], cn[j][ax]) for j in people if raw[j][ax] is not None]
            tot = sum(w for _, w in xs)
            mu = sum(v * w for v, w in xs) / tot if tot else 0
            for j in people:
                v, w = raw[j][ax], cn[j][ax]
                shr[(j, ax)] = None if v is None else mu + (v - mu) * w / (w + SHR[ax])
            ok = sorted((shr[(j, ax)], j) for j in people if shr[(j, ax)] is not None)
            vs = [v for v, _ in ok]
            lo, hi = vs[int(len(vs) * 0.02)], vs[-1]
            for v, j in ok:
                score[(j, ax)] = round(100 * min(1.0, max(0.0, (v - lo) / (hi - lo)))) if hi > lo else 50
        return raw, cn, score

    people = [j for (j, per), a in acc.items() if per == "all" and a.n["win"] >= MIN_PERSON]
    raw, cn, score = scored(people, "all")
    years = sorted({per for (_, per) in acc if isinstance(per, int)})
    by_year = {}
    for y in years:
        py = [j for j in people if acc[(j, y)].n["win"] >= MIN_YEAR]
        if len(py) < 20:
            continue
        ry, cy, sy = scored(py, y)
        by_year[str(y)] = [[j, acc[(j, y)].n["win"], [sy.get((j, ax)) for ax in AX],
                            [None if ry[j][ax] is None else round(ry[j][ax], 4) for ax in AX]]
                           for j in sorted(py, key=lambda j: -acc[(j, y)].n["win"])]
    persist = {}
    for ax in AX:
        pairs = []
        for j in people:
            a1, a2 = acc.get((j, "h1")), acc.get((j, "h2"))
            if not a1 or not a2 or a1.n[ax] < 100 or a2.n[ax] < 100:
                continue
            pairs.append((vals(a1)[ax], vals(a2)[ax], min(a1.n[ax], a2.n[ax])))
        r, m = corr(pairs)
        persist[ax] = {"corr": r, "pairs": m}
    out = []
    for j in sorted(people, key=lambda j: -acc[(j, "all")].n["win"]):
        lo, hi = span[j]
        out.append({"id": j, "name": names[j], "n": acc[(j, "all")].n["win"], "years": [lo, hi],
                    "raw": {ax: (None if raw[j][ax] is None else round(raw[j][ax], 4)) for ax in AX},
                    "count": cn[j], "score": {ax: score.get((j, ax)) for ax in AX}})
    jst = timezone(timedelta(hours=9))
    return {"version": 1, "generated": datetime.now(jst).strftime("%Y-%m-%d %H:%M"), "split_year": SPLIT_YEAR,
            "min_person": MIN_PERSON, "min_year": MIN_YEAR,
            "axes": [{"id": a, "label": l, "desc": d, "kind": KIND[a], "persist": persist[a]} for a, l, d in AXES],
            "jockeys": out, "by_year": by_year}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = build(Path(a.data))
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("jockeys", len(d["jockeys"]), "bytes", Path(a.out).stat().st_size)
    for ax in d["axes"]:
        print(ax["id"], ax["label"], ax["persist"])
