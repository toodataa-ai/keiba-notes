"""出走馬の「強さ」を、そのレースより前の情報だけから1つの数字にまとめる（条件付きロジット）。
学習期間で係数を決め、検証期間で当たり具合（ログ損失）をオッズと比べる。
今回のオッズは使わない（--with-odds のときだけ、オッズに上乗せの情報があるかを調べる）。"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np

FEATS = ["speed", "peak", "kick", "early", "wet_power", "stamina_fit", "debut", "log_runs", "finpct3", "margin3", "lninki3",
         "level_diff", "log_days", "carried_diff", "draw", "age_diff", "sd", "jockey", "dist_up", "dist_down", "surf_switch", "bw_diff_abs", "bw_diff", "sire_surf", "sire_debut_x_debut", "sire_surf_x_young"]


def feats(race):
    rs = race["runners"]; H = len(rs)
    car = [x["carried"] or 56 for x in rs]; cm = sum(car) / H
    ages = [x["age_m"] for x in rs if x.get("age_m") is not None]; am = sum(ages) / len(ages) if ages else 0
    wet = 1.0 if race["going"] in ("重", "不良") else (0.5 if race["going"] == "稍重" else 0.0)
    lvl = race.get("level")
    X = []
    for x in rs:
        deb = 1.0 if (x.get("runs_total") or 0) == 0 else 0.0
        X.append([
            x["speed"], x["peak"] if x.get("peak") is not None else x["speed"], x["kick"], x["early"],
            x["power"] * wet, x["stamina"] * (race["dist"] - 1800) / 1000.0, deb, math.log1p(x.get("runs_total") or 0),
            x["finpct3"] if x.get("finpct3") is not None else 0.5, x["margin3"] if x.get("margin3") is not None else 1.5,
            x["lninki3"] if x.get("lninki3") is not None else math.log(max(1, H / 2)),
            ((x["level_last"] - lvl) if (x.get("level_last") is not None and lvl is not None) else 0.0),
            math.log1p(x["days_since"]) if x.get("days_since") is not None else 0.0,
            (x["carried"] or cm) - cm, (x["no"] - 1) / max(1, H - 1), ((x["age_m"] or am) - am) / 12.0, x["sd"],
            x.get("jockey", 0.0), max(0.0, x.get("dist_change", 0.0)), max(0.0, -x.get("dist_change", 0.0)), x.get("surf_switch", 0),
            min(20, abs(x.get("bw_diff") or 0)) / 10.0, max(-20, min(20, x.get("bw_diff") or 0)) / 10.0,
            x.get("sire_surf", 0.0), x.get("sire_debut", 0.0) * deb, x.get("sire_surf", 0.0) * (1.0 if (x.get("runs_total") or 0) <= 3 else 0.0)])
    return np.array(X, dtype=float)


def fit(races, l2=0.02, iters=300):
    data = [(feats(r), next(i for i, x in enumerate(r["runners"]) if x["finish"] == 1)) for r in races if any(x["finish"] == 1 for x in r["runners"])]
    allX = np.vstack([d[0] for d in data]); mu = allX.mean(0); sdv = allX.std(0) + 1e-9
    data = [((X - mu) / sdv, w) for X, w in data]
    b = np.zeros(allX.shape[1])
    for it in range(iters):
        g = np.zeros_like(b); Hm = np.zeros((len(b), len(b))); L = 0
        for X, w in data:
            z = X @ b; z -= z.max(); p = np.exp(z); p /= p.sum()
            L -= math.log(p[w] + 1e-12)
            g += X[w] - p @ X
            Xc = X - p @ X
            Hm += (Xc * p[:, None]).T @ Xc
        g -= l2 * len(data) * b * 0.001; Hm += np.eye(len(b)) * l2 * len(data) * 0.001
        step = np.linalg.solve(Hm, g); b += step
        if np.abs(step).max() < 1e-6:
            break
    return {"feats": FEATS, "mu": mu.tolist(), "sd": sdv.tolist(), "beta": b.tolist(), "train_ll": L / len(data), "n": len(data)}


def score(model, race):
    X = (feats(race) - np.array(model["mu"])) / np.array(model["sd"])
    return X @ np.array(model["beta"])


def ll(races, probf):
    L = n = 0
    for r in races:
        w = [i for i, x in enumerate(r["runners"]) if x["finish"] == 1]
        if not w:
            continue
        p = probf(r)
        if p is None:
            continue
        L -= math.log(max(p[w[0]], 1e-9)); n += 1
    return L / n, n


def softmax(z):
    z = np.array(z, float); z -= z.max(); e = np.exp(z); return e / e.sum()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--races", required=True)
    ap.add_argument("--split", default="2026-03-01")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    races = json.loads(Path(a.races).read_text(encoding="utf-8"))["races"]
    tr = [r for r in races if r["date"] < a.split]; te = [r for r in races if r["date"] >= a.split]
    m = fit(tr)
    oddsp = lambda r: (lambda v: v / v.sum())(np.array([1 / x["odds"] for x in r["runners"]])) if all(x["odds"] for x in r["runners"]) else None
    res = {"train_races": len(tr), "test_races": len(te),
           "test_ll_model": ll(te, lambda r: softmax(score(m, r)))[0],
           "test_ll_odds": ll(te, oddsp)[0], "test_ll_uniform": ll(te, lambda r: np.ones(len(r["runners"])) / len(r["runners"]))[0]}
    # オッズに上乗せの情報があるか：log(オッズ確率) と モデルの強さ を混ぜて、検証期間で
    best = None
    for wgt in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
        def mix(r, wgt=wgt):
            o = oddsp(r)
            if o is None: return None
            return softmax(np.log(o) * 1.0 + wgt * score(m, r))
        v = ll(te, mix)[0]
        res[f"test_ll_odds_plus_model_{wgt}"] = v
        if best is None or v < best[1]: best = (wgt, v)
    res["best_mix"] = best
    m.update({"eval": res})
    Path(a.out).write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print(dict(zip(FEATS, [round(x, 3) for x in m["beta"]])))


if __name__ == "__main__":
    main()
