"""仕組みページ用：予想の確率に効く各要素の強さ（標準偏差1つ分で勝つ確率が何倍になるか）を公開用JSONにする。
入力：sim_v2/step1_factor_coef.json（step1_fit.py の結果）。距離帯の補正は検証値（係数0.7・標準偏差約0.08）。
出力：docs/data/step1_factor_strength_v1.json。使い方：python3 -m sim_v2.build_strength_public"""
import json, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
c = json.loads((ROOT / "sim_v2/step1_factor_coef.json").read_text(encoding="utf-8"))
items = [{"label": i["label"], "mult_per_sd": i["mult_per_sd"], "added": i["added"]} for i in c["items"] if i["name"] not in ("T1", "K2")]
add = [
    {"label": "上がり順位のよさ", "key": "kick", "mult_per_sd": c["K2"]["mult_per_sd"], "cap_min": 0.65, "cap_max": 1.53, "what": "直近3走の上がり3Fが、そのレースの出走馬の中で何番目だったか", "gain": "+0.0030（95%幅 +0.0006〜+0.0053）"},
    {"label": "調教師の強さ", "key": "trainer", "mult_per_sd": c["T1"]["mult_per_sd"], "cap_min": 0.80, "cap_max": 1.25, "what": "その調教師の過去のJRA成績（3着内率−全体）。レースによらない絶対的な強さ", "gain": "+0.0044（95%幅 +0.0015〜+0.0071）"},
    {"label": "この距離での過去の成績", "key": "dist", "mult_per_sd": round(math.exp(0.7 * 0.08), 3), "cap_min": 0.90, "cap_max": 1.11, "what": "同じ距離帯（200mごと）での3着内率と、全体の3着内率の差", "gain": "+0.0016（95%幅 +0.0005〜+0.0027）"},
]
out = {"version": 1, "races_train": c["races_train"], "races_test": c["races_test"], "existing": sorted(items, key=lambda x: -abs(math.log(x["mult_per_sd"]))), "added": add, "overlap": c.get("overlap")}
(ROOT / "docs/data/step1_factor_strength_v1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(items), "既存", len(add), "追加")
