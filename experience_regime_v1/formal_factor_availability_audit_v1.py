#!/usr/bin/env python3
"""Evidence-availability audit for 9 JRA factors, comparing immutable formal and E012.

A filled grade is not evidence of an observed, calibrated factor.  This reads
the formal collector and immutable proof-referenced records but NEVER modifies
any prediction, existing evidence, bet, score, or source.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/jra-gather-live-v314.py"
WEEK = ROOT / "experience_regime_v1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inspect(week, day):
    source = SCRIPT.read_text(encoding="utf-8")
    # Require that this assessment is tied to the actual implementation,
    # rather than assuming unverified training/jockey/pedigree statistics.
    checks = {
        "pedigree_fixed_grade": "grades[5]='B' # pedigree compatibility not established",
        "workout_fixed_grade": "grades[6]='B-' # workout not independently observed",
        "jockey_fixed_grade": "grades[7]='B' # jockey course-adjusted statistics not independently observed",
        "workout_data_unavailable": "workout_data_status='unavailable'",
        "jockey_stats_unavailable": "jockey_course_stats_status='unavailable'",
        "grade_is_required": "factor_grades=grades",
    }
    missing = [name for name, marker in checks.items() if marker not in source]
    if missing:
        raise ValueError("JRA_formal_model_changed_reaudit_needed:" + ",".join(missing))
    plan = read(WEEK / "collection" / week / "sample_plan.json")
    selected = [r for r in plan["selected_races"] if r["date"] == day]
    formal = [r for r in selected if r["sample_origin"] == "official_prediction"]
    undercards = [r for r in selected if r["sample_origin"] == "stratified_sample"]
    runners = 0
    formal_files = {}
    for item in formal:
        path = WEEK / "step1_frozen" / week / (item["race_id"] + ".json")
        data = read(path)
        if data["race_id"] != item["race_id"] or data["source_proof_commit"] is None:
            raise ValueError("formal_proof_not_available:" + item["race_id"])
        rows = data["runners"]
        if not rows:
            raise ValueError("formal_runners_missing")
        for row in rows:
            g = row["factor_grades"]
            if len(g) != 9 or (g[5],g[6],g[7]) != ("B","B-","B"):
                raise ValueError("formal_fallback_pattern_changed:" + item["race_id"])
        runners += len(rows)
        formal_files[item["race_id"]] = {
            "source_path": data["source_prediction_path"],
            "formal_proof_commit": data["source_proof_commit"],
            "first_committed": data["source_first_commit_at"],
            "runners": len(rows),
            "grade_is_not_observation": [6,7,8]
        }
    status = read(ROOT / "docs/data/experience_regime_factor_evidence_status.json")
    if status["week_id"] != week or status["date"] != day or status["target_races"] != len(undercards):
        raise ValueError("undercard_status_not_current")
    observed = {str(k): 0 for k in (2, 3, 5, 6, 7, 8)}
    count = 0
    for item in undercards:
        path = WEEK / "factor_evidence" / week / (item["race_id"] + ".json")
        data = read(path)
        if data["race_id"] != item["race_id"] or data["production_effect"] or data["all_nine_factors_scored"]:
            raise ValueError("research_identity_or_scope_error")
        count += len(data["runners"])
        for row in data["runners"]:
            for key, entry in row["factor_evidence"].items():
                index = key.split("_",1)[0]
                if entry.get("observed_prestart"):
                    observed[index] += 1
                if entry.get("grade") is not None:
                    raise ValueError("additional_unvalidated_grade_found")
    if count != status["horses"] or observed != status["factor_support_counts"]:
        raise ValueError("research_factor_evidence_count_mismatch")
    result = {
        "schema_version": 1, "week_id": week, "date": day,
        "source_code_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        "formal_races": len(formal), "formal_horses": runners,
        "formal_nine_grade_labels": True,
        "formal_factors_6_7_8_observed": False,
        "formal_fallback_grades": {"6_pedigree": "B", "7_workout": "B-", "8_jockey": "B"},
        "formal_explanation": "The three entries above are fixed grade placeholders in the current source; not measured or calibrated factor ratings",
        "formal_files": formal_files,
        "research_undercard_races": len(undercards),
        "research_horses": count,
        "research_observed_source_counts": observed,
        "research_workouts_with_actual_times": 0,
        "research_pedigree_sires_observed_not_calibrated": observed["6"],
        "research_jockey_names_observed_not_course_stats": observed["8"],
        "result": "9_grade_fields_exist_but_9_source_verified_grades_do_not",
        "canonical_prediction_changed": False, "existing_research_prediction_changed": False,
        "no_data_fabrication": True
    }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-id", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    report = inspect(args.week_id, args.date)
    path = ROOT / "docs/data/experience_regime_formal_factor_availability.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JRA_FORMAL_FACTOR_EVIDENCE_AUDIT", report["result"],
          report["formal_horses"], report["research_horses"])


if __name__ == "__main__":
    main()
