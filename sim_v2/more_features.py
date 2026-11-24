"""3つの追加検証（研究のみ・予想には使わない）。土台・分け方・評価は distance_no_odds / pace_lap_features と同じ。
 P：前走のペースで補正した内容（脚質が展開で得をしたか損をしたか）
 K：位置取りの上がり方（最後のコーナーからの順位変化、上がり順位、上がり順位が着順より良かったか）
 T：調教師・騎手×調教師の組み合わせ・調教師の休み明け成績・騎手の乗り替わり
先に決めた判断ルール：後半の改善の95%幅が0より上＋前半の係数と後半だけで決め直した係数の向きが同じ＋後半を前後に分けて両方で正。
使い方：python3 -m sim_v2.more_features --pages <非公開 data_v2/race_pages> --data <非公開 data_v2> --races R.json --out out.json"""
from __future__ import annotations
import argparse, bisect, glob, json, re, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim_v2.strength_model import FEATS, feats
from sim_v2.distance_no_odds import newton, per_race_ll
from sire_db_v1.debut_common import load_horses

SPLIT = "2024-07-01"
FRONT, CLOSER = 0.30, 0.60
NAMES = ["P1 展開で得した度合い（直近3走平均）", "P2 展開の得失×着順のよさ", "K1 最後のコーナーからの順位上昇", "K2 上がり順位のよさ", "K3 上がり順位が着順より良い幅",
         "T1 調教師の3着内率（全体との差）", "T2 騎手×調教師の組み合わせの上乗せ", "T3 調教師の休み明け(90日以上)の上乗せ", "T4 騎手の乗り替わり"]
FAM = {"P（前走のペース補正）": [0, 1], "K（位置取りの上がり方）": [2, 3, 4], "T（調教師・組み合わせ・乗り替わり）": [5, 6, 7, 8]}


def extract_trainers(pages_dir):
    out = {}
    for f in sorted(glob.glob(str(Path(pages_dir) / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line); r = (d.get("pages") or {}).get("result") or {}
            m = {}
            for t in r.get("tables") or []:
                if t and t[0] and t[0][0] == "着順":
                    for row in t[1:]:
                        h = tr = None
                        for c in row:
                            a = re.search(r"horse/(\d+)/", c or ""); b = re.search(r"trainer/(\d+)/", c or "")
                            if a: h = a.group(1)
                            if b: tr = b.group(1)
                        if h and tr: m[h] = tr
            if m: out[d["code"]] = m
    return out


def pace_info(laps):
    """レースごとの（前3F−後3F）。正＝前半が遅い（スロー）。距離・芝ダごとに標準化。"""
    raw = {}
    for c, v in laps.items():
        s = v["sec"]
        if len(s) >= 6: raw[c] = sum(s[:3]) - sum(s[-3:])
    return raw


def build(hs, laps, trainers):
    pace_raw = pace_info(laps)
    # 距離×芝ダごとの標準化
    grp = defaultdict(list)
    runs = []
    for h in hs.values():
        hist = sorted([r for r in (h.get("history") or []) if r.get("date") and isinstance(r.get("finish"), int) and r.get("heads") and r.get("code") in trainers], key=lambda r: r["date"])
        prev = None
        for r in hist:
            tr = trainers[r["code"]].get(h["id"])
            if tr is None: prev = r; continue
            ds = (r["date"][:10] and None)
            runs.append((r["date"], h["id"], r, tr, prev))
            if r["code"] in pace_raw: grp[(r["surface"], r["dist"])].append(pace_raw[r["code"]])
            prev = r
    stat = {k: (float(np.mean(v)), float(np.std(v)) + 1e-6) for k, v in grp.items() if len(v) >= 20}
    runs.sort(key=lambda x: x[0])
    # 時系列順に、調教師・組み合わせの統計を更新しながら特徴を作る
    from datetime import date as D
    cnt = {"t": defaultdict(lambda: [0, 0]), "jt": defaultdict(lambda: [0, 0]), "tl": defaultdict(lambda: [0, 0])}
    allt = [0, 0]
    out = {}
    i = 0
    while i < len(runs):
        j = i
        while j < len(runs) and runs[j][0] == runs[i][0]: j += 1
        batch = runs[i:j]
        base = allt[0] / allt[1] if allt[1] > 1000 else 0.2
        for date, hid, r, tr, prev in batch:
            jk = r.get("jockey_id")
            n_t = cnt["t"][tr]; rate_t = (n_t[0] + 30 * base) / (n_t[1] + 30)
            t1 = rate_t - base
            nc = cnt["jt"][(jk, tr)]; t2 = (nc[0] + 15 * rate_t) / (nc[1] + 15) - rate_t
            lay = 0
            if prev is not None:
                lay = (D.fromisoformat(r["date"]) - D.fromisoformat(prev["date"])).days
            t3 = 0.0
            if lay >= 90:
                nl = cnt["tl"][tr]; t3 = (nl[0] + 20 * rate_t) / (nl[1] + 20) - rate_t
            t4 = 1.0 if (prev is not None and prev.get("jockey_id") and jk and prev.get("jockey_id") != jk) else 0.0
            out[(hid, r["code"])] = [t1, t2, t3, t4]
        for date, hid, r, tr, prev in batch:
            top = 1 if r["finish"] <= 3 else 0; jk = r.get("jockey_id")
            allt[0] += top; allt[1] += 1
            cnt["t"][tr][0] += top; cnt["t"][tr][1] += 1
            cnt["jt"][(jk, tr)][0] += top; cnt["jt"][(jk, tr)][1] += 1
            if prev is not None and (D.fromisoformat(r["date"]) - D.fromisoformat(prev["date"])).days >= 90:
                cnt["tl"][tr][0] += top; cnt["tl"][tr][1] += 1
        i = j
    trfeat = out
    # 走ごとの P・K 値
    per = defaultdict(list)
    for date, hid, r, tr, prev in runs:
        c = r["code"]; H = r["heads"]
        try: ps = [int(x) for x in str(r.get("passing") or "").split("-") if x.strip().isdigit()]
        except Exception: ps = []
        if not ps or H < 5: continue
        fin = (r["finish"] - 1) / max(1, H - 1)
        style = 1.0 if ps[0] / H <= FRONT else (-1.0 if ps[0] / H >= CLOSER else 0.0)
        z = 0.0
        if c in pace_raw and (r["surface"], r["dist"]) in stat:
            mu, sd = stat[(r["surface"], r["dist"])]; z = (pace_raw[c] - mu) / sd
        benefit = z * style
        h1 = ((ps[-1] - 1) / max(1, H - 1)) - fin
        h2 = h3 = 0.0
        l3 = laps.get(c, {}).get("l3")
        if l3 and r.get("last3f"):
            rank = sum(1 for x in l3 if x < r["last3f"]) / len(l3)
            h2 = 1 - rank; h3 = h2 - (1 - fin)
        per[hid].append((date, c, [benefit, benefit * (1 - fin), h1, h2, h3]))
    return per, trfeat


def window(per, hid, date, k=3, prior=1.0):
    seq = per.get(hid)
    if not seq: return [0.0] * 5
    past = [x for x in seq if x[0] < date][-k:]
    if not past: return [0.0] * 5
    return [float(v) for v in np.sum([x[2] for x in past], axis=0) / (len(past) + prior)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", required=True); ap.add_argument("--data", required=True); ap.add_argument("--races", required=True); ap.add_argument("--out")
    ap.add_argument("--laps-cache", default="/tmp/dnw/laps.json"); ap.add_argument("--trainers-cache", default="/tmp/dnw/trainers.json")
    a = ap.parse_args()
    laps = json.loads(Path(a.laps_cache).read_text(encoding="utf-8"))
    tp = Path(a.trainers_cache)
    if tp.exists(): trainers = json.loads(tp.read_text(encoding="utf-8"))
    else:
        trainers = extract_trainers(a.pages); tp.write_text(json.dumps(trainers), encoding="utf-8")
    print("調教師の取れたレース", len(trainers), file=sys.stderr)
    hs = load_horses(a.data)
    per, trfeat = build(hs, laps, trainers)
    races = json.loads(Path(a.races).read_text(encoding="utf-8"))["races"]
    data = []
    for r in races:
        w = [i for i, x in enumerate(r["runners"]) if x["finish"] == 1]
        if len(w) != 1: continue
        E = []
        for x in r["runners"]:
            pk = window(per, x.get("hid"), r["date"]); tf = trfeat.get((x.get("hid"), r["code"]), [0.0, 0.0, 0.0, 0.0])
            E.append(pk + tf)
        data.append((r["date"], np.hstack([feats(r), np.array(E, float)]), w[0]))
    tr = [(X, w) for d, X, w in data if d < SPLIT]; te = [(X, w) for d, X, w in data if d >= SPLIT]; te_date = [d for d, X, w in data if d >= SPLIT]
    print(f"レース 前半{len(tr)} 後半{len(te)}", file=sys.stderr)
    nf = len(FEATS); b1 = list(range(nf)); cols = [nf + k for k in range(9)]
    models = {"B1": b1}
    for k in range(9): models[NAMES[k]] = b1 + [cols[k]]
    for fam, ix in FAM.items(): models["家族まとめ：" + fam] = b1 + [cols[i] for i in ix]
    models["全9項目"] = b1 + cols
    fitted = {k: newton(tr, c) for k, c in models.items()}
    ll = {k: per_race_ll(te, c, fitted[k]) for k, c in models.items()}
    rng = np.random.default_rng(13); n = len(te)
    def ci(d): return [float(np.percentile([d[rng.integers(0, n, n)].mean() for _ in range(3000)], q)) for q in (2.5, 97.5)]
    mid = sorted(set(te_date))[len(set(te_date)) // 2]; sel = np.array([d < mid for d in te_date])
    res = {"races": {"前半": len(tr), "後半": len(te)}, "test_ll_B1": float(ll["B1"].mean()), "gain": {}}
    allm = b1 + cols; coef_test = newton(te, allm)[2]
    single_test = {}
    for k in range(9): single_test[NAMES[k]] = float(newton(te, b1 + [cols[k]])[2][-1])
    for k, v in ll.items():
        if k == "B1": continue
        d = ll["B1"] - v
        e = {"gain": float(d.mean()), "ci95": ci(d), "前の半分": float(d[sel].mean()), "後の半分": float(d[~sel].mean())}
        if k in single_test: e["coef_train"] = round(float(fitted[k][2][-1]), 4); e["coef_test_refit"] = round(single_test[k], 4); e["same_sign"] = (e["coef_train"] > 0) == (e["coef_test_refit"] > 0)
        res["gain"][k] = e
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.out: Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
