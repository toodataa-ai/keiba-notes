#!/usr/bin/env python3
"""Zero-cost, deterministic nine-factor *source-quality* layer, shared by formal JRA and E012.

The scores/marks/odds/predictions in frozen originals are immutable. This module
assesses which factor inputs are observed, which grades are proxies, and which
must remain ungraded. It is a challenger DIAGNOSTIC, not a retroactive forecast.
Only dated prereace facts already frozen in Git are accepted as inputs.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from statistics import median
from typing import Any

FACTOR_NAMES = ("斤量", "展開", "馬場", "ローテ", "コース", "血統", "調教", "騎手", "基礎能力")
STATUS = ("observed", "proxy_uncalibrated", "identity_only", "unavailable")


def factor(number: int, status: str, *, facts: dict | None = None,
           grade: str | None = None, sample_size: int = 0, caveat: str = "") -> dict:
    if number not in range(1, 10) or status not in STATUS:
        raise ValueError("invalid_factor_status")
    if grade is not None and status != "proxy_uncalibrated":
        raise ValueError("numerical_grade_without_validated_model_forbidden")
    if sample_size < 0:
        raise ValueError("negative_sample_size")
    return {
        "number": number, "name": FACTOR_NAMES[number-1],
        "status": status, "grade": grade, "facts": facts or {},
        "sample_size": sample_size, "caveat": caveat
    }


def _ensure_same_horse(row: dict, evidence_row: dict):
    if (row["horse_number"] != evidence_row["horse_number"] or
            row["horse_name"] != evidence_row["horse_name"] or
            row["regime"] != evidence_row["regime"]):
        raise ValueError("immutable_horse_identity_mismatch")


def undercard_factor_quality(baseline: dict, evidence: dict) -> dict:
    """Build factor-quality diagnostics; never re-estimate win or top-three probabilities."""
    if baseline["race_id"] != evidence["race_id"] or baseline["date"] != evidence["date"]:
        raise ValueError("immutable_race_identity_mismatch")
    if evidence["production_effect"] or evidence["all_nine_factors_scored"]:
        raise ValueError("research_only_evidence_expected")
    if (baseline.get("probabilities_calibrated") is not False or
            baseline.get("no_odds_or_results_accessed") is not True or
            evidence.get("no_odds_read_for_scores") is not True or
            evidence.get("no_current_race_results_used") is not True):
        raise ValueError("price_blind_frozen_input_unverified")
    old = {r["horse_number"]: r for r in baseline["runners"]}
    new = {r["horse_number"]: r for r in evidence["runners"]}
    if set(old) != set(new):
        raise ValueError("field_roster_mismatch")
    all_weights = [r["factor_evidence"]["8_jockey"].get("official_weight_kg")
                   for r in evidence["runners"]]
    eligible = [v for v in all_weights if isinstance(v, (int, float)) and not isinstance(v, bool)]
    median_weight = median(eligible) if eligible else None
    result = []
    for no in sorted(old):
        prior, observed = old[no], new[no]
        _ensure_same_horse(prior, observed)
        e = observed["factor_evidence"]
        p = e["2_pace"]["historical_first_section_positions"]
        same_going = e["3_ground"]["similar_going_record"]
        same_course = e["5_course"]["prior_matching_course_races"]
        sire = e["6_pedigree"]["official_sire"]
        dam = e["6_pedigree"]["official_dam"]
        damsire = e["6_pedigree"]["official_damsire"]
        jockey = e["8_jockey"]["official_jockey"]
        weight = e["8_jockey"]["official_weight_kg"]
        if not isinstance(weight, (float, int)) or isinstance(weight, bool):
            one = factor(1, "unavailable", caveat="斤量の数値なし")
        else:
            one = factor(1, "observed",
                         facts={"weight_kg": weight, "field_median_kg": median_weight,
                                "delta_from_field_median_kg": round(weight-median_weight, 3)},
                         caveat="斤量差と競走能力の関係は未校正")
        passing_fracs = [x["front_fraction"] for x in p if isinstance(x.get("front_fraction"), (float, int))]
        if passing_fracs:
            avg = sum(passing_fracs) / len(passing_fracs)
            style = "先行寄り" if avg <= 0.38 else "後方寄り" if avg >= 0.72 else "中団寄り"
            two = factor(2, "observed", facts={
                "past_first_corner_relative_mean": round(avg, 4),
                "past_position_style": style}, sample_size=len(passing_fracs),
                caveat="過去の位置取りであり当日のペース・展開の予測ではない")
        else:
            two = factor(2, "unavailable", caveat="過去の通過位置データなし。新馬は適性未知")
        three = factor(3, "observed" if same_going else "unavailable",
                       facts={"going": e["3_ground"]["official_current_going"],
                              "matching_going_starts": len(same_going),
                              "top3_finishes": sum(x.get("finish") in (1, 2, 3) for x in same_going)},
                       sample_size=len(same_going),
                       caveat="馬場状態が一致した履歴。馬場バイアス・競走条件・統計的優位は未検証")
        recent = prior["official_prior_evidence"]
        dates = [date.fromisoformat(x["date"]) for x in recent if x.get("date")]
        if dates:
            rest = (date.fromisoformat(baseline["date"]) - max(dates)).days
            if rest <= 0:
                raise ValueError("future_or_postrace_history")
            four = factor(4, "proxy_uncalibrated", facts={"rest_days": rest},
                          grade=prior["factor_grades"][3], sample_size=len(dates),
                          caveat="レース間隔は実測、グレードへの変換は未校正")
        else:
            four = factor(4, "unavailable", caveat="過去出走なし・間隔評価不能")
        five = factor(5, "observed" if same_course else "unavailable",
                      facts={"course_m":e["5_course"]["official_distance_m"],
                             "surface":e["5_course"]["official_surface"],
                             "same_course_starts":len(same_course)},
                      sample_size=len(same_course),
                      caveat="過去の同一条件履歴のみ。適性グレードの校正なし")
        six = factor(6, "identity_only" if sire else "unavailable",
                     facts={"sire": sire, "dam": dam, "damsire": damsire},
                     caveat="血統表のみ。距離別・馬場別の種牡馬勝率と母数が未取得")
        seven = factor(7, "unavailable", facts={"workout_times":None},
                       caveat="無料出馬表に馬別調教時計の検証可能データなし")
        eight = factor(8, "identity_only" if jockey else "unavailable",
                       facts={"jockey":jockey},
                       caveat="騎手名のみ。競馬場・距離条件別の事前成績・母数は未取得")
        ability = prior.get("career_ability_proxy")
        nine = factor(9, "proxy_uncalibrated" if ability is not None else "unavailable",
                      facts={"career_ability_proxy": ability} if ability is not None else {},
                      grade=prior["factor_grades"][8] if ability is not None else None,
                      sample_size=observed["raced_before"],
                      caveat="既存の戦績スコア。新馬は同評価へ強制しない")
        factors = [one, two, three, four, five, six, seven, eight, nine]
        observed_count = sum(f["status"] in ("observed", "identity_only", "proxy_uncalibrated")
                             for f in factors)
        result.append({
            "horse_number": no, "horse_name": prior["horse_name"], "regime": prior["regime"],
            "factors": factors, "observed_or_identity_factors": observed_count,
            "missing_factors": [f["number"] for f in factors if f["status"] == "unavailable"],
            "baseline_rank_frozen": prior["step1_rank"],
            "baseline_mark_frozen": prior["mark"],
            "baseline_win_probability_frozen": prior["predicted_win_probability"],
            "baseline_top3_probability_frozen": prior["predicted_top3_probability"],
            "new_rank": None, "new_probability": None,
            "outcome_backtest": None,
        })
    return {
        "race_id": baseline["race_id"], "date": baseline["date"],
        "source_candidate_capture": baseline["capture_type"],
        "source_factor_evidence_capture": evidence["capture_type"],
        "status": "free_source_diagnostics_only_not_a_new_prerace_prediction",
        "no_poststart_retroactive_forecast": True,
        "predictive_improvement_unverified": True,
        "change_to_formal_jra": False,
        "runners": result
    }


def formal_factor_quality(frozen: dict) -> dict:
    """Interpret formal labels faithfully without reassigning scores or changing marks."""
    rows = []
    if not frozen.get("no_odds_used"):
        raise ValueError("formal_price_blind_proof_required")
    for row in frozen["runners"]:
        grades = row["factor_grades"]
        if len(grades) != 9:
            raise ValueError("not_nine_formal_grades")
        if grades[5:8] != ["B", "B-", "B"]:
            raise ValueError("formal_placeholder_contract_changed")
        rows.append({
            "horse_number": row["horse_number"], "horse_name": row["horse_name"],
            "baseline_rank_frozen": row["step1_rank"],
            "baseline_mark_frozen": row["mark"],
            "factor_grades_unchanged": grades,
            "fallback_factors": [
                {"number": 6, "grade": "B", "status": "unavailable", "basis": "pedigree compatibility not established"},
                {"number": 7, "grade": "B-", "status": "unavailable", "basis": "workout data not observed"},
                {"number": 8, "grade": "B", "status": "unavailable", "basis": "jockey course-adjusted stats not observed"}
            ],
            "other_factors_status": "existing_heuristic_not_independently_calibrated",
        })
    return {"race_id": frozen["race_id"],
            "audit_type": "formal_grade_source_completeness_not_new_prediction",
            "runners": rows, "source_proof_commit": frozen["source_proof_commit"],
            "canonical_unchanged": True}


def compare_quality(formal_records: list[dict], undercards: list[dict]) -> dict:
    """A/B is evidence coverage only; NEVER winner accuracy or ROI without outcomes."""
    if not undercards or not formal_records:
        raise ValueError("comparison_requires_both_cohorts")
    sum_horses = sum(len(x["runners"]) for x in undercards)
    formal_horses = sum(len(x["runners"]) for x in formal_records)
    supported = {str(i): 0 for i in range(1, 10)}
    lacking = {str(i): 0 for i in range(1, 10)}
    by_regime = {r: {"horses": 0, "factor_observations": 0, "factor_missing": 0}
                 for r in ("E0","E1","E2")}
    untouched = 0
    for race in undercards:
        for h in race["runners"]:
            by_regime[h["regime"]]["horses"] += 1
            for f in h["factors"]:
                present = f["status"] != "unavailable"
                supported[str(f["number"])] += int(present)
                lacking[str(f["number"])] += int(not present)
                by_regime[h["regime"]]["factor_observations"] += int(present)
                by_regime[h["regime"]]["factor_missing"] += int(not present)
            if h["new_rank"] is not None or h["new_probability"] is not None:
                raise ValueError("retrospective_prediction_disallowed")
            untouched += 1
    if sum(supported.values()) + sum(lacking.values()) != sum_horses * 9:
        raise ValueError("nine_factor_accounting")
    return {
        "schema_version": 1, "stage": "research_challenger_diagnostics",
        "formal_races": len(formal_records), "formal_horses": formal_horses,
        "undercard_races": len(undercards), "undercard_horses": sum_horses,
        "frozen_predictions_untouched": untouched,
        "coverage_by_factor": {n: {"observed_or_identity":supported[n],
                                   "unavailable":lacking[n]}
                               for n in supported},
        "by_experience_regime": by_regime,
        "comparison_kind": "legacy fixed 9 grade slots vs new evidence/unknown-status accounting",
        "winner_accuracy_old": None, "winner_accuracy_challenger": None,
        "roi_old": None, "roi_challenger": None,
        "calibration_improvement_claimed": False,
        "production_effect": False,
        "stage_recommendation": "keep_formal_frozen_run_prospective_calibration_before_promotion",
    }
