"""距離の変化と得意距離が、単勝オッズ以上の情報を持つかの検証（研究のみ・予想には使わない）。
見るもの：①前走からの距離延長／短縮（200m以上）②その馬が過去の延長／短縮で成績を上げたか下げたか
③その馬の得意な距離帯（過去の3着内率）に今回の距離が合うか。
見方：オッズだけのモデルに足して、後半の期間（2024-07以降）の対数損失が良くなるか。前半（〜2024-06）で係数を決める。
使い方：python3 -m sire_db_v1.distance_features --data <非公開 data_v2>"""
from __future__ import annotations
import argparse, collections, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sire_db_v1.debut_common import load_horses
from sire_db_v1.debut_model import fit, ll

JRA = {"京都", "阪神", "中山", "東京", "福島", "新潟", "小倉", "札幌", "函館", "中京"}
SPLIT = "2024-07-01"
SINCE = "2022-01-01"
NAMES = ["距離延長(200m以上)", "距離短縮(200m以上)", "過去の延長で成績が上がる癖", "過去の短縮で成績が上がる癖", "今回の距離帯での過去の3着内率（全体との差）", "今回の距離が得意距離（最良の帯）"]
PRIOR_N, BASE = 3.0, 0.25


def bucket(d): return int(round(d / 200.0) * 200)


def pct(r): return (r["finish"] - 1) / max(1, (r.get("heads") or 2) - 1)


def horse_features(hs):
    """{(horse_id, code): [ext, short, resp_ext, resp_short, apt, is_best]}（その出走より前の履歴だけで作る）"""
    out = {}
    for h in hs.values():
        hist = [r for r in (h.get("history") or []) if r.get("date") and isinstance(r.get("finish"), int) and r.get("dist")]
        hist.sort(key=lambda r: r["date"])
        trans = {"ext": [], "short": []}            # 過去の遷移での 順位の変化（負＝良くなった）
        bk = collections.defaultdict(lambda: [0, 0])  # 距離帯 -> [3着内, 出走]
        for i, r in enumerate(hist):
            if r["date"] >= SINCE and r.get("venue") in JRA and r.get("odds") and r.get("heads") and r.get("code"):
                prev = hist[i - 1] if i > 0 else None
                ext = sht = 0.0
                if prev:
                    dd = r["dist"] - prev["dist"]
                    ext = 1.0 if dd >= 200 else 0.0; sht = 1.0 if dd <= -200 else 0.0
                re_ = -sum(trans["ext"]) / (len(trans["ext"]) + 2.0) if trans["ext"] else 0.0
                rs_ = -sum(trans["short"]) / (len(trans["short"]) + 2.0) if trans["short"] else 0.0
                n_all = sum(v[1] for v in bk.values()); t_all = sum(v[0] for v in bk.values())
                base = (t_all + BASE * PRIOR_N) / (n_all + PRIOR_N)
                b = bucket(r["dist"]); t, n = bk.get(b, (0, 0))
                apt = (t + base * PRIOR_N) / (n + PRIOR_N) - base
                best = 0.0
                if n_all >= 5:
                    cand = {k: (v[0] + base * PRIOR_N) / (v[1] + PRIOR_N) for k, v in bk.items() if v[1] >= 2}
                    if cand and max(cand, key=cand.get) == b: best = 1.0
                out[(h["id"], r["code"])] = [ext, sht, re_ * ext, rs_ * sht, apt, best]
            # この出走を履歴に足す
            if i > 0:
                prev = hist[i - 1]; dd = r["dist"] - prev["dist"]; ch = pct(r) - pct(prev)
                if dd >= 200: trans["ext"].append(ch)
                elif dd <= -200: trans["short"].append(ch)
            b = bucket(r["dist"]); bk[b][1] += 1; bk[b][0] += 1 if r["finish"] <= 3 else 0
    return out


def build(hs):
    feats = horse_features(hs)
    races = collections.defaultdict(list)
    for h in hs.values():
        for r in h.get("history") or []:
            k = (h["id"], r.get("code"))
            if k in feats and isinstance(r.get("finish"), int) and r.get("odds"):
                races[r["code"]].append((r["date"], r["heads"], r["finish"], r["odds"], feats[k], r["surface"], r["dist"]))
    rows = []
    for code, es in races.items():
        heads = es[0][1]
        if len(es) != heads or sum(1 for e in es if e[2] == 1) != 1: continue
        lo = np.array([math.log(1.0 / e[3]) for e in es]); X = np.array([e[4] for e in es]); w = [e[2] for e in es].index(1)
        rows.append((es[0][0], code, X, lo - lo.max(), w))
    rows.sort(key=lambda t: t[0])
    return rows


def ae_table(rows):
    """区分ごとのA/E（実際の勝ち ÷ 0.8/オッズの合計）。前半・後半で向きが続くか"""
    res = {}
    for nm, sel in (("前半", lambda d: d < SPLIT), ("後半", lambda d: d >= SPLIT)):
        S = collections.defaultdict(lambda: [0, 0.0, 0])
        for d, c, X, lo, w in rows:
            if not sel(d): continue
            p = np.exp(lo); p = p / p.sum() * 0.8
            for j in range(len(lo)):
                for key, flag in (("延長", X[j][0]), ("短縮", X[j][1]), ("同距離(前走あり)", None)):
                    pass
                cat = "延長" if X[j][0] else "短縮" if X[j][1] else "ほぼ同じ"
                S[cat][0] += 1 if j == w else 0; S[cat][1] += p[j]; S[cat][2] += 1
        res[nm] = {k: {"出走": v[2], "勝ち": v[0], "期待": round(v[1], 1), "A/E": round(v[0] / v[1], 3) if v[1] else None} for k, v in S.items()}
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    hs = load_horses(a.data)
    rows = build(hs)
    tr = [r for r in rows if r[0] < SPLIT]; te = [r for r in rows if r[0] >= SPLIT]
    print(f"レース数 前半{len(tr)} 後半{len(te)}", file=sys.stderr)
    res = {"races": {"前半": len(tr), "後半": len(te)}, "ae": ae_table(rows)}
    base = fit(tr, []); res["baseline_test_ll"] = ll(base, te, [])
    allc = list(range(6)); full = fit(tr, allc, ridge=1.0)
    res["all_features"] = {"coef": dict(zip(NAMES, [round(float(x), 4) for x in full[1:]])), "alpha": round(float(full[0]), 3), "test_ll": ll(full, te, allc), "gain": res["baseline_test_ll"] - ll(full, te, allc)}
    # 1項目ずつ
    res["each"] = {}
    for j in allc:
        t = fit(tr, [j], ridge=1.0); g = res["baseline_test_ll"] - ll(t, te, [j])
        # ブートストラップ（レース単位）で改善の95%幅
        rng = np.random.default_rng(j); diffs = []
        for _ in range(200):
            idx = rng.integers(0, len(te), len(te)); sub = [te[i] for i in idx]
            diffs.append(ll(base, sub, []) - ll(t, sub, [j]))
        res["each"][NAMES[j]] = {"coef": round(float(t[1]), 4), "gain": g, "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.out: Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
