"""STEP1 に使う要素の強さ（係数）を決める（研究・仕組みページ用）。
土台 B1（既存の能力モデルの特徴・オッズなし）に 調教師T1・上がり順位K2・距離帯apt を足して条件付きロジットを当てはめ、
各要素が「標準偏差1つ分」で勝つ確率を何倍にするかを、既存の要素と同じ物差しで出す。
出力：sim_v2/step1_factor_coef.json
使い方：python3 -m sim_v2.step1_fit --pages <非公開 data_v2/race_pages> --data <非公開 data_v2> --races R.json
（R.json は build_races --with-hid の出力。laps/trainers のキャッシュは more_features と共通）"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim_v2.strength_model import FEATS, feats
from sim_v2.distance_no_odds import newton, per_race_ll
from sim_v2.more_features import build, window, extract_trainers, SPLIT
from sire_db_v1.debut_common import load_horses

ROOT = Path(__file__).resolve().parents[1]
JP = {"speed": "走破タイムの指数", "peak": "過去最高の指数", "kick": "上がりの指数", "early": "序盤の位置取り", "wet_power": "道悪の適性",
      "stamina_fit": "距離への適性（スタミナ）", "debut": "初出走", "log_runs": "出走数", "finpct3": "近3走の着順", "margin3": "近3走の着差",
      "lninki3": "近3走の人気", "level_diff": "前走からのクラス差", "log_days": "前走からの間隔", "carried_diff": "斤量（平均との差）",
      "draw": "馬番（内→外）", "age_diff": "年齢（平均との差）", "sd": "能力のばらつき", "jockey": "騎手", "dist_up": "距離延長", "dist_down": "距離短縮",
      "surf_switch": "芝ダートの替わり", "bw_diff_abs": "馬体重の増減幅", "bw_diff": "馬体重の増減", "sire_surf": "父の芝ダート傾向",
      "sire_debut_x_debut": "父の初出走成績×初出走", "sire_surf_x_young": "父の芝ダート傾向×若駒"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", required=True); ap.add_argument("--data", required=True); ap.add_argument("--races", required=True)
    ap.add_argument("--laps-cache", default="/tmp/dnw/laps.json"); ap.add_argument("--trainers-cache", default="/tmp/dnw/trainers.json")
    ap.add_argument("--out", default=str(ROOT / "sim_v2/step1_factor_coef.json"))
    a = ap.parse_args()
    laps = json.loads(Path(a.laps_cache).read_text(encoding="utf-8"))
    tp = Path(a.trainers_cache)
    trainers = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else extract_trainers(a.pages)
    hs = load_horses(a.data)
    per, trfeat = build(hs, laps, trainers)
    races = json.loads(Path(a.races).read_text(encoding="utf-8"))["races"]
    data = []
    for r in races:
        w = [i for i, x in enumerate(r["runners"]) if x["finish"] == 1]
        if len(w) != 1: continue
        E = []
        for x in r["runners"]:
            pk = window(per, x.get("hid"), r["date"]); tf = trfeat.get((x.get("hid"), r["code"]), [0.0] * 4)
            E.append([tf[0], pk[3]])        # T1, K2
        data.append((r["date"], np.hstack([feats(r), np.array(E, float)]), w[0]))
    nf = len(FEATS); b1 = list(range(nf)); t1, k2 = nf, nf + 1
    tr = [(X, w) for d, X, w in data if d < SPLIT]; te = [(X, w) for d, X, w in data if d >= SPLIT]
    out = {"races_train": len(tr), "races_test": len(te), "split": SPLIT}
    # ① 前半で決めた係数（検証時の係数）
    mu, sd, b = newton(tr, b1 + [t1, k2])
    out["train_fit"] = {"T1": round(float(b[-2] / sd[-2]), 4), "K2": round(float(b[-1] / sd[-1]), 4)}
    # ② 全期間で決め直した最終の係数（予想用）。T1・K2・既存の全要素を一緒に当てはめる
    allr = tr + te
    mu, sd, b = newton(allr, b1 + [t1, k2])
    names = FEATS + ["T1", "K2"]
    items = []
    for i, n in enumerate(names):
        per_sd = float(np.exp(b[i]))      # 標準化済みなので、標準偏差1つ分で勝つ確率が何倍になるか
        items.append({"name": n, "label": JP.get(n, {"T1": "調教師の強さ", "K2": "上がり順位のよさ"}.get(n, n)), "coef_per_unit": round(float(b[i] / sd[i]), 4),
                      "sd": round(float(sd[i]), 4), "mean": round(float(mu[i]), 4), "mult_per_sd": round(per_sd, 3), "added": n in ("T1", "K2")})
    out["items"] = items
    out["T1"] = {k: v for k, v in items[-2].items()}
    out["K2"] = {k: v for k, v in items[-1].items()}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for it in sorted(items, key=lambda x: -abs(np.log(x["mult_per_sd"]))):
        print(f'{it["label"]:<16} ×{it["mult_per_sd"]:.3f}/SD  sd={it["sd"]}  {"★追加" if it["added"] else ""}')
    print("train_fit", out["train_fit"])


if __name__ == "__main__":
    main()
