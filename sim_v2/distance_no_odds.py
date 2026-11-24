"""距離の変化・得意距離が、オッズを使わない能力モデルに足して効くかの検証（研究のみ・予想には使わない）。
土台＝strength_model と同じ特徴（今回のオッズは使わない）から、距離に関する列を外したもの。
 B0：土台（距離の列なし） B1：B0＋前走からの延長・短縮・stamina_fit（既存の距離の列） B2：B1＋今回の4項目
前半（〜2024-06）で係数を決め、後半（2024-07〜）の対数損失を比べる。差の95%幅はレース単位のやり直し計算。
使い方：python3 -m sim_v2.build_races ... --with-hid --out-backtest R.json のあと
        python3 -m sim_v2.distance_no_odds --races R.json --data <非公開 data_v2> --out out.json"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim_v2.strength_model import feats, FEATS
from sire_db_v1.debut_common import load_horses
from sire_db_v1.distance_features import horse_features

SPLIT = "2024-07-01"
DIST_COLS = ["dist_up", "dist_down", "stamina_fit"]
NEW = ["過去の延長で成績が上がる癖", "過去の短縮で成績が上がる癖", "今回の距離帯での過去の3着内率（全体との差）", "今回の距離が得意距離（最良の帯）"]


def design(races, hf, use_new):
    out = []
    for r in races:
        w = [i for i, x in enumerate(r["runners"]) if x["finish"] == 1]
        if len(w) != 1:
            continue
        X = feats(r)
        extra = []
        for x in r["runners"]:
            v = hf.get((x.get("hid"), r["code"]))
            extra.append([v[2], v[3], v[4], v[5]] if v else [0.0, 0.0, 0.0, 0.0])
        out.append((r["date"], X, np.array(extra, float), w[0]))
    return out


def newton(data, cols, l2=0.02, iters=60):
    allX = np.vstack([d[0][:, cols] for d in data]); mu = allX.mean(0); sd = allX.std(0) + 1e-9
    b = np.zeros(len(cols)); n = len(data)
    Z = [((d[0][:, cols] - mu) / sd, d[1]) for d in data]
    for _ in range(iters):
        g = np.zeros_like(b); H = np.zeros((len(b), len(b)))
        for X, w in Z:
            z = X @ b; z -= z.max(); p = np.exp(z); p /= p.sum()
            m = p @ X; Xc = X - m
            g += X[w] - m; H += (Xc * p[:, None]).T @ Xc
        g -= l2 * n * 0.001 * b; H += np.eye(len(b)) * l2 * n * 0.001
        st = np.linalg.solve(H, g); b += st
        if np.abs(st).max() < 1e-6:
            break
    return mu, sd, b


def per_race_ll(data, cols, m):
    mu, sd, b = m; out = np.zeros(len(data))
    for i, d in enumerate(data):
        z = ((d[0][:, cols] - mu) / sd) @ b; z -= z.max(); lp = z - np.log(np.exp(z).sum())
        out[i] = -lp[d[1]]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--races", required=True); ap.add_argument("--data", required=True); ap.add_argument("--out")
    a = ap.parse_args()
    races = json.loads(Path(a.races).read_text(encoding="utf-8"))["races"]
    hf = horse_features(load_horses(a.data))
    raw = design(races, hf, True)
    # 設計行列：[strength特徴(26) | 新4項目]
    data = [(np.hstack([X, E]), w, d) for d, X, E, w in raw]
    tr = [(X, w) for X, w, d in data if d < SPLIT]; te = [(X, w) for X, w, d in data if d >= SPLIT]
    te_date = [d for X, w, d in data if d >= SPLIT]
    print(f"レース 前半{len(tr)} 後半{len(te)}", file=sys.stderr)
    nf = len(FEATS); idx = {n: i for i, n in enumerate(FEATS)}
    b0 = [i for i, n in enumerate(FEATS) if n not in DIST_COLS]
    b1 = list(range(nf)); new = [nf + k for k in range(4)]
    models = {"B0": b0, "B1": b1, "B2": b1 + new}
    for k in range(4): models[f"B1+{NEW[k]}"] = b1 + [new[k]]
    models["B0+新4項目(既存の距離列なし)"] = b0 + new
    fitted = {k: newton(tr, c) for k, c in models.items()}
    ll = {k: per_race_ll(te, c, fitted[k]) for k, c in models.items()}
    rng = np.random.default_rng(7); n = len(te)
    def ci(diff):
        bs = [diff[rng.integers(0, n, n)].mean() for _ in range(3000)]
        return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    res = {"races": {"前半": len(tr), "後半": len(te)}, "test_ll": {k: float(v.mean()) for k, v in ll.items()}, "gain": {}}
    def cmp(name, base, new_):
        d = ll[base] - ll[new_]; res["gain"][name] = {"gain": float(d.mean()), "ci95": ci(d)}
    cmp("既存の距離列（延長・短縮・stamina_fit）の寄与：B1 vs B0", "B0", "B1")
    cmp("新4項目をまとめて：B2 vs B1", "B1", "B2")
    for k in range(4): cmp(f"{NEW[k]}（B1に1項目）", "B1", f"B1+{NEW[k]}")
    cmp("新4項目だけ足す（既存の距離列なし）：B0+新4 vs B0", "B0", "B0+新4項目(既存の距離列なし)")
    # 係数の向き：前半で決めた係数と、後半だけで決め直した係数
    def newton_sub(sub): return newton(sub, b1 + new)
    mu, sd, b = fitted["B2"]; coef_tr = dict(zip(NEW, [round(float(x), 4) for x in b[-4:]]))
    coef_te = dict(zip(NEW, [round(float(x), 4) for x in newton_sub(te)[2][-4:]]))
    res["coef_B2_train"] = coef_tr; res["coef_B2_test_refit"] = coef_te
    res["same_sign"] = {k: (coef_tr[k] > 0) == (coef_te[k] > 0) for k in NEW}
    # 年別の安定性（後半を半分に分けて B2 vs B1）
    mid = sorted(set(te_date))[len(set(te_date)) // 2]
    sel = np.array([d < mid for d in te_date]); d = ll["B1"] - ll["B2"]
    res["B2_vs_B1_by_half"] = {"後半の前の半分": float(d[sel].mean()), "後半の後の半分": float(d[~sel].mean())}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.out: Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
