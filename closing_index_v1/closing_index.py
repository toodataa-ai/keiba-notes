from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd


POSITION_BINS = [-1e-9, 0.20, 0.40, 0.65, 1.0]
POSITION_LABELS = ["front", "stalk", "mid", "rear"]


@dataclass(frozen=True)
class PositionAdjustmentModel:
    exact: Dict[Tuple[str, str, str], float]
    surface_position: Dict[Tuple[str, str], float]
    position_only: Dict[str, float]
    global_mean: float


def distance_band(distance_m: float) -> str:
    if pd.isna(distance_m):
        return "unknown"
    d = int(distance_m)
    if d <= 1400:
        return "sprint_1400"
    if d <= 1800:
        return "mile_1800"
    if d <= 2200:
        return "middle_2200"
    return "staying_2400plus"


def normalize_surface(value: object) -> str:
    s = str(value)
    if "芝" in s:
        return "turf"
    if "ダ" in s:
        return "dirt"
    return "other"


def _robust_scale(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) < 2:
        return 0.20
    med = np.median(values)
    mad = np.median(np.abs(values - med))
    scale = 1.4826 * mad
    if not np.isfinite(scale) or scale < 0.15:
        std = np.std(values, ddof=1) if len(values) > 1 else 0.20
        scale = max(float(std) if np.isfinite(std) else 0.20, 0.15)
    return float(scale)


def add_race_relative_features(
    df: pd.DataFrame,
    race_col: str = "レースID",
    last3f_col: str = "上り",
    corner4_col: str = "4コーナー",
    distance_col: str = "距離(m)",
    surface_col: str = "芝・ダート区分",
) -> pd.DataFrame:
    out = df.copy()
    out[last3f_col] = pd.to_numeric(out[last3f_col], errors="coerce")
    out[corner4_col] = pd.to_numeric(out[corner4_col], errors="coerce")

    g = out.groupby(race_col, sort=False)
    out["field_size"] = g[race_col].transform("size")
    out["race_median_3f"] = g[last3f_col].transform("median")
    scales = g[last3f_col].transform(_robust_scale)
    out["race_3f_scale"] = scales.clip(lower=0.15)
    out["raw_close_z"] = (
        out["race_median_3f"] - out[last3f_col]
    ) / out["race_3f_scale"]

    denom = (out["field_size"] - 1).clip(lower=1)
    out["corner4_pct"] = ((out[corner4_col] - 1) / denom).clip(0, 1)
    out["position_band"] = pd.cut(
        out["corner4_pct"],
        bins=POSITION_BINS,
        labels=POSITION_LABELS,
        include_lowest=True,
    ).astype("object")
    out["position_band"] = out["position_band"].fillna("unknown")
    out["surface_norm"] = out[surface_col].map(normalize_surface)
    out["distance_band"] = out[distance_col].map(distance_band)
    out["raw_close_index"] = (100 + 10 * out["raw_close_z"]).clip(70, 130)
    return out


def _means_with_min_count(
    df: pd.DataFrame,
    group_cols: Iterable[str],
    value_col: str,
    min_count: int,
) -> Dict[Tuple[str, ...], float]:
    stats = (
        df.groupby(list(group_cols), dropna=False)[value_col]
        .agg(["mean", "count"])
        .reset_index()
    )
    stats = stats[stats["count"] >= min_count]
    result: Dict[Tuple[str, ...], float] = {}
    for row in stats.itertuples(index=False):
        values = tuple(str(getattr(row, c)) for c in group_cols)
        result[values] = float(row.mean)
    return result


def fit_position_adjustment(
    train_df: pd.DataFrame,
    value_col: str = "raw_close_z",
    min_exact_count: int = 300,
    min_fallback_count: int = 500,
) -> PositionAdjustmentModel:
    valid = train_df[
        train_df[value_col].notna()
        & train_df["position_band"].notna()
        & (train_df["position_band"] != "unknown")
        & train_df["surface_norm"].isin(["turf", "dirt"])
    ].copy()
    if valid.empty:
        raise ValueError("No valid rows to fit position adjustment")

    exact = _means_with_min_count(
        valid,
        ["surface_norm", "distance_band", "position_band"],
        value_col,
        min_exact_count,
    )
    surface_position = _means_with_min_count(
        valid,
        ["surface_norm", "position_band"],
        value_col,
        min_fallback_count,
    )
    pos_stats = (
        valid.groupby("position_band")[value_col]
        .agg(["mean", "count"])
        .reset_index()
    )
    position_only = {
        str(r.position_band): float(r.mean)
        for r in pos_stats.itertuples(index=False)
        if int(r.count) >= min_fallback_count
    }
    return PositionAdjustmentModel(
        exact=exact,
        surface_position=surface_position,
        position_only=position_only,
        global_mean=float(valid[value_col].mean()),
    )


def expected_position_z(row: pd.Series, model: PositionAdjustmentModel) -> float:
    exact_key = (
        str(row["surface_norm"]),
        str(row["distance_band"]),
        str(row["position_band"]),
    )
    if exact_key in model.exact:
        return model.exact[exact_key]
    surface_key = (str(row["surface_norm"]), str(row["position_band"]))
    if surface_key in model.surface_position:
        return model.surface_position[surface_key]
    pos = str(row["position_band"])
    if pos in model.position_only:
        return model.position_only[pos]
    return model.global_mean


def apply_aci(df: pd.DataFrame, model: PositionAdjustmentModel) -> pd.DataFrame:
    out = df.copy()
    out["expected_position_z"] = out.apply(
        expected_position_z, axis=1, model=model
    )
    out["adjusted_close_z"] = out["raw_close_z"] - out["expected_position_z"]
    out["aci"] = (100 + 10 * out["adjusted_close_z"]).clip(70, 130)
    return out


def add_prior_features(
    df: pd.DataFrame,
    horse_col: str = "馬名",
    date_col: str = "レース日付",
    race_col: str = "レースID",
    last3f_col: str = "上り",
) -> pd.DataFrame:
    out = df.sort_values([horse_col, date_col, race_col]).copy()
    grouped = out.groupby(horse_col, sort=False)
    out["prev_last3f"] = grouped[last3f_col].shift(1)
    out["prev_raw_close_z"] = grouped["raw_close_z"].shift(1)
    out["prev_aci"] = grouped["aci"].shift(1)
    out["prev3_aci_median"] = grouped["aci"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).median()
    )
    out["prior_valid_starts"] = grouped["aci"].transform(
        lambda s: s.shift(1).notna().cumsum()
    )
    return out
