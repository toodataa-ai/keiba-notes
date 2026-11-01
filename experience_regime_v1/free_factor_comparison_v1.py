#!/usr/bin/env python3
"""Reproduce evidence-quality A/B at a frozen prereace source boundary.

This is not outcome validation: records were captured before starts but the
comparison is computed later. It never updates forecasts, odds or model weights.
"""
from __future__ import annotations
import argparse
import html
import json
from datetime import date
from pathlib import Path

from experience_regime_v1.free_shared_factor_quality_v1 import (
    undercard_factor_quality, formal_factor_quality, compare_quality)
from experience_regime_v1.step1_factors_evidence_v1 import first_git_proof

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experience_regime_v1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit_and_compare(week, day):
    plan = read(BASE / "collection" / week / "sample_plan.json")
    if plan["week_id"] != week:
        raise ValueError("wrong_frozen_week")
    sample = [r for r in plan["selected_races"] if r["date"] == day]
    if not sample:
        raise ValueError("no_fixed_sampled_races")
    formal, shadow = [], []
    proof_records = {}
    for r in sample:
        rid = r["race_id"]
        deadline = r["start_at"]
        from datetime import datetime
        start = datetime.fromisoformat(deadline)
        if r["sample_origin"] == "official_prediction":
            path = BASE / "step1_frozen" / week / (rid + ".json")
            proof_records[rid] = first_git_proof(path, start)
            data = read(path)
            formal.append(formal_factor_quality(data))
        else:
            candidate_path = BASE / "research_step1_candidates" / week / (rid + ".json")
            fact_path = BASE / "factor_evidence" / week / (rid + ".json")
            proof_records[rid] = {
                "original_candidate":first_git_proof(candidate_path,start),
                "factors":first_git_proof(fact_path,start)}
            candidate, evidence = read(candidate_path), read(fact_path)
            shadow.append(undercard_factor_quality(candidate, evidence))
    out = compare_quality(formal, shadow)
    out["date"] = day
    out["week_id"] = week
    out["sample_plan"] = str((BASE / "collection" / week / "sample_plan.json").relative_to(ROOT))
    out["evidence_first_git_proofs"] = proof_records
    out["price_blind_record_only"] = True
    out["outcome_data_read"] = False
    out["full_nine_factor_grades_calibrated"] = False
    out["data_collection_cost_yen"] = 0
    out["independent_grade_improvement_claimed"] = False
    if len(formal)+len(shadow) != len(sample):
        raise ValueError("fixed_plan_scope_mismatch")
    return out


def render(report):
    columns = ["斤量", "展開", "馬場", "ローテ", "コース", "血統", "調教", "騎手", "基礎能力"]
    rows = "".join(
        "<tr><th>"+str(i)+" "+html.escape(label)+"</th>"
        "<td>"+str(report["coverage_by_factor"][str(i)]["observed_or_identity"])+"</td>"
        "<td>"+str(report["coverage_by_factor"][str(i)]["unavailable"])+"</td></tr>"
        for i,label in enumerate(columns,1))
    return """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>無料データの9項目監査・ステージング</title>
<style>body{font:15px/1.65 Meiryo,'Hiragino Kaku Gothic ProN',sans-serif;max-width:820px;margin:35px auto;padding:0 16px;color:#1d2939}
h1{font-size:1.65rem}h2{font-size:1.25rem}table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid #d0d5dd;padding:10px;text-align:left}
th{font-weight:600} .muted{color:#475467}.meta{background:#f2f4f7;padding:14px;border-radius:7px}
strong{color:#101828}</style></head><body>
<h1>①〜⑨ 無料データの取得・評価根拠比較</h1>
<p class="meta"><strong>ステージング検証用／公開馬券予想ではありません。</strong>
既存のJRA正式予想・研究予想の印、確率、買い目は変更していません。
これは発走前に保存された根拠を後から集計した監査で、新たな発走前予想や的中検証ではありません。</p>
<p>対象：正式メイン """ + str(report["formal_races"]) + """レース / """ + str(report["formal_horses"]) + """頭、
研究用 """ + str(report["undercard_races"]) + """レース / """ + str(report["undercard_horses"]) + """頭。</p>
<h2>研究対象の根拠取得数</h2>
<table><thead><tr><th>評価項目</th><th>根拠・属性あり</th><th>未取得</th></tr></thead><tbody>""" + rows + """</tbody></table>
<p class="muted">「根拠・属性あり」は評価グレードが校正済みであることを意味しません。
血統・騎手は主に名前のみ。調教時計は未取得です。</p>
<h2>正式予想の現状</h2>
<p>⑥血統：一律B、⑦調教：一律B−、⑧騎手：一律B。
現行のコードではデータ未観測時の固定値です。実測能力との混同を避けます。</p>
<h2>新旧比較の判定</h2>
<p><strong>データ取得の可視化は可能。予測精度・回収率の改善は未判定。</strong>
将来開催の発走前Shadowデータ、結果確定後の同一母集団比較、E0/E1/E2別のBrier・回収率・校正を必要とします。</p>
<p class="muted">無料データのみ。既存正式モデルへの昇格は承認制です。</p>
</body></html>
"""


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--week-id",required=True)
    p.add_argument("--date",required=True)
    p.add_argument("--outdir",required=True)
    args=p.parse_args()
    result=audit_and_compare(args.week_id,args.date)
    path=Path(args.outdir)
    path.mkdir(parents=True,exist_ok=True)
    (path/"e012-free-factor-compare.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (path/"e012-free-factor-compare.html").write_text(render(result),encoding="utf-8")
    print("E012_FREE_FACTOR_STAGING",result["undercard_races"],"races",
          result["undercard_horses"],"horses","unchanged",result["frozen_predictions_untouched"])


if __name__=="__main__":
    main()
