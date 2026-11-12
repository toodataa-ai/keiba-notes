#!/usr/bin/env python3
"""要素の検証（研究のみ・予想には使わない）。公開するのは集計だけ（1頭ごとの記録・馬名は出さない）。
  python3 -m factor_screen_v1.screen --table <表.pkl> --out docs/data/factor_screen_v1.json
見るもの（どれも『発走前に分かる要素』の単独と、2つの組み合わせ）：
 ①勝率との関係（勝ちやすさ）＝実際の勝ち数÷『頭数だけで決めた期待の勝ち数（1/頭数）』。人気で勝ちやすい要素もここに出る。
 ②オッズ妙味＝実際の勝ち数÷『オッズから作った期待の勝ち数』（A/E）。1より大きいほど、人気で説明できない上乗せ。
確かめ方：前半（〜2021年）で z≥2 だった条件を『候補』とし、後半（2022年〜）で同じ向きが続くかを見る。
条件の数が多いので、偶然でも一部は当たる。偶然の見込みの数と、実際に後半で続いた数を並べて示す（BH法のq値も付ける）。"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SPLIT = 2022
MIN_N = 300          # 条件に入る出走数の下限（全期間）
MIN_H = 120          # 前半・後半それぞれの下限
Z_FIND = 2.0

NAMES = {
    "venue": "競馬場", "surface": "芝・ダート", "dist_band": "距離", "going": "馬場", "klass": "クラス", "heads_band": "頭数",
    "frame_band": "枠", "no_pos": "馬番の位置", "sex": "性別", "age_band": "年齢", "weight_band": "馬体重", "wdiff_band": "体重増減",
    "pop_band": "人気", "nichi_band": "開催の進み", "season": "季節", "starts_band": "経験(出走数)", "prev_finish": "前走の着順",
    "prev_vs_pop": "前走の人気との比べ", "prev_style": "前走の脚質", "interval": "前走からの間隔", "surf_change": "芝ダ替わり",
    "dist_change": "距離の変化", "jockey_change": "騎手の乗り替わり", "sire_line": "父の系統",
    "jockey": "騎手", "trainer": "調教師", "course": "コース",
}
PAIR_FEATS = ["venue", "surface", "dist_band", "going", "klass", "heads_band", "frame_band", "no_pos", "sex", "age_band",
              "weight_band", "wdiff_band", "pop_band", "nichi_band", "season", "starts_band", "prev_finish", "prev_vs_pop",
              "prev_style", "interval", "surf_change", "dist_change", "jockey_change", "sire_line"]
SINGLE_ONLY = ["jockey", "trainer", "course"]


def cut(s, edges, labels):
    return pd.cut(s, edges, labels=labels, right=True).astype("object")


def prep(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["dist_band"] = cut(d["dist"], [0, 1300, 1600, 2000, 9999], ["〜1300m", "1400〜1600m", "1700〜2000m", "2100m〜"])
    d["heads_band"] = cut(d["heads"], [0, 10, 14, 99], ["〜10頭", "11〜14頭", "15頭〜"])
    d["frame_band"] = cut(d["frame"], [0, 2, 6, 8], ["内枠(1〜2)", "中枠(3〜6)", "外枠(7〜8)"])
    rel = d["no"] / d["heads"]
    d["no_pos"] = cut(rel, [0, 1 / 3, 2 / 3, 1.01], ["馬番が小さい(内寄り)", "馬番が中ほど", "馬番が大きい(外寄り)"])
    d["age_band"] = cut(d["age"], [0, 2, 3, 4, 5, 99], ["2歳", "3歳", "4歳", "5歳", "6歳以上"])
    d["weight_band"] = cut(d["weight"], [0, 440, 480, 520, 999], ["〜440kg", "441〜480kg", "481〜520kg", "521kg〜"])
    d["wdiff_band"] = cut(d["wdiff"], [-99, -8, -2, 1, 7, 99], ["−8以下", "−7〜−2", "−1〜+1", "+2〜+7", "+8以上"])
    d["pop_band"] = cut(d["pop"], [0, 1, 3, 6, 9, 99], ["1番人気", "2〜3番人気", "4〜6番人気", "7〜9番人気", "10番人気〜"])
    d["nichi_band"] = cut(d["nichi"], [0, 3, 6, 99], ["開催序盤(1〜3日目)", "開催中盤(4〜6日目)", "開催終盤(7日目〜)"])
    d["season"] = d["month"].map(lambda m: "春(3〜5月)" if 3 <= m <= 5 else "夏(6〜8月)" if 6 <= m <= 8 else "秋(9〜11月)" if 9 <= m <= 11 else "冬(12〜2月)")
    d["starts_band"] = cut(d["starts"], [-1, 0, 3, 9, 999], ["初出走", "1〜3戦", "4〜9戦", "10戦以上"])
    d["going"] = d["going"].replace({"稍重": "道悪(稍重〜不良)", "重": "道悪(稍重〜不良)", "不良": "道悪(稍重〜不良)", "良": "良"})
    d["course"] = d["venue"] + d["surface"] + d["dist"].astype(str) + "m" + d["inout"].fillna("").map(lambda x: f"({x})" if x else "")
    for k in ("jockey", "trainer"):
        vc = d[k].value_counts()
        keep = set(vc[vc >= 600].index)
        d[k] = d[k].where(d[k].isin(keep))
    d["win"] = (d["finish"] == 1).astype(float)
    d["top3"] = d["finish"].map(lambda f: 1.0 if isinstance(f, (int, float)) and f == f and f <= 3 else 0.0)
    d["exp"] = d["p"]
    d["var"] = d["p"] * (1 - d["p"])
    d["fvar"] = d["fair"] * (1 - d["fair"])
    d["ret"] = d["win"] * d["odds"]
    d["half"] = np.where(d["year"] < SPLIT, 1, 2)
    d["one"] = 1.0
    return d


SUMS = ["one", "win", "top3", "exp", "var", "fair", "fvar", "ret"]


def zscore(x, e, v):
    return (x - e) / math.sqrt(v) if v > 0 else None


def pval(z):
    return math.erfc(abs(z) / math.sqrt(2)) if z is not None else 1.0


def cells(d: pd.DataFrame, feats: list[str]) -> list[dict]:
    sub = d.dropna(subset=feats)
    g = sub.groupby(feats + ["half"], observed=True)[SUMS].sum()
    out = []
    for key, grp in g.reset_index().groupby(feats, observed=True):
        key = key if isinstance(key, tuple) else (key,)
        a = grp.set_index("half")
        tot = a[SUMS].sum()
        n = tot["one"]
        if n < MIN_N:
            continue

        def part(h):
            if h not in a.index:
                return {"n": 0, "ae": None, "z": None, "lift": None, "zl": None}
            r = a.loc[h]
            return {"n": int(r["one"]), "ae": r["win"] / r["exp"] if r["exp"] > 0 else None, "z": zscore(r["win"], r["exp"], r["var"]),
                    "lift": r["win"] / r["fair"] if r["fair"] > 0 else None, "zl": zscore(r["win"], r["fair"], r["fvar"])}
        h1, h2 = part(1), part(2)
        z = zscore(tot["win"], tot["exp"], tot["var"])
        zl = zscore(tot["win"], tot["fair"], tot["fvar"])
        out.append({"f": feats, "v": list(key), "n": int(n), "wr": tot["win"] / n, "top3": tot["top3"] / n,
                    "lift": tot["win"] / tot["fair"], "ae": tot["win"] / tot["exp"], "roi": tot["ret"] / n,
                    "z": z, "zl": zl, "h1": h1, "h2": h2})
    return out


def bh(ps, q=0.05):
    """BH法：q値（発見の偽りの割合の目安）"""
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    qv = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, ps[i] * m / rank)
        qv[i] = prev
    return qv


def r3(x, nd=3):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), nd)


def compact(c):
    return {"f": [NAMES[x] for x in c["f"]], "v": c["v"], "n": c["n"], "wr": r3(c["wr"]), "top3": r3(c["top3"]), "lift": r3(c["lift"], 2),
            "ae": r3(c["ae"], 2), "roi": r3(c["roi"], 2), "z": r3(c["z"], 2), "zl": r3(c["zl"], 2), "q": r3(c.get("q"), 3), "ql": r3(c.get("ql"), 3),
            "h1": {k: r3(v, 2) for k, v in c["h1"].items()}, "h2": {k: r3(v, 2) for k, v in c["h2"].items()}}


def summarize(allc, zkey, h_key, ae_key, label):
    """前半で z≥2 の条件（候補）が、後半でも同じ向きか"""
    cand = [c for c in allc if c["h1"]["n"] >= MIN_H and c["h2"]["n"] >= MIN_H and c["h1"][zkey] is not None and c["h1"][zkey] >= Z_FIND]
    tested = [c for c in allc if c["h1"]["n"] >= MIN_H and c["h2"]["n"] >= MIN_H and c["h1"][zkey] is not None]
    conf = [c for c in cand if c["h2"][ae_key] is not None and c["h2"][ae_key] > 1.0]
    sig = [c for c in cand if c["h2"][zkey] is not None and c["h2"][zkey] >= 2.0]
    # 後半の平均（頭数で重み）
    w = sum(c["h2"]["n"] for c in cand) or 1
    mean_h2 = sum((c["h2"][ae_key] or 1.0) * c["h2"]["n"] for c in cand) / w
    return {"label": label, "tested": len(tested), "candidates": len(cand),
            "chance_expected": round(len(tested) * 0.0228, 1),   # z≥2 を満たす偶然の見込み（片側2.28%）
            "continued": len(conf), "continued_pct": round(100 * len(conf) / len(cand), 1) if cand else None,
            "strong": len(sig), "mean_h2": round(mean_h2, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = prep(pd.read_pickle(a.table))
    d = d[d["pop"].notna() & d["finish"].notna()]
    allc = []
    for f in PAIR_FEATS + SINGLE_ONLY:
        allc += cells(d, [f])
    for f1, f2 in itertools.combinations(PAIR_FEATS, 2):
        allc += cells(d, [f1, f2])
    # q値（全期間のz、条件の数で補正）
    qa = bh([pval(c["z"]) for c in allc])
    ql = bh([pval(c["zl"]) for c in allc])
    for c, x, y in zip(allc, qa, ql):
        c["q"], c["ql"] = x, y
    singles = [c for c in allc if len(c["f"]) == 1]
    pairs = [c for c in allc if len(c["f"]) == 2]
    both = lambda c, k, t: c["h1"][k] is not None and c["h2"][k] is not None and c["h1"][k] >= t and c["h2"][k] >= t

    def top(cs, zk, ak, n=40):
        """前半・後半ともに z≥1.5（同じ向きが続いた）条件を、後半のzの大きい順に"""
        keep = [c for c in cs if c["h1"]["n"] >= MIN_H and c["h2"]["n"] >= MIN_H and both(c, zk, 1.5)
                and (c["h1"][ak] or 0) > 1 and (c["h2"][ak] or 0) > 1]
        keep.sort(key=lambda c: -(min(c["h1"][zk], c["h2"][zk])))
        return [compact(c) for c in keep[:n]]

    def bottom(cs, n=20):
        keep = [c for c in cs if c["h1"]["n"] >= MIN_H and c["h2"]["n"] >= MIN_H and c["h1"]["z"] is not None and c["h2"]["z"] is not None
                and c["h1"]["z"] <= -1.5 and c["h2"]["z"] <= -1.5]
        keep.sort(key=lambda c: max(c["h1"]["z"], c["h2"]["z"]))
        return [compact(c) for c in keep[:n]]

    by_feat = {}
    for c in singles:
        by_feat.setdefault(NAMES[c["f"][0]], []).append(c)
    single_tbl = {}
    for k, cs in by_feat.items():
        if k in ("騎手", "調教師", "コース"):
            cs = sorted(cs, key=lambda c: -abs(c["z"] or 0))[:15]
        else:
            cs = sorted(cs, key=lambda c: -c["n"])
        single_tbl[k] = [compact(c) for c in cs]

    jst = timezone(timedelta(hours=9))
    out = {
        "generated": datetime.now(jst).strftime("%Y-%m-%d %H:%M"),
        "meta": {"rows": int(len(d)), "races": int(d["code"].nunique()), "years": [int(d["year"].min()), int(d["year"].max())],
                 "split_year": SPLIT, "min_n": MIN_N, "features": [NAMES[x] for x in PAIR_FEATS], "entity_features": [NAMES[x] for x in SINGLE_ONLY],
                 "conditions_tested": len(allc), "singles": len(singles), "pairs": len(pairs),
                 "base_rate": {"win": r3(d["win"].mean(), 4), "ae": r3(d["win"].sum() / d["exp"].sum(), 3)}},
        "summary": {
            "win_singles": summarize(singles, "zl", "lift", "lift", "勝率（単独）"), "win_pairs": summarize(pairs, "zl", "lift", "lift", "勝率（2つの組み合わせ）"),
            "value_singles": summarize(singles, "z", "ae", "ae", "オッズ妙味（単独）"), "value_pairs": summarize(pairs, "z", "ae", "ae", "オッズ妙味（2つの組み合わせ）"),
        },
        "win": {"singles": top(singles, "zl", "lift", 25), "pairs": top(pairs, "zl", "lift", 40)},
        "value": {"singles": top(singles, "z", "ae", 25), "pairs": top(pairs, "z", "ae", 40), "overbet": bottom(allc, 25)},
        "single_tables": single_tbl,
        "q_pass": {"value_q05": sum(1 for c in allc if c["q"] < 0.05 and c["ae"] > 1), "win_q05": sum(1 for c in allc if c["ql"] < 0.05 and c["lift"] > 1)},
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
    print("conditions", len(allc), "q_pass", out["q_pass"], "bytes", Path(a.out).stat().st_size)


if __name__ == "__main__":
    main()
