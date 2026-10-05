from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import kagglehub
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from closing_index_v1_1 import (
    DemandProfileModel,
    PositionAdjustmentModel,
    add_prior_features,
    add_race_relative_features,
    apply_aci,
    apply_demand_profile,
    fit_demand_profile,
    fit_position_adjustment,
)

DATASET = "takamotoki/jra-horse-racing-dataset"
RACE_RESULT_FILE = "19860105-20210731_race_result.csv"
USECOLS = [
    "レースID", "レース日付", "競馬場名", "競争条件", "レース番号", "レース名",
    "障害区分", "芝・ダート区分", "距離(m)", "馬場状態1", "着順", "馬名",
    "性別", "斤量", "タイム", "3コーナー", "4コーナー", "上り",
]


def find_dataset_file(root: Path) -> Path:
    direct = root / RACE_RESULT_FILE
    if direct.exists():
        return direct
    matches = list(root.rglob(RACE_RESULT_FILE))
    if not matches:
        raise FileNotFoundError(f"{RACE_RESULT_FILE} not found below {root}")
    return matches[0]


def load_data(start_year: int, end_year: int) -> pd.DataFrame:
    root = Path(kagglehub.dataset_download(DATASET))
    csv_path = find_dataset_file(root)
    df = pd.read_csv(csv_path, usecols=USECOLS, low_memory=False)
    df["レース日付"] = pd.to_datetime(df["レース日付"], errors="coerce")
    df["year"] = df["レース日付"].dt.year
    for c in ["着順", "上り", "4コーナー", "距離(m)"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    flat = df["障害区分"].isna() | (df["障害区分"].astype(str).str.strip() == "")
    surface = df["芝・ダート区分"].astype(str).str.contains("芝|ダ", regex=True)
    valid = (
        df["year"].between(start_year, end_year)
        & flat & surface
        & df["着順"].between(1, 30)
        & df["上り"].between(25.0, 60.0)
        & df["4コーナー"].between(1, 30)
        & df["距離(m)"].between(800, 4000)
        & df["馬名"].notna() & df["競馬場名"].notna()
    )
    return df.loc[valid].copy()


def prepare_dataset(df: pd.DataFrame, fit_start: int, fit_end: int) -> tuple[pd.DataFrame, PositionAdjustmentModel, DemandProfileModel, dict]:
    enriched = add_race_relative_features(df)
    train0 = enriched[enriched["year"].between(fit_start, fit_end)].copy()
    pos_model = fit_position_adjustment(train0)
    enriched = apply_aci(enriched, pos_model)
    train1 = enriched[enriched["year"].between(fit_start, fit_end)].copy()
    demand_model = fit_demand_profile(train1)
    enriched = apply_demand_profile(enriched, demand_model)
    enriched = add_prior_features(enriched)
    enriched["target_top3"] = (enriched["着順"] <= 3).astype(int)
    enriched["target_win"] = (enriched["着順"] == 1).astype(int)
    fit_prior = enriched[
        enriched["year"].between(fit_start, fit_end)
        & (enriched["prior_valid_starts"] >= 3)
        & enriched["reproducibility_score"].notna()
    ]
    q = fit_prior["reproducibility_score"].quantile([1/3, 2/3]).to_dict()
    thresholds = {"low_max": float(q.get(1/3, 45.0)), "high_min": float(q.get(2/3, 65.0))}
    return enriched, pos_model, demand_model, thresholds


def _serialize_tuple_map(mapping: dict, names: list[str], value_name: str) -> list[dict]:
    out = []
    for key, value in sorted(mapping.items()):
        if not isinstance(key, tuple):
            key = (key,)
        row = {n: k for n, k in zip(names, key)}
        row[value_name] = round(float(value), 9)
        out.append(row)
    return out


def serialize_models(pos: PositionAdjustmentModel, demand: DemandProfileModel, fit_start: int, fit_end: int, consistency_thresholds: dict) -> dict:
    return {
        "model": "Adjusted Closing Index v1.1",
        "version": "v1.1",
        "fit_period": [fit_start, fit_end],
        "source_dataset": DATASET,
        "principles": [
            "absolute last-3F seconds are not treated as ability by themselves",
            "ACI is race-relative and 4th-corner-position adjusted",
            "course/surface/distance/going closing reliance is learned only from fit-period history",
            "low closing-reliance courses do not reward slower last-3F; they reduce the weight of sharp-closing evidence and shift interpretation toward sustained/position performance",
            "horse inconsistency is represented as reproducibility uncertainty, separate from peak ability",
        ],
        "position_adjustment": {
            "formula": {
                "raw_close_z": "(race_median_last3f - horse_last3f) / robust_race_scale",
                "adjusted_close_z": "raw_close_z - expected_position_z",
                "aci": "clip(100 + 10 * adjusted_close_z, 70, 130)",
            },
            "exact": _serialize_tuple_map(pos.exact, ["surface", "distance_band", "position_band"], "expected_raw_close_z"),
            "surface_position_fallback": _serialize_tuple_map(pos.surface_position, ["surface", "position_band"], "expected_raw_close_z"),
            "position_only_fallback": [{"position_band": k, "expected_raw_close_z": round(float(v), 9)} for k, v in sorted(pos.position_only.items())],
            "global_mean": round(float(pos.global_mean), 9),
        },
        "demand_profile": {
            "definition": "closing_edge = mean(adjusted_close_z of top3) - mean(adjusted_close_z of non-top3)",
            "interpretation": {
                "sharp_closing": "historically high reliance on strong adjusted closing performance",
                "balanced": "middle closing reliance",
                "sustained_position": "lower closing reliance; prioritize position/sustained performance rather than raw sharpness",
            },
            "thresholds": {"low": round(float(demand.low_threshold), 9), "high": round(float(demand.high_threshold), 9)},
            "exact": _serialize_tuple_map(demand.exact, ["venue", "surface", "distance_band", "going"], "closing_edge"),
            "course_fallback": _serialize_tuple_map(demand.course_fallback, ["venue", "surface", "distance_band"], "closing_edge"),
            "surface_distance_going_fallback": _serialize_tuple_map(demand.surface_distance_going, ["surface", "distance_band", "going"], "closing_edge"),
            "surface_distance_fallback": _serialize_tuple_map(demand.surface_distance, ["surface", "distance_band"], "closing_edge"),
            "global_edge": round(float(demand.global_edge), 9),
        },
        "reproducibility": {
            "base": "MAD of prior ACI, preferably among starts with the same demand_type",
            "same_demand_min_starts_for_median": 2,
            "same_demand_min_starts_for_mad": 3,
            "score": "100 * exp(-reproducibility_mad / 12)",
            "fit_period_tercile_thresholds": consistency_thresholds,
            "important": "reproducibility changes confidence/current-value interpretation, not peak ability itself",
        },
        "runtime_pace_rule": "The public dataset lacks reliable full sectional pace labels for this test. At prediction time, the existing S/M/M-H/H pace forecast must further adjust demand interpretation; v1.1 course demand is not a substitute for pace analysis.",
    }


def evaluate_feature(df: pd.DataFrame, score_col: str) -> Dict[str, float]:
    work = df.copy()
    work["feature_rank"] = work.groupby("レースID")[score_col].rank(ascending=False, method="average")
    race_rows: List[dict] = []
    for _, race in work.groupby("レースID", sort=False):
        race = race.sort_values(["feature_rank", score_col], ascending=[True, False])
        top1 = race.iloc[0]
        selected3 = set(race.head(3).index)
        actual_top3 = set(race[race["着順"] <= 3].index)
        winner = race[race["着順"] == 1]
        if winner.empty:
            continue
        race_rows.append({
            "top1_win": float(top1["着順"] == 1),
            "top1_top3": float(top1["着順"] <= 3),
            "top3_capture": len(selected3 & actual_top3) / 3.0,
            "winner_rank": float(winner.iloc[0]["feature_rank"]),
            "top3_mean_rank": float(race[race["着順"] <= 3]["feature_rank"].mean()),
        })
    race_df = pd.DataFrame(race_rows)
    if race_df.empty:
        raise ValueError(f"No eligible races for {score_col}")
    auc = roc_auc_score(work["target_top3"], work[score_col]) if work["target_top3"].nunique() > 1 else np.nan
    return {
        "rows": int(len(work)), "races": int(len(race_df)),
        "auc_top3": round(float(auc), 6),
        "top1_win_rate": round(float(race_df["top1_win"].mean()), 6),
        "top1_top3_rate": round(float(race_df["top1_top3"].mean()), 6),
        "top3_capture_rate": round(float(race_df["top3_capture"].mean()), 6),
        "winner_mean_rank": round(float(race_df["winner_rank"].mean()), 6),
        "top3_mean_rank": round(float(race_df["top3_mean_rank"].mean()), 6),
    }


def eligible_common(test: pd.DataFrame) -> pd.DataFrame:
    cols = ["prev_last3f", "prev_raw_close_z", "prev_aci", "prev3_aci_median", "demand_fit_aci", "aci_v11_confidence_score", "reproducibility_score"]
    work = test.dropna(subset=cols).copy()
    race_counts = work.groupby("レースID").size()
    work = work[work["レースID"].isin(race_counts[race_counts >= 6].index)]
    top3_counts = work[work["着順"] <= 3].groupby("レースID").size()
    work = work[work["レースID"].isin(top3_counts[top3_counts == 3].index)]
    return work


def evaluate_all(test: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    work = eligible_common(test)
    scores = {
        "prev_last3f_seconds": -work["prev_last3f"],
        "prev_race_relative_z": work["prev_raw_close_z"],
        "prev_aci": work["prev_aci"],
        "prev3_aci_median": work["prev3_aci_median"],
        "demand_fit_aci_v11": work["demand_fit_aci"],
        "confidence_adjusted_aci_v11": work["aci_v11_confidence_score"],
    }
    out = {}
    for label, values in scores.items():
        col = f"score_{label}"
        tmp = work.copy(); tmp[col] = values
        out[label] = evaluate_feature(tmp, col)
    return out


def evaluate_segments(test: pd.DataFrame) -> Dict[str, dict]:
    segments = {"turf": test[test["surface_norm"] == "turf"], "dirt": test[test["surface_norm"] == "dirt"]}
    for band in ["sprint_1400", "mile_1800", "middle_2200", "staying_2400plus"]:
        segments[band] = test[test["distance_band"] == band]
    for demand in ["sharp_closing", "balanced", "sustained_position"]:
        segments[f"demand_{demand}"] = test[test["demand_type"] == demand]
    out = {}
    for name, frame in segments.items():
        if frame["レースID"].nunique() >= 100:
            out[name] = evaluate_all(frame)
    return out


def consistency_signal(test: pd.DataFrame, thresholds: dict) -> dict:
    work = eligible_common(test).copy()
    work["base_rank"] = work.groupby("レースID")["demand_fit_aci"].rank(ascending=False, method="first")
    top = work[work["base_rank"] == 1].copy()
    lo, hi = thresholds["low_max"], thresholds["high_min"]
    top["bucket"] = np.select([top["reproducibility_score"] <= lo, top["reproducibility_score"] >= hi], ["low", "high"], default="mid")
    result = {}
    for b in ["low", "mid", "high"]:
        g = top[top["bucket"] == b]
        if g.empty:
            continue
        result[b] = {
            "races": int(len(g)),
            "top1_win_rate": round(float((g["着順"] == 1).mean()), 6),
            "top1_top3_rate": round(float((g["着順"] <= 3).mean()), 6),
            "mean_reproducibility_score": round(float(g["reproducibility_score"].mean()), 3),
        }
    return result


def decision(metrics: dict, segments: dict, consistency: dict) -> dict:
    baseline = metrics["prev3_aci_median"]
    demand = metrics["demand_fit_aci_v11"]
    conf = metrics["confidence_adjusted_aci_v11"]
    demand_delta = {
        "auc_top3": demand["auc_top3"] - baseline["auc_top3"],
        "top1_win_rate": demand["top1_win_rate"] - baseline["top1_win_rate"],
        "top3_capture_rate": demand["top3_capture_rate"] - baseline["top3_capture_rate"],
        "winner_mean_rank": baseline["winner_mean_rank"] - demand["winner_mean_rank"],
    }
    conf_delta = {
        "auc_top3": conf["auc_top3"] - baseline["auc_top3"],
        "top1_win_rate": conf["top1_win_rate"] - baseline["top1_win_rate"],
        "top3_capture_rate": conf["top3_capture_rate"] - baseline["top3_capture_rate"],
        "winner_mean_rank": baseline["winner_mean_rank"] - conf["winner_mean_rank"],
    }
    material_harm = []
    for s in ["turf", "dirt"]:
        if s in segments:
            d = segments[s]["demand_fit_aci_v11"]["top3_capture_rate"] - segments[s]["prev3_aci_median"]["top3_capture_rate"]
            if d < -0.01:
                material_harm.append({"segment": s, "top3_capture_delta": round(float(d), 6)})
    high_low_gap = None
    if "high" in consistency and "low" in consistency:
        high_low_gap = consistency["high"]["top1_top3_rate"] - consistency["low"]["top1_top3_rate"]
    supplemental_ok = demand_delta["auc_top3"] >= -0.005 and demand_delta["top3_capture_rate"] >= -0.005 and not material_harm and (high_low_gap is None or high_low_gap >= 0.0)
    return {
        "integration_candidate": bool(supplemental_ok),
        "integration_mode": "supplemental: demand_fit + reproducibility confidence; do not replace peak ability or the 9-axis structure",
        "delta_demand_fit_vs_prev3_aci": {k: round(float(v), 6) for k, v in demand_delta.items()},
        "delta_confidence_adjusted_vs_prev3_aci": {k: round(float(v), 6) for k, v in conf_delta.items()},
        "high_vs_low_reproducibility_top1_top3_gap": None if high_low_gap is None else round(float(high_low_gap), 6),
        "material_surface_harm": material_harm,
        "rule": "supplemental adoption if demand-fit AUC/top3 capture are not worse by >0.5pp, no turf/dirt segment loses >1pp top3 capture, and reliability signal is non-inverted",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-start-year", type=int, default=2014)
    p.add_argument("--fit-start-year", type=int, default=2015)
    p.add_argument("--fit-end-year", type=int, default=2018)
    p.add_argument("--test-start-year", type=int, default=2019)
    p.add_argument("--test-end-year", type=int, default=2021)
    p.add_argument("--output", default="closing_index_v1/backtest_result_v1_1.json")
    p.add_argument("--model-output", default="closing_index_v1/model_params_v1_1.json")
    args = p.parse_args()
    df = load_data(args.data_start_year, args.test_end_year)
    enriched, pos, demand, thresholds = prepare_dataset(df, args.fit_start_year, args.fit_end_year)
    test = enriched[enriched["year"].between(args.test_start_year, args.test_end_year)].copy()
    metrics = evaluate_all(test)
    segments = evaluate_segments(test)
    consistency = consistency_signal(test, thresholds)
    result = {
        "model": "Adjusted Closing Index v1.1",
        "dataset": DATASET,
        "source_file": RACE_RESULT_FILE,
        "fit_period": [args.fit_start_year, args.fit_end_year],
        "test_period": [args.test_start_year, args.test_end_year],
        "methodology": "leakage-safe next-start validation; course/surface/distance/going demand profile fitted only on 2015-2018; prior-race features only",
        "metrics": metrics,
        "segments": segments,
        "reproducibility_signal": consistency,
        "decision": decision(metrics, segments, consistency),
        "limitations": [
            "full sectional pace labels are not available in this public race-result test, so runtime S/M/M-H/H pace remains a separate prediction-time adjustment",
            "reproducibility estimates performance volatility after race-relative and position adjustment; it is a proxy for uncertainty, not a claim about a horse's psychology",
            "horse identity uses horse name because this public file has no separate horse ID column",
            "dataset ends 2021-07-31 and is structural validation, not current-form calibration",
        ],
    }
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    model_out = Path(args.model_output); model_out.parent.mkdir(parents=True, exist_ok=True)
    model_out.write_text(json.dumps(serialize_models(pos, demand, args.fit_start_year, args.fit_end_year, thresholds), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("MODEL_PARAMS_PATH=" + str(model_out))
    print("BACKTEST_DECISION=" + json.dumps(result["decision"], ensure_ascii=False))


if __name__ == "__main__":
    main()
