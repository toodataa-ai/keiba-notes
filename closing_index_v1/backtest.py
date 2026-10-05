from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import kagglehub
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from closing_index import (
    PositionAdjustmentModel,
    add_prior_features,
    add_race_relative_features,
    apply_aci,
    fit_position_adjustment,
)

DATASET = "takamotoki/jra-horse-racing-dataset"
RACE_RESULT_FILE = "19860105-20210731_race_result.csv"
USECOLS = [
    "レースID",
    "レース日付",
    "競馬場名",
    "競争条件",
    "レース番号",
    "レース名",
    "障害区分",
    "芝・ダート区分",
    "距離(m)",
    "馬場状態1",
    "着順",
    "馬名",
    "性別",
    "斤量",
    "タイム",
    "3コーナー",
    "4コーナー",
    "上り",
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
    df["着順"] = pd.to_numeric(df["着順"], errors="coerce")
    df["上り"] = pd.to_numeric(df["上り"], errors="coerce")
    df["4コーナー"] = pd.to_numeric(df["4コーナー"], errors="coerce")
    df["距離(m)"] = pd.to_numeric(df["距離(m)"], errors="coerce")

    flat = df["障害区分"].isna() | (df["障害区分"].astype(str).str.strip() == "")
    surface = df["芝・ダート区分"].astype(str).str.contains("芝|ダ", regex=True)
    valid = (
        df["year"].between(start_year, end_year)
        & flat
        & surface
        & df["着順"].between(1, 30)
        & df["上り"].between(25.0, 60.0)
        & df["4コーナー"].between(1, 30)
        & df["距離(m)"].between(800, 4000)
        & df["馬名"].notna()
    )
    return df.loc[valid].copy()


def prepare_dataset(
    df: pd.DataFrame,
    fit_start: int,
    fit_end: int,
) -> tuple[pd.DataFrame, PositionAdjustmentModel]:
    enriched = add_race_relative_features(df)
    train = enriched[enriched["year"].between(fit_start, fit_end)]
    model = fit_position_adjustment(train)
    enriched = apply_aci(enriched, model)
    enriched = add_prior_features(enriched)
    enriched["target_top3"] = (enriched["着順"] <= 3).astype(int)
    enriched["target_win"] = (enriched["着順"] == 1).astype(int)
    return enriched, model


def serialize_model(
    model: PositionAdjustmentModel,
    fit_start: int,
    fit_end: int,
) -> dict:
    return {
        "model": "Adjusted Closing Index v1 position adjustment",
        "version": "v1",
        "fit_period": [fit_start, fit_end],
        "source_dataset": DATASET,
        "formula": {
            "raw_close_z": "(race_median_last3f - horse_last3f) / robust_race_scale",
            "robust_race_scale": "max(1.4826 * MAD(last3f), fallback_sample_std, 0.15)",
            "corner4_pct": "(corner4_rank - 1) / max(field_size - 1, 1)",
            "adjusted_close_z": "raw_close_z - expected_position_z",
            "aci": "clip(100 + 10 * adjusted_close_z, 70, 130)"
        },
        "distance_bands": {
            "sprint_1400": "<=1400m",
            "mile_1800": "1401-1800m",
            "middle_2200": "1801-2200m",
            "staying_2400plus": ">2200m"
        },
        "position_bands": {
            "front": "0-20%",
            "stalk": "20-40%",
            "mid": "40-65%",
            "rear": "65-100%"
        },
        "exact": [
            {
                "surface": key[0],
                "distance_band": key[1],
                "position_band": key[2],
                "expected_raw_close_z": round(value, 9)
            }
            for key, value in sorted(model.exact.items())
        ],
        "surface_position_fallback": [
            {
                "surface": key[0],
                "position_band": key[1],
                "expected_raw_close_z": round(value, 9)
            }
            for key, value in sorted(model.surface_position.items())
        ],
        "position_only_fallback": [
            {
                "position_band": key,
                "expected_raw_close_z": round(value, 9)
            }
            for key, value in sorted(model.position_only.items())
        ],
        "global_mean": round(model.global_mean, 9),
        "fallback_order": [
            "surface+distance_band+position_band",
            "surface+position_band",
            "position_band",
            "global_mean"
        ]
    }


def evaluate_feature(df: pd.DataFrame, score_col: str) -> Dict[str, float]:
    work = df.copy()
    work["feature_rank"] = work.groupby("レースID")[score_col].rank(
        ascending=False, method="average"
    )

    race_rows: List[dict] = []
    for _, race in work.groupby("レースID", sort=False):
        race = race.sort_values(["feature_rank", score_col], ascending=[True, False])
        top1 = race.iloc[0]
        selected3 = set(race.head(3).index)
        actual_top3 = set(race[race["着順"] <= 3].index)
        winner = race[race["着順"] == 1]
        if winner.empty:
            continue
        race_rows.append(
            {
                "top1_win": float(top1["着順"] == 1),
                "top1_top3": float(top1["着順"] <= 3),
                "top3_capture": len(selected3 & actual_top3) / 3.0,
                "winner_rank": float(winner.iloc[0]["feature_rank"]),
                "top3_mean_rank": float(race[race["着順"] <= 3]["feature_rank"].mean()),
            }
        )
    race_df = pd.DataFrame(race_rows)
    if race_df.empty:
        raise ValueError(f"No eligible races for {score_col}")
    auc = (
        roc_auc_score(work["target_top3"], work[score_col])
        if work["target_top3"].nunique() > 1
        else np.nan
    )
    return {
        "rows": int(len(work)),
        "races": int(len(race_df)),
        "auc_top3": round(float(auc), 6),
        "top1_win_rate": round(float(race_df["top1_win"].mean()), 6),
        "top1_top3_rate": round(float(race_df["top1_top3"].mean()), 6),
        "top3_capture_rate": round(float(race_df["top3_capture"].mean()), 6),
        "winner_mean_rank": round(float(race_df["winner_rank"].mean()), 6),
        "top3_mean_rank": round(float(race_df["top3_mean_rank"].mean()), 6),
    }


def evaluate_all(test: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    score_defs = {
        "prev_last3f_seconds": ("score_prev_last3f", -test["prev_last3f"]),
        "prev_race_relative_z": ("score_prev_raw_z", test["prev_raw_close_z"]),
        "prev_aci": ("score_prev_aci", test["prev_aci"]),
        "prev3_aci_median": ("score_prev3_aci", test["prev3_aci_median"]),
    }
    work = test.copy()
    for _, (col, values) in score_defs.items():
        work[col] = values

    common_cols = [v[0] for v in score_defs.values()]
    work = work.dropna(subset=common_cols).copy()
    race_counts = work.groupby("レースID").size()
    good_races = race_counts[race_counts >= 6].index
    work = work[work["レースID"].isin(good_races)]
    top3_counts = work[work["着順"] <= 3].groupby("レースID").size()
    complete_top3 = top3_counts[top3_counts == 3].index
    work = work[work["レースID"].isin(complete_top3)]

    result: Dict[str, Dict[str, float]] = {}
    for label, (col, _) in score_defs.items():
        result[label] = evaluate_feature(work, col)
    return result


def evaluate_segments(test: pd.DataFrame) -> Dict[str, dict]:
    segments: Dict[str, pd.DataFrame] = {
        "turf": test[test["surface_norm"] == "turf"],
        "dirt": test[test["surface_norm"] == "dirt"],
    }
    for band in ["sprint_1400", "mile_1800", "middle_2200", "staying_2400plus"]:
        segments[band] = test[test["distance_band"] == band]
    out: Dict[str, dict] = {}
    for name, frame in segments.items():
        if frame["レースID"].nunique() < 100:
            continue
        out[name] = evaluate_all(frame)
    return out


def decision(metrics: Dict[str, Dict[str, float]], segments: Dict[str, dict]) -> dict:
    raw = metrics["prev_race_relative_z"]
    aci = metrics["prev_aci"]
    improvements = {
        "auc_top3": aci["auc_top3"] - raw["auc_top3"],
        "top1_win_rate": aci["top1_win_rate"] - raw["top1_win_rate"],
        "top3_capture_rate": aci["top3_capture_rate"] - raw["top3_capture_rate"],
        "winner_mean_rank": raw["winner_mean_rank"] - aci["winner_mean_rank"],
    }
    positive = sum(v > 0 for v in improvements.values())
    surface_harm = []
    for surface in ("turf", "dirt"):
        if surface not in segments:
            continue
        seg = segments[surface]
        delta = (
            seg["prev_aci"]["top3_capture_rate"]
            - seg["prev_race_relative_z"]["top3_capture_rate"]
        )
        if delta < -0.01:
            surface_harm.append(
                {"surface": surface, "top3_capture_delta": round(delta, 6)}
            )
    candidate = positive >= 2 and not surface_harm
    return {
        "integration_candidate": bool(candidate),
        "positive_core_metrics": int(positive),
        "delta_prev_aci_vs_prev_race_relative_z": {
            k: round(v, 6) for k, v in improvements.items()
        },
        "material_surface_harm": surface_harm,
        "rule": "candidate if >=2/4 core metrics improve and neither turf nor dirt loses >1pp top3 capture",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-start-year", type=int, default=2014)
    p.add_argument("--fit-start-year", type=int, default=2015)
    p.add_argument("--fit-end-year", type=int, default=2018)
    p.add_argument("--test-start-year", type=int, default=2019)
    p.add_argument("--test-end-year", type=int, default=2021)
    p.add_argument("--output", default="closing_index_v1/backtest_result.json")
    p.add_argument("--model-output", default="closing_index_v1/model_params.json")
    args = p.parse_args()

    df = load_data(args.data_start_year, args.test_end_year)
    enriched, model = prepare_dataset(df, args.fit_start_year, args.fit_end_year)
    test = enriched[
        enriched["year"].between(args.test_start_year, args.test_end_year)
    ].copy()

    metrics = evaluate_all(test)
    segments = evaluate_segments(test)
    result = {
        "model": "Adjusted Closing Index v1",
        "dataset": DATASET,
        "source_file": RACE_RESULT_FILE,
        "data_start_year": args.data_start_year,
        "position_adjustment_fit_period": [args.fit_start_year, args.fit_end_year],
        "test_period": [args.test_start_year, args.test_end_year],
        "methodology": "next-start backtest; prior-race features only; common eligible runner set per race",
        "metrics": metrics,
        "segments": segments,
        "decision": decision(metrics, segments),
        "limitations": [
            "v1 does not yet use race sectional/laptime data for explicit pace correction",
            "horse identity uses horse name because this public race-result file has no separate horse ID column",
            "dataset ends 2021-07-31 and is used for structural validation, not current-form calibration",
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    model_out = Path(args.model_output)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    model_out.write_text(
        json.dumps(
            serialize_model(model, args.fit_start_year, args.fit_end_year),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("MODEL_PARAMS_PATH=" + str(model_out))
    print("BACKTEST_DECISION=" + json.dumps(result["decision"], ensure_ascii=False))


if __name__ == "__main__":
    main()
