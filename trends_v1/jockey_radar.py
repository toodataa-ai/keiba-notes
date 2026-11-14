#!/usr/bin/env python3
"""騎手のレーダーチャート（研究のみ・公開するのは集計だけ）。
  python3 -m trends_v1.jockey_radar --data <非公開 data_v2> --out docs/data/jockey_radar_v1.json
7つの軸（どれも『結果』から見た騎手の傾向。人気・馬の普段の走り方の影響をできるだけ除く）：
  勝ち切る力 …… 勝ち数 ÷ オッズから作った期待の勝ち数（A/E）
  人気以上の着順 …… 同じ勝つ確率（オッズ）の馬の普通の着順より、どれだけ前で入ったか（平均）
  穴馬の激走 …… 6番人気以下の馬が3着内に来た数 ÷ 同じ勝つ確率（オッズ）の馬が普通に来る数
  人気馬の堅実さ …… 1〜3番人気の馬が3着内に来た数 ÷ 普通に来る数
  先行力 …… その馬の普段の位置取り（最初のコーナーの順位÷頭数）より前に出した度合い
  末脚を引き出す力 …… その馬の普段の上がり3F（レース平均との差）より速く上げさせた度合い
  上級戦の強さ …… オープン・重賞で3着内に来た数 ÷ 普通に来る数
得点は、軸ごとに騎手の中での順位（0〜100）。走数が少ない軸は平均に寄せる（縮小）。
『続くか』は、前半（〜2021年）と後半（2022年〜）で、騎手の並びがそろうか（相関）。"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .parse import iter_races
from .stats import corr, race_probs

SPLIT_YEAR = 2022
MIN_PERSON = 300
AXES = [
    ("win", "勝ち切る力", "勝ち数を、人気（オッズ）どおりなら勝つはずの数で割った値（A/E）。"),
    ("rank", "人気以上の着順", "同じ勝つ確率（オッズ）の馬が普通に入る着順より、どれだけ前で入ったか（平均）。"),
    ("long", "穴馬の激走", "6番人気以下の馬を3着内に持ってきた回数 ÷ 同じ勝つ確率（オッズ）の馬が普通に来る回数。"),
    ("fav", "人気馬の堅実さ", "1〜3番人気の馬を3着内に持ってきた回数 ÷ 普通に来る回数。"),
    ("front", "先行力", "その馬の普段の位置取りより、前に出した度合い（最初のコーナーの順位 ÷ 頭数 で比べる）。"),
    ("kick", "末脚を引き出す力", "その馬の普段の上がり3F（そのレースの平均との差）より速く上げさせた度合い。位置取りを前にした分の遅れは差し引いてある。"),
    ("top", "上級戦の強さ", "オープン・重賞で3着内に持ってきた回数 ÷ 普通に来る回数。"),
]


def hb(n):
    return 0 if n <= 12 else (1 if n <= 15 else 2)


def load(data_dir: Path):
    races = []
    for race, rows in iter_races(data_dir):
        if race["surface"] not in ("芝", "ダート") or not race["venue"]:
            continue
        races.append((race["date"], race["code"], race, rows))
    races.sort(key=lambda t: (t[0], t[1]))
    return races


class A:
    __slots__ = ("n", "win", "exp", "rk", "rkn", "lt", "ltx", "ltn", "ft", "ftx", "ftn", "tt", "ttx", "ttn", "fr", "frn", "kk", "kkn", "kx")

    def __init__(self):
        for k in self.__slots__:
            setattr(self, k, 0.0)


def build(data_dir: Path) -> dict:
    races = load(data_dir)
    # 1回目：同じ勝つ確率（オッズ）の馬が3着内に来る普通の割合
    import bisect
    allp = []
    for _d, _c, race, rows in races:
        pr = race_probs(rows)
        if pr:
            allp.extend(x for x in pr if x is not None)
    allp.sort()
    edges = [allp[int(len(allp) * q / 40)] for q in range(1, 40)]       # オッズから作った勝つ確率の40分位。同じ確率の馬どうしで『普通の成績』を作る（人気の順位ではなくオッズの大きさで比べる）
    cnt = defaultdict(lambda: [0, 0, 0.0])
    for _d, _c, race, rows in races:
        n = len(rows)
        pr = race_probs(rows)
        if not pr:
            continue
        for r, pv in zip(rows, pr):
            if pv is not None and r["finish"] is not None:
                k = bisect.bisect_left(edges, pv)
                cnt[k][0] += 1
                cnt[k][1] += 1 if r["finish"] <= 3 else 0
                cnt[k][2] += (r["finish"] - 1) / (n - 1) if n > 1 else 0.0
    base = {k: v[1] / v[0] for k, v in cnt.items() if v[0] >= 30}
    basef = {k: v[2] / v[0] for k, v in cnt.items() if v[0] >= 30}      # 同じ勝つ確率（オッズ）の馬の平均の着順（0=1着、1=最下位）
    # 2回目：日付順に、その馬の『普段』を更新しながら騎手ごとに積み上げる
    acc = defaultdict(A)
    names, span = {}, {}
    G = [0.0, 0.0, 0]                                    # 位置取りの変化と上がりの変化の関係（全体の傾き）
    hs = {}                                              # 馬 -> [位置の合計, 回数, 上がりの差の合計, 回数]
    for date, _c, race, rows in races:
        n = len(rows)
        probs = race_probs(rows)
        half = "h1" if race["year"] < SPLIT_YEAR else "h2"
        l3s = sorted(r["last3"] for r in rows if r["last3"])
        med = l3s[len(l3s) // 2] if len(l3s) >= 5 else None
        for i, r in enumerate(rows):
            jid = r["jockey"]
            rel = r["pass"][0] / n if r["pass"] and n else None
            d3 = (r["last3"] - med) if (r["last3"] and med) else None
            h = hs.setdefault(r["horse"], [0.0, 0, 0.0, 0]) if r["horse"] else None
            if jid:
                names[jid] = r["jockey_name"]
                lo, hi = span.get(jid, (race["year"], race["year"]))
                span[jid] = (min(lo, race["year"]), max(hi, race["year"]))
                for per in ("all", half):
                    a = acc[(jid, per)]
                    a.n += 1
                    p = probs[i] if probs else None
                    if p is not None:
                        a.exp += p
                        a.win += 1 if r["finish"] == 1 else 0
                    pop, fin = r["pop"], r["finish"]
                    if pop and fin is not None and n > 1 and p is not None:
                        kb = bisect.bisect_left(edges, p) if p is not None else None
                        bf = basef.get(kb)
                        if bf is not None:
                            a.rk += bf - (fin - 1) / (n - 1)          # 同じ人気の馬の普通の着順より、どれだけ前か
                            a.rkn += 1
                        b = base.get(kb)
                        if b is not None:
                            t = 1 if fin <= 3 else 0
                            if pop >= 6:
                                a.lt += t; a.ltx += b; a.ltn += 1
                            if pop <= 3:
                                a.ft += t; a.ftx += b; a.ftn += 1
                            if race["klass"] == "OP・重賞":
                                a.tt += t; a.ttx += b; a.ttn += 1
                    if h and rel is not None and h[1] >= 2:
                        a.fr += h[0] / h[1] - rel          # 普段より前に出したら +（rel が小さいほど前）
                        a.frn += 1
                    if h and d3 is not None and h[3] >= 2 and rel is not None and h[1] >= 2:
                        y = h[2] / h[3] - d3               # 普段より上がりが速ければ +（秒の差）
                        x = h[0] / h[1] - rel              # 普段より前に出していれば +
                        a.kk += y
                        a.kx += x
                        a.kkn += 1
                        if per == "all":
                            G[0] += x * x; G[1] += x * y; G[2] += 1
            if h:                                            # この走を『普段』に足す（次の走から使う）
                if rel is not None:
                    h[0] += rel; h[1] += 1
                if d3 is not None:
                    h[2] += d3; h[3] += 1

    slope = None

    def vals(a):
        return {"win": (a.win / a.exp) if a.exp > 0 else None, "rank": (a.rk / a.rkn) if a.rkn else None,
                "long": (a.lt / a.ltx) if a.ltx > 0 else None, "fav": (a.ft / a.ftx) if a.ftx > 0 else None,
                "front": (a.fr / a.frn) if a.frn else None, "kick": ((a.kk - slope * a.kx) / a.kkn) if a.kkn else None,
                "top": (a.tt / a.ttx) if a.ttx > 0 else None}

    def counts(a):
        return {"win": int(a.n), "rank": int(a.rkn), "long": int(a.ltn), "fav": int(a.ftn), "front": int(a.frn), "kick": int(a.kkn), "top": int(a.ttn)}

    slope = G[1] / G[0] if G[0] else 0.0              # 前に出すほど上がりは遅くなる。その分を引いて、『位置取りを変えた影響』を除く
    people = [j for (j, per), a in acc.items() if per == "all" and a.n >= MIN_PERSON]
    raw = {j: vals(acc[(j, "all")]) for j in people}
    cn = {j: counts(acc[(j, "all")]) for j in people}
    # 縮小：軸ごとの平均へ、走数が少ないほど寄せる（k は軸の走数の目安）
    SHR = {"win": 400, "rank": 150, "long": 120, "fav": 250, "front": 100, "kick": 100, "top": 80}
    shr = {}
    for ax, *_ in AXES:
        xs = [(raw[j][ax], cn[j][ax]) for j in people if raw[j][ax] is not None]
        tot = sum(w for _, w in xs)
        mu = sum(v * w for v, w in xs) / tot if tot else 0
        for j in people:
            v, w = raw[j][ax], cn[j][ax]
            shr[(j, ax)] = None if v is None else mu + (v - mu) * w / (w + SHR[ax])
    score = {}
    for ax, *_ in AXES:
        ok = sorted((shr[(j, ax)], j) for j in people if shr[(j, ax)] is not None)
        for r, (_, j) in enumerate(ok):
            score[(j, ax)] = round(100 * r / max(1, len(ok) - 1))
    # 続くか
    persist = {}
    for ax, *_ in AXES:
        pairs = []
        for j in people:
            a1, a2 = acc.get((j, "h1")), acc.get((j, "h2"))
            if not a1 or not a2:
                continue
            c1, c2 = counts(a1), counts(a2)
            if c1[ax] >= 100 and c2[ax] >= 100:
                pairs.append((vals(a1)[ax], vals(a2)[ax], min(c1[ax], c2[ax])))
        r, m = corr(pairs)
        persist[ax] = {"corr": r, "pairs": m}
    out = []
    for j in sorted(people, key=lambda j: -acc[(j, "all")].n):
        lo, hi = span[j]
        out.append({"id": j, "name": names[j], "n": int(acc[(j, "all")].n), "years": [lo, hi],
                    "raw": {ax: (None if raw[j][ax] is None else round(raw[j][ax], 3)) for ax, *_ in AXES},
                    "count": cn[j], "score": {ax: score.get((j, ax)) for ax, *_ in AXES}})
    jst = timezone(timedelta(hours=9))
    return {"version": 1, "generated": datetime.now(jst).strftime("%Y-%m-%d %H:%M"), "split_year": SPLIT_YEAR, "min_person": MIN_PERSON,
            "axes": [{"id": a, "label": l, "desc": d, "persist": persist[a]} for a, l, d in AXES], "jockeys": out}


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
