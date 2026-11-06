"""新馬戦：血統などの傾向が、単勝オッズに織り込まれていない情報を持つかの検証（研究のみ）。
各特徴は「そのレースの日より前」のデータだけで作る。モデル＝レース内の条件付きロジット
（得点 = a*log(オッズ由来の確率) + Σ b*特徴）。前半で b を決め、後半の新馬戦で対数損失を比べる。"""
from __future__ import annotations
import argparse, collections, json, math, sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sire_db_v1.debut_common import load_horses, debut_races, mb

K = 4.0  # 縮小（勝ち数の目安）


def lae(w, e):
    return math.log((w + K) / (e + K))


def build(hs, drs):
    ev = []  # 全出走（日付順）
    for h in hs.values():
        p = h["ped"]
        for r in h.get("history") or []:
            if r.get("odds") and r.get("date") and isinstance(r.get("finish"), int):
                try:
                    m = mb(h["birth"], r["date"])
                except Exception:
                    continue
                ev.append((r["date"], h, r, m))
    ev.sort(key=lambda x: x[0])
    races = sorted(drs.items(), key=lambda kv: kv[1][0][1]["date"])
    S = collections.defaultdict(lambda: [0.0, 0.0])  # key -> [wins, exp]
    rows = []  # 1レース=（特徴行列, 勝ち馬index, ログオッズ）
    j = 0
    for code, lst in races:
        d = lst[0][1]["date"]
        while j < len(ev) and ev[j][0] < d:
            _, h, r, m = ev[j]; j += 1
            p = 0.8 / r["odds"]; w = 1.0 if r["finish"] == 1 else 0.0
            ped = h["ped"]; prof = h.get("profile") or {}
            deb = "新馬" in (r.get("race") or "")
            sur = r["surface"]
            for key in (("sire", ped["sire"], "all", sur), ("dsire", ped.get("dam_sire"), "all", sur), ("dam", ped.get("dam"), "all", "-"),
                        ("sire", ped["sire"], "young", sur) if m <= 38 else None):
                if key and key[1]:
                    S[key][0] += w; S[key][1] += p
            if deb:
                for key in (("sire", ped["sire"], "deb", sur), ("sire", ped["sire"], "deb", "-"), ("dsire", ped.get("dam_sire"), "deb", "-"),
                            ("trainer", prof.get("調教師（所属）_id"), "deb", "-"), ("breeder", prof.get("生産者"), "deb", "-"), ("jockey", r.get("jockey_id"), "deb", "-")):
                    if key[1]:
                        S[key][0] += w; S[key][1] += p
        feats = []; odds = []; win = -1
        for i, (h, r) in enumerate(lst):
            ped = h["ped"]; prof = h.get("profile") or {}; sur = r["surface"]
            f = [
                lae(*S[("sire", ped["sire"], "deb", "-")]),          # 父の新馬戦の傾向
                lae(*S[("sire", ped["sire"], "deb", sur)]),          # 父×芝ダの新馬戦の傾向
                lae(*S[("sire", ped["sire"], "young", sur)]),        # 父×芝ダ×若い時期（~38か月）の全出走
                lae(*S[("dsire", ped.get("dam_sire"), "deb", "-")]), # 母の父の新馬戦の傾向
                lae(*S[("dsire", ped.get("dam_sire"), "all", sur)]), # 母の父×芝ダの全出走
                lae(*S[("dam", ped.get("dam"), "all", "-")]),        # 母の他の産駒の全出走
                lae(*S[("trainer", prof.get("調教師（所属）_id"), "deb", "-")]),   # 比較用（血統以外）：調教師
                lae(*S[("breeder", prof.get("生産者"), "deb", "-")]),               # 比較用：生産者
                lae(*S[("jockey", r.get("jockey_id"), "deb", "-")]),                # 比較用：騎手
            ]
            feats.append(f); odds.append(r["odds"])
            if r.get("finish") == 1:
                win = i
        p = np.array([0.8 / o for o in odds]); p = p / p.sum()
        rows.append((d, code, np.array(feats), np.log(p), win))
    return rows


NAMES = ["父:新馬戦の傾向", "父×芝ダ:新馬戦の傾向", "父×芝ダ:若い時期の全出走", "母の父:新馬戦の傾向", "母の父×芝ダ:全出走", "母の他の産駒:全出走", "(比較)調教師:新馬戦", "(比較)生産者:新馬戦", "(比較)騎手:新馬戦"]


def nll(theta, rows, cols, ridge=0.0):
    a = theta[0]; b = theta[1:]
    tot = 0.0; g = np.zeros_like(theta)
    for d, c, X, lo, w in rows:
        Xs = X[:, cols] if cols else np.zeros((len(lo), 0))
        s = a * lo + Xs @ b
        s = s - s.max(); e = np.exp(s); z = e.sum(); pr = e / z
        tot -= s[w] - math.log(z)
        gm = np.concatenate([[lo[w] - pr @ lo], (Xs[w] - pr @ Xs)]) if len(b) else np.array([lo[w] - pr @ lo])
        g -= gm
    tot += ridge * float(b @ b) if len(b) else 0
    if len(b): g[1:] += 2 * ridge * b
    return tot, g


def fit(rows, cols, ridge=0.0):
    th0 = np.concatenate([[1.0], np.zeros(len(cols))])
    r = minimize(lambda t: nll(t, rows, cols, ridge), th0, jac=True, method="BFGS")
    return r.x


def ll(theta, rows, cols):
    return nll(theta, rows, cols)[0] / len(rows)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--split", default="2025-01-01"); ap.add_argument("--out", default="debut_model_result.json")
    a = ap.parse_args()
    hs = load_horses(a.data); drs = debut_races(hs)
    rows = build(hs, drs)
    rows = [r for r in rows if r[0] >= "2022-01-01"]  # 特徴が育つまでの最初の1年は除く
    tr = [r for r in rows if r[0] < a.split]; te = [r for r in rows if r[0] >= a.split]
    print("train races", len(tr), "test races", len(te))
    res = {"train_races": len(tr), "test_races": len(te), "tests": []}
    base = fit(tr, []); print("odds-only a=", base[0], "train", ll(base, tr, []), "test", ll(base, te, []))
    res["odds_only"] = {"a": float(base[0]), "train": ll(base, tr, []), "test": ll(base, te, [])}
    sets = {"血統だけ(父3+母父2+母産駒1)": [0, 1, 2, 3, 4, 5], "父だけ": [0, 1, 2], "全部": list(range(9)), "調教師・生産者・騎手だけ(比較)": [6, 7, 8]}
    for nm, cols in sets.items():
        th = fit(tr, cols, ridge=1.0); t_te = ll(th, te, cols); t_b = ll(base, te, [])
        # 対応のあるブートストラップ（レース単位）で差の信頼区間
        diffs = []
        for d, c, X, lo, w in te:
            pass
        per_b = np.array([nll(base, [r], [])[0] for r in te]); per_f = np.array([nll(th, [r], cols)[0] for r in te])
        dd = per_b - per_f
        rng = np.random.default_rng(0); bs = [dd[rng.integers(0, len(dd), len(dd))].mean() for _ in range(2000)]
        print(nm, "coef", {NAMES[c]: round(float(x), 3) for c, x in zip(cols, th[1:])}, "a", round(float(th[0]), 3))
        print("   test ll odds-only %.4f  +feat %.4f  改善 %.4f  95%%[%.4f, %.4f]" % (t_b, t_te, dd.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)))
        res["tests"].append({"set": nm, "coef": {NAMES[c]: float(x) for c, x in zip(cols, th[1:])}, "a": float(th[0]), "test_odds_only": t_b, "test_with": t_te, "gain": float(dd.mean()), "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]})
    # 全期間で各特徴を1つずつ足したときの尤度比（係数の向きと有意性）
    allr = rows
    b0 = fit(allr, [])
    print("全期間・1つずつ追加:")
    res["single"] = []
    for c in range(9):
        th = fit(allr, [c], ridge=0.0); lr = 2 * (nll(b0, allr, [])[0] - nll(th, allr, [c])[0])
        print("  %-28s b=%.3f  LR=%.2f" % (NAMES[c], th[1], lr)); res["single"].append({"feature": NAMES[c], "b": float(th[1]), "LR": float(lr)})
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
