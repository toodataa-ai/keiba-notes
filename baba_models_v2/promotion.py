from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _improvement_pct(baseline: float | None, model: float | None) -> float | None:
    if baseline is None or model is None or baseline <= 0:
        return None
    return (baseline - model) / baseline * 100.0


def stage_a_candidate(metrics: dict[str, Any] | None, data: dict[str, Any], audits: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    policy = _load("promotion_policy.json")["stage_a"]
    metrics = metrics or {}
    audits = audits or {}
    gaps: list[str] = []
    mins = policy["minimums"]
    rules = policy["promotion_rules"]

    if data.get("samples", 0) < mins["independent_samples"]:
        gaps.append(f"独立サンプル {mins['independent_samples']}件未満")
    if data.get("years", 0) < mins["calendar_years"]:
        gaps.append(f"暦年 {mins['calendar_years']}年未満")
    if data.get("wet_samples", 0) < mins["wet_samples"]:
        gaps.append(f"雨天サンプル {mins['wet_samples']}件未満")

    for name in policy["required_metrics"]:
        if metrics.get(name) is None:
            gaps.append(f"Stage A {name}未計測")

    mae_imp = _improvement_pct(metrics.get("baseline_mae"), metrics.get("mae"))
    rmse_imp = _improvement_pct(metrics.get("baseline_rmse"), metrics.get("rmse"))
    if mae_imp is None or mae_imp < rules["mae_improvement_vs_baseline_pct_min"]:
        gaps.append("MAEのbaseline改善条件未達/未計測")
    if rmse_imp is None or rmse_imp < rules["rmse_improvement_vs_baseline_pct_min"]:
        gaps.append("RMSEのbaseline改善条件未達/未計測")

    wet_base = metrics.get("wet_baseline_mae")
    wet_model = metrics.get("wet_mae")
    if wet_base is None or wet_model is None:
        gaps.append("雨天MAE比較未計測")
    elif wet_base > 0 and ((wet_model - wet_base) / wet_base * 100.0) > rules["wet_mae_degradation_vs_baseline_pct_max"]:
        gaps.append("雨天MAEが許容劣化幅を超過")

    if rules["leakage_audit_required"] and audits.get("leakage_passed") is not True:
        gaps.append("leakage監査未合格")
    if rules["reproducible_backtest_required"] and audits.get("reproducible") is not True:
        gaps.append("再現可能バックテスト未確認")
    return not gaps, gaps


def stage_b_candidate(metrics: dict[str, Any] | None, data: dict[str, Any], audits: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    policy = _load("promotion_policy.json")["stage_b"]
    metrics = metrics or {}
    audits = audits or {}
    gaps: list[str] = []
    mins = policy["minimums"]
    rules = policy["promotion_rules"]

    if data.get("labelled_races", 0) < mins["labelled_races"]:
        gaps.append(f"ラベル付きレース {mins['labelled_races']}件未満")
    if data.get("independent_meeting_days", 0) < mins["independent_meeting_days"]:
        gaps.append(f"独立開催日 {mins['independent_meeting_days']}日未満")
    if data.get("years", 0) < mins["calendar_years"]:
        gaps.append(f"暦年 {mins['calendar_years']}年未満")
    if data.get("rain_transition_days", 0) < mins["rain_transition_days"]:
        gaps.append(f"雨天遷移日 {mins['rain_transition_days']}日未満")

    for name in policy["required_metrics"]:
        if metrics.get(name) is None:
            gaps.append(f"Stage B {name}未計測")

    ll_imp = _improvement_pct(metrics.get("baseline_log_loss"), metrics.get("multiclass_log_loss"))
    br_imp = _improvement_pct(metrics.get("baseline_brier_score"), metrics.get("brier_score"))
    if ll_imp is None or ll_imp < rules["log_loss_improvement_vs_current_heuristic_pct_min"]:
        gaps.append("Log Lossの現行heuristic改善条件未達/未計測")
    if br_imp is None or br_imp < rules["brier_improvement_vs_current_heuristic_pct_min"]:
        gaps.append("Brier Scoreの現行heuristic改善条件未達/未計測")

    rb = metrics.get("rain_transition_baseline_brier")
    rm = metrics.get("rain_transition_brier")
    if rb is None or rm is None:
        gaps.append("雨天遷移Brier比較未計測")
    elif rb > 0 and ((rm - rb) / rb * 100.0) > rules["rain_transition_brier_degradation_pct_max"]:
        gaps.append("雨天遷移Brierが許容劣化幅を超過")

    if rules["leakage_audit_required"] and audits.get("leakage_passed") is not True:
        gaps.append("leakage監査未合格")
    if rules["reproducible_backtest_required"] and audits.get("reproducible") is not True:
        gaps.append("再現可能バックテスト未確認")
    return not gaps, gaps


def evaluate(model: dict[str, Any]) -> dict[str, Any]:
    a_ok, a_gaps = stage_a_candidate(model.get("stage_a", {}).get("metrics"), model.get("data", {}), model.get("stage_a", {}).get("audits"))
    b_ok, b_gaps = stage_b_candidate(model.get("stage_b", {}).get("metrics"), model.get("data", {}), model.get("stage_b", {}).get("audits"))
    return {
        "track": model["track"],
        "surface": model["surface"],
        "stage_a_candidate": a_ok,
        "stage_b_candidate": b_ok,
        "overall_candidate": a_ok and b_ok,
        "gaps": {"stage_a": a_gaps, "stage_b": b_gaps},
    }


if __name__ == "__main__":
    registry = _load("model_registry.json")
    print(json.dumps([evaluate(m) for m in registry["models"]], ensure_ascii=False, indent=2))
