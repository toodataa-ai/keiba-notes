#!/usr/bin/env python3
"""騎手のレーダーチャート（研究のみ・公開するのは集計だけ）。人気（オッズ）は使わない＝絶対評価。
  python3 -m trends_v1.jockey_radar --data <非公開 data_v2> --out docs/data/jockey_radar_v1.json
7つの軸（どれも結果そのもの。人気・オッズとの比べ方はしない）：
  勝率／連対率（2着内）／複勝率（3着内）
  着順の良さ …… 平均の着順を、頭数で割って0〜100に直したもの（100＝いつも1着、0＝いつも最下位）
  先行力 …… 最初のコーナーでの位置（頭数で割った位置の前め度。100＝いつも先頭）
  末脚 …… 上がり3Fのそのレース内での速さの順位（100＝いつも最速）
  上級戦の強さ …… オープン・重賞での複勝率
得点は、軸ごとに騎手151人の値の幅（下位2%〜最高）を0〜100に直したもの。走数が少ない軸は平均に寄せる（縮小）。
注意：人気を使わないので、乗る馬の力（有力馬に乗れるか）の違いがそのまま入る。
『続くか』は、前半（〜2021年）と後半（2022年〜）で、騎手の並びがそろうか（相関）。"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .parse import iter_races
from .radar_cond import CONDS, MIN_COND, keys
from .stats import corr

SPLIT_YEAR = 2022
MIN_PERSON = 300
MIN_YEAR = 100      # 年別は、その年に100走以上した騎手だけ
AXES = [
    ("win", "勝率", "出走のうち1着になった割合。"),
    ("p2", "連対率", "出走のうち2着以内に入った割合。"),
    ("p3", "複勝率", "出走のうち3着以内に入った割合。"),
    ("rank", "着順の良さ", "平均の着順（頭数で割って、1着＝100、最下位＝0にした平均）。"),
    ("front", "先行力", "最初のコーナーでの位置の前め度（頭数で割った位置。先頭＝100、最後方＝0の平均）。"),
    ("kick", "末脚", "上がり3Fの、そのレース内での速さの順位（最速＝100、最も遅い＝0の平均）。"),
    ("top", "上級戦の強さ", "オープン・重賞での複勝率。"),
]
SHR = {"win": 300, "p2": 250, "p3": 200, "rank": 150, "front": 100, "kick": 100, "top": 80}


class A:
    __slots__ = ("n", "w", "p2", "p3", "rk", "rkn", "fr", "frn", "kk", "kkn", "tn", "t3")

    def __init__(self):
        for k in self.__slots__:
            setattr(self, k, 0.0)


def build(data_dir: Path) -> dict:
    acc = defaultdict(A)
    names, span = {}, {}
    for race, rows in iter_races(data_dir):
        if race["surface"] not in ("芝", "ダート") or not race["venue"]:
            continue
        n = len(rows)
        half = "h1" if race["year"] < SPLIT_YEAR else "h2"
        l3s = sorted(r["last3"] for r in rows if r["last3"])
        for r in rows:
            jid = r["jockey"]
            if not jid:
                continue
            names[jid] = r["jockey_name"]
            lo, hi = span.get(jid, (race["year"], race["year"]))
            span[jid] = (min(lo, race["year"]), max(hi, race["year"]))
            fin = r["finish"]
            for per in ("all", half, race["year"], *keys(race["surface"], race["venue"], r["sex"], race["date"])):
                a = acc[(jid, per)]
                if fin is not None:                       # 中止・除外は着順の軸に入れない（出走数にも数えない）
                    a.n += 1
                    a.w += fin == 1
                    a.p2 += fin <= 2
                    a.p3 += fin <= 3
                    if n > 1:
                        a.rk += 100 * (1 - (fin - 1) / (n - 1)); a.rkn += 1
                    if race["klass"] == "OP・重賞":
                        a.tn += 1; a.t3 += fin <= 3
                if r["pass"] and n > 1:
                    a.fr += 100 * (1 - (r["pass"][0] - 1) / (n - 1)); a.frn += 1
                if r["last3"] and len(l3s) >= 5:
                    rank = sum(1 for x in l3s if x < r["last3"]) + 1
                    a.kk += 100 * (1 - (rank - 1) / (len(l3s) - 1)); a.kkn += 1

    def vals(a):
        return {"win": a.w / a.n if a.n else None, "p2": a.p2 / a.n if a.n else None, "p3": a.p3 / a.n if a.n else None,
                "rank": a.rk / a.rkn if a.rkn else None, "front": a.fr / a.frn if a.frn else None,
                "kick": a.kk / a.kkn if a.kkn else None, "top": a.t3 / a.tn if a.tn else None}

    def counts(a):
        return {"win": int(a.n), "p2": int(a.n), "p3": int(a.n), "rank": int(a.rkn), "front": int(a.frn), "kick": int(a.kkn), "top": int(a.tn)}

    def scored(people, per):
        raw = {j: vals(acc[(j, per)]) for j in people}
        cn = {j: counts(acc[(j, per)]) for j in people}
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
            vs = [v for v, _ in ok]
            lo, hi = vs[int(len(vs) * 0.02)], vs[-1]      # 下位2%を0、最高の人を100にして、間を直線で結ぶ（順位ではなく、値の開きがそのまま見える）
            for v, j in ok:
                score[(j, ax)] = round(100 * min(1.0, max(0.0, (v - lo) / (hi - lo)))) if hi > lo else 50
        return raw, cn, score

    people = [j for (j, per), a in acc.items() if per == "all" and a.n >= MIN_PERSON]
    raw, cn, score = scored(people, "all")
    years = sorted({per for (_, per) in acc if isinstance(per, int)})
    by_year = {}
    for y in years:
        py = [j for j in people if acc[(j, y)].n >= MIN_YEAR]
        if len(py) < 20:
            continue
        ry, cy, sy = scored(py, y)
        by_year[str(y)] = [[j, int(acc[(j, y)].n), [sy.get((j, ax)) for ax, *_ in AXES],
                            [None if ry[j][ax] is None else round(ry[j][ax], 4) for ax, *_ in AXES]] for j in
                           sorted(py, key=lambda j: -acc[(j, y)].n)]
    cond_out = {}
    for ck, lab, grp in CONDS:
        pc = [j for j in people if acc[(j, ck)].n >= MIN_COND]
        if len(pc) < 20:
            continue
        rc, cc, sc = scored(pc, ck)
        cond_out[ck] = {"label": lab, "group": grp, "min": MIN_COND, "jockeys": [
            [j, int(acc[(j, ck)].n), [sc.get((j, ax)) for ax, *_ in AXES],
             [None if rc[j][ax] is None else round(rc[j][ax], 4) for ax, *_ in AXES]]
            for j in sorted(pc, key=lambda j: -acc[(j, ck)].n)]}
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
                    "raw": {ax: (None if raw[j][ax] is None else round(raw[j][ax], 4)) for ax, *_ in AXES},
                    "count": cn[j], "score": {ax: score.get((j, ax)) for ax, *_ in AXES}})
    jst = timezone(timedelta(hours=9))
    return {"version": 3, "min_year": MIN_YEAR, "generated": datetime.now(jst).strftime("%Y-%m-%d %H:%M"), "split_year": SPLIT_YEAR, "min_person": MIN_PERSON,
            "axes": [{"id": a, "label": l, "desc": d, "persist": persist[a]} for a, l, d in AXES], "jockeys": out, "by_year": by_year, "_cond": cond_out}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cond-dir")
    a = ap.parse_args()
    d = build(Path(a.data))
    cd = d.pop("_cond")
    if a.cond_dir:
        Path(a.cond_dir).mkdir(parents=True, exist_ok=True)
        for k, v in cd.items():
            Path(a.cond_dir, "abs_%s.json" % k).write_text(json.dumps(v, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        d["conds"] = [{"key": k, "label": v["label"], "group": v["group"], "n": len(v["jockeys"])} for k, v in cd.items()]
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("jockeys", len(d["jockeys"]), "bytes", Path(a.out).stat().st_size)
    for ax in d["axes"]:
        print(ax["id"], ax["label"], ax["persist"])
