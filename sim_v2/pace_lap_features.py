"""ラップ（200mごとの区間タイム）を使った特徴の検証（研究のみ・予想には使わない）。
仮説（ユーザー 2026-11-25）：『淀みない流れの中、逃げ・先行で最後も速い脚を使った馬は強い』。
段階：①race_pages（非公開）から全レースのラップと上がり3Fの分布を取り出す ②馬ごとの過去の走りを数値にして、
レースの日より前の直近5走で平均 ③オッズを使わない能力モデル（strength_model と同じ特徴）に足して、後半の対数損失を比べる。
前半（〜2024-06）で係数を決め、後半（2024-07〜）で評価。差の95%幅はレース単位のやり直し計算。
使い方：python3 -m sim_v2.pace_lap_features --pages <非公開 data_v2/race_pages> --data <非公開 data_v2> --races R.json --out out.json"""
from __future__ import annotations
import argparse, glob, json, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim_v2.strength_model import FEATS
from sim_v2.distance_no_odds import newton, per_race_ll, DIST_COLS
from sire_db_v1.debut_common import load_horses

SPLIT = "2024-07-01"
FLAT_MAX_LOOSEN = 0.3   # 『淀みない』：序盤の1ハロン以降、最後の600mより前で、前の1ハロンより0.3秒を超えて遅くなった所が無い
FRONT_PCT = 0.30        # 逃げ・先行：最初の通過順位 ÷ 頭数 ≤ 0.30
LAST_GAP = 0.3          # 最後も速い：上がり3Fがそのレースの最速から0.3秒以内
NEW = ["淀みない流れで先行し上がりも速かった（回数）", "先行し上がりも速かった（流れを問わない・回数）", "先行して上がりが平均より速かった幅（淀みない流れのみ）", "最後の1ハロンが加速したレースで先行して上がりも速かった（回数）"]


def parse_laps(tables):
    heads, vals = [], []
    for t in tables:
        if t and t[0] and re.fullmatch(r"\d+m", t[0][0] or ""):
            for i in range(0, len(t) - 1, 2):
                heads += [h for h in t[i]]; vals += [v for v in t[i + 1]]
    cum, sec = [], []
    for h, v in zip(heads, vals):
        m = re.fullmatch(r"(?:(\d+):)?([\d.]+)\((?:(\d+):)?([\d.]+)\)", v or "")
        if not (h and m): continue
        sec.append(float(m.group(4)) + (60 * int(m.group(3)) if m.group(3) else 0))
    return sec


def last3f_list(tables):
    out = []
    for t in tables:
        if t and t[0] and t[0][0] == "着順":
            for row in t[1:]:
                for c in row:
                    m = re.fullmatch(r"(?:\d+-?)+ (\d\d\.\d)", (c or "").strip())
                    if m: out.append(float(m.group(1))); break
    return out


def extract(pages_dir):
    res = {}
    for f in sorted(glob.glob(str(Path(pages_dir) / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line); r = (d.get("pages") or {}).get("result") or {}
            tb = r.get("tables") or []
            sec = parse_laps(tb); l3 = last3f_list(tb)
            if len(sec) < 5 or len(l3) < 5: continue
            res[d["code"]] = {"sec": sec, "l3": l3}
    return res


def race_flags(info):
    s = info["sec"]; n = len(s)
    mid = range(2, n - 3)       # 序盤の最初の1つの後〜最後の600mより前
    loosen = max([s[i] - s[i - 1] for i in mid] or [0.0])
    return {"flat": 1.0 if (n >= 6 and loosen <= FLAT_MAX_LOOSEN) else 0.0, "acc_end": 1.0 if s[-1] <= s[-2] else 0.0,
            "l3min": min(info["l3"]), "l3med": float(np.median(info["l3"]))}


def run_scores(hs, laps):
    """{(hid, code): [S1,S2,S3,S4]} と 各馬の時系列"""
    flags = {c: race_flags(v) for c, v in laps.items()}
    per = {}
    for h in hs.values():
        hist = [r for r in (h.get("history") or []) if r.get("code") in flags and r.get("date") and r.get("last3f") and r.get("heads") and r.get("passing")]
        hist.sort(key=lambda r: r["date"])
        seq = []
        for r in hist:
            fl = flags[r["code"]]
            try: p0 = int(str(r["passing"]).split("-")[0])
            except Exception: continue
            front = 1.0 if p0 / r["heads"] <= FRONT_PCT else 0.0
            fast = 1.0 if r["last3f"] - fl["l3min"] <= LAST_GAP else 0.0
            s1 = front * fast * fl["flat"]; s2 = front * fast
            s3 = front * fl["flat"] * max(-1.5, min(1.5, fl["l3med"] - r["last3f"]))
            s4 = front * fast * fl["acc_end"]
            seq.append((r["date"], r["code"], [s1, s2, s3, s4]))
        per[h["id"]] = seq
    return per


def window_feature(per, hid, date, code, k=5, prior=2.0):
    """そのレースの日より前の直近k走の平均（少ない走数は0に近づける）。"""
    seq = per.get(hid)
    if not seq: return [0.0] * 4
    past = [x for x in seq if x[0] < date][-k:]
    if not past: return [0.0] * 4
    sm = np.sum([x[2] for x in past], axis=0)
    return [float(v) for v in sm / (len(past) + prior)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", required=True); ap.add_argument("--data", required=True); ap.add_argument("--races", required=True); ap.add_argument("--out")
    ap.add_argument("--laps-cache", default="/tmp/dnw/laps.json")
    a = ap.parse_args()
    cp = Path(a.laps_cache)
    if cp.exists(): laps = json.loads(cp.read_text(encoding="utf-8"))
    else:
        laps = extract(a.pages); cp.write_text(json.dumps(laps), encoding="utf-8")
    print("ラップの取れたレース", len(laps), file=sys.stderr)
    hs = load_horses(a.data)
    per = run_scores(hs, laps)
    from sim_v2.strength_model import feats
    races = json.loads(Path(a.races).read_text(encoding="utf-8"))["races"]
    data = []
    for r in races:
        w = [i for i, x in enumerate(r["runners"]) if x["finish"] == 1]
        if len(w) != 1: continue
        E = np.array([window_feature(per, x.get("hid"), r["date"], r["code"]) for x in r["runners"]], float)
        data.append((r["date"], np.hstack([feats(r), E]), w[0]))
    tr = [(X, w) for d, X, w in data if d < SPLIT]; te = [(X, w) for d, X, w in data if d >= SPLIT]
    te_date = [d for d, X, w in data if d >= SPLIT]
    print(f"レース 前半{len(tr)} 後半{len(te)}", file=sys.stderr)
    nf = len(FEATS); b1 = list(range(nf)); new = [nf + k for k in range(4)]
    models = {"B1": b1, "B1+全4項目": b1 + new}
    for k in range(4): models[f"B1+{NEW[k]}"] = b1 + [new[k]]
    fitted = {k: newton(tr, c) for k, c in models.items()}
    ll = {k: per_race_ll(te, c, fitted[k]) for k, c in models.items()}
    rng = np.random.default_rng(11); n = len(te)
    def ci(d):
        bs = [d[rng.integers(0, n, n)].mean() for _ in range(3000)]
        return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    res = {"races": {"前半": len(tr), "後半": len(te)}, "laps_races": len(laps), "test_ll_B1": float(ll["B1"].mean()), "gain": {}}
    for k in models:
        if k == "B1": continue
        d = ll["B1"] - ll[k]; res["gain"][k] = {"gain": float(d.mean()), "ci95": ci(d)}
    res["coef_train"] = {NEW[i]: round(float(fitted["B1+全4項目"][2][nf + i]), 4) for i in range(4)}
    res["coef_test_refit"] = {NEW[i]: round(float(newton(te, b1 + new)[2][nf + i]), 4) for i in range(4)}
    mid = sorted(set(te_date))[len(set(te_date)) // 2]; sel = np.array([d < mid for d in te_date]); d = ll["B1"] - ll["B1+全4項目"]
    res["all4_by_half"] = {"後半の前の半分": float(d[sel].mean()), "後半の後の半分": float(d[~sel].mean())}
    # 単純な見え方：先行し上がりも速かった走の割合と、次走の勝ち率（参考）
    flat_rate = float(np.mean([v["flat"] for v in map(race_flags, laps.values())]))
    res["flat_race_rate"] = round(flat_rate, 3)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.out: Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
