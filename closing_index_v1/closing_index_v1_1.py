from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd


POSITION_BINS = [-1e-9, 0.20, 0.40, 0.65, 1.0]
POSITION_LABELS = ["front", "stalk", "mid", "rear"]
DEMAND_LABELS = ("sustained_position", "balanced", "sharp_closing")


@dataclass(frozen=True)
class PositionAdjustmentModel:
    exact: Dict[Tuple[str, str, str], float]
    surface_position: Dict[Tuple[str, str], float]
    position_only: Dict[str, float]
    global_mean: float


@dataclass(frozen=True)
class DemandProfileModel:
    exact: Dict[Tuple[str, str, str, str], float]
    course_fallback: Dict[Tuple[str, str, str], float]
    surface_distance_going: Dict[Tuple[str, str, str], float]
    surface_distance: Dict[Tuple[str, str], float]
    global_edge: float
    low_threshold: float
    high_threshold: float


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


def normalize_going(value: object) -> str:
    s = str(value).strip()
    if "不良" in s:
        return "heavy"
    if "重" in s and "稍" not in s:
        return "soft"
    if "稍" in s:
        return "yielding"
    if "良" in s:
        return "firm"
    return "unknown"


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


def _rolling_mad(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        return np.nan
    med = np.median(arr)
    return float(np.median(np.abs(arr - med)))


def add_race_relative_features(
    df: pd.DataFrame,
    race_col: str = "レースID",
    last3f_col: str = "上り",
    corner4_col: str = "4コーナー",
    distance_col: str = "距離(m)",
    surface_col: str = "芝・ダート区分",
    going_col: str = "馬場状態1",
) -> pd.DataFrame:
    out = df.copy()
    out[last3f_col] = pd.to_numeric(out[last3f_col], errors="coerce")
    out[corner4_col] = pd.to_numeric(out[corner4_col], errors="coerce")
    g = out.groupby(race_col, sort=False)
    out["field_size"] = g[race_col].transform("size")
    out["race_median_3f"] = g[last3f_col].transform("median")
    scales = g[last3f_col].transform(_robust_scale)
    out["race_3f_scale"] = scales.clip(lower=0.15)
    out["raw_close_z"] = (out["race_median_3f"] - out[last3f_col]) / out["race_3f_scale"]
    denom = (out["field_size"] - 1).clip(lower=1)
    out["corner4_pct"] = ((out[corner4_col] - 1) / denom).clip(0, 1)
    out["position_band"] = pd.cut(out["corner4_pct"], bins=POSITION_BINS, labels=POSITION_LABELS, include_lowest=True).astype("object")
    out["position_band"] = out["position_band"].fillna("unknown")
    out["surface_norm"] = out[surface_col].map(normalize_surface)
    out["distance_band"] = out[distance_col].map(distance_band)
    out["going_norm"] = out[going_col].map(normalize_going) if going_col in out.columns else "unknown"
    out["raw_close_index"] = (100 + 10 * out["raw_close_z"]).clip(70, 130)
    return out


def _means_with_min_count(df: pd.DataFrame, group_cols: Iterable[str], value_col: str, min_count: int) -> Dict[Tuple[str, ...], float]:
    stats = df.groupby(list(group_cols), dropna=False)[value_col].agg(["mean", "count"]).reset_index()
    stats = stats[stats["count"] >= min_count]
    result: Dict[Tuple[str, ...], float] = {}
    for row in stats.itertuples(index=False):
        values = tuple(str(getattr(row, c)) for c in group_cols)
        result[values] = float(row.mean)
    return result


def fit_position_adjustment(train_df: pd.DataFrame, value_col: str = "raw_close_z", min_exact_count: int = 300, min_fallback_count: int = 500) -> PositionAdjustmentModel:
    valid = train_df[train_df[value_col].notna() & train_df["position_band"].notna() & (train_df["position_band"] != "unknown") & train_df["surface_norm"].isin(["turf", "dirt"])].copy()
    if valid.empty:
        raise ValueError("No valid rows to fit position adjustment")
    exact = _means_with_min_count(valid, ["surface_norm", "distance_band", "position_band"], value_col, min_exact_count)
    surface_position = _means_with_min_count(valid, ["surface_norm", "position_band"], value_col, min_fallback_count)
    pos_stats = valid.groupby("position_band")[value_col].agg(["mean", "count"]).reset_index()
    position_only = {str(r.position_band): float(r.mean) for r in pos_stats.itertuples(index=False) if int(r.count) >= min_fallback_count}
    return PositionAdjustmentModel(exact=exact, surface_position=surface_position, position_only=position_only, global_mean=float(valid[value_col].mean()))


def expected_position_z(row: pd.Series, model: PositionAdjustmentModel) -> float:
    exact_key = (str(row["surface_norm"]), str(row["distance_band"]), str(row["position_band"]))
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
    out["expected_position_z"] = out.apply(expected_position_z, axis=1, model=model)
    out["adjusted_close_z"] = out["raw_close_z"] - out["expected_position_z"]
    out["aci"] = (100 + 10 * out["adjusted_close_z"]).clip(70, 130)
    return out


def _closing_edge_table(df: pd.DataFrame, group_cols: list[str], min_rows: int, min_races: int) -> Dict[Tuple[str, ...], float]:
    rows = []
    for key, g in df.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        top3 = g[g["着順"] <= 3]["adjusted_close_z"].dropna()
        others = g[g["着順"] > 3]["adjusted_close_z"].dropna()
        if len(g) < min_rows or g["レースID"].nunique() < min_races or len(top3) < 30 or len(others) < 60:
            continue
        rows.append((tuple(str(v) for v in key), float(top3.mean() - others.mean())))
    return dict(rows)


def fit_demand_profile(train_df: pd.DataFrame, venue_col: str = "競馬場名", min_exact_rows: int = 700, min_exact_races: int = 45) -> DemandProfileModel:
    valid = train_df[train_df["adjusted_close_z"].notna() & train_df["着順"].notna() & train_df["surface_norm"].isin(["turf", "dirt"]) & train_df[venue_col].notna()].copy()
    if valid.empty:
        raise ValueError("No valid rows to fit demand profile")
    exact = _closing_edge_table(valid, [venue_col, "surface_norm", "distance_band", "going_norm"], min_exact_rows, min_exact_races)
    course_fallback = _closing_edge_table(valid, [venue_col, "surface_norm", "distance_band"], min_exact_rows, min_exact_races)
    surface_distance_going = _closing_edge_table(valid, ["surface_norm", "distance_band", "going_norm"], 1000, 70)
    surface_distance = _closing_edge_table(valid, ["surface_norm", "distance_band"], 1500, 100)
    top3 = valid[valid["着順"] <= 3]["adjusted_close_z"]
    others = valid[valid["着順"] > 3]["adjusted_close_z"]
    global_edge = float(top3.mean() - others.mean())
    threshold_source = np.array(list(course_fallback.values()), dtype=float)
    if len(threshold_source) < 6:
        threshold_source = np.array(list(surface_distance_going.values()), dtype=float)
    if len(threshold_source) < 3:
        low, high = global_edge * 0.85, global_edge * 1.15
    else:
        low, high = np.quantile(threshold_source, [1 / 3, 2 / 3])
    return DemandProfileModel(exact=exact, course_fallback=course_fallback, surface_distance_going=surface_distance_going, surface_distance=surface_distance, global_edge=global_edge, low_threshold=float(low), high_threshold=float(high))


def demand_edge_for_row(row: pd.Series, model: DemandProfileModel, venue_col: str = "競馬場名") -> float:
    exact_key = (str(row.get(venue_col, "unknown")), str(row["surface_norm"]), str(row["distance_band"]), str(row["going_norm"]))
    if exact_key in model.exact:
        return model.exact[exact_key]
    course_key = exact_key[:3]
    if course_key in model.course_fallback:
        return model.course_fallback[course_key]
    sdg_key = (exact_key[1], exact_key[2], exact_key[3])
    if sdg_key in model.surface_distance_going:
        return model.surface_distance_going[sdg_key]
    sd_key = (exact_key[1], exact_key[2])
    if sd_key in model.surface_distance:
        return model.surface_distance[sd_key]
    return model.global_edge


def demand_type_from_edge(edge: float, model: DemandProfileModel) -> str:
    if edge <= model.low_threshold:
        return "sustained_position"
    if edge >= model.high_threshold:
        return "sharp_closing"
    return "balanced"


def apply_demand_profile(df: pd.DataFrame, model: DemandProfileModel, venue_col: str = "競馬場名") -> pd.DataFrame:
    out = df.copy()
    out["closing_reliance_edge"] = out.apply(demand_edge_for_row, axis=1, model=model, venue_col=venue_col)
    out["demand_type"] = out["closing_reliance_edge"].map(lambda v: demand_type_from_edge(float(v), model))
    return out


def add_prior_features(df: pd.DataFrame, horse_col: str = "馬名", date_col: str = "レース日付", race_col: str = "レースID", last3f_col: str = "上り") -> pd.DataFrame:
    out = df.sort_values([horse_col, date_col, race_col]).copy()
    grouped = out.groupby(horse_col, sort=False)
    out["prev_last3f"] = grouped[last3f_col].shift(1)
    out["prev_raw_close_z"] = grouped["raw_close_z"].shift(1)
    out["prev_aci"] = grouped["aci"].shift(1)
    out["prev3_aci_median"] = grouped["aci"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).median())
    out["prev6_aci_peak"] = grouped["aci"].transform(lambda s: s.shift(1).rolling(6, min_periods=1).max())
    out["prev6_aci_mad"] = grouped["aci"].transform(lambda s: s.shift(1).rolling(6, min_periods=2).apply(_rolling_mad, raw=True))
    out["prior_valid_starts"] = grouped["aci"].transform(lambda s: s.shift(1).notna().cumsum())
    if "demand_type" in out.columns:
        same = out.groupby([horse_col, "demand_type"], sort=False)
        out["prev_same_demand_aci"] = same["aci"].shift(1)
        out["prev3_same_demand_aci_median"] = same["aci"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).median())
        out["prev6_same_demand_aci_mad"] = same["aci"].transform(lambda s: s.shift(1).rolling(6, min_periods=2).apply(_rolling_mad, raw=True))
        out["prior_same_demand_starts"] = same["aci"].transform(lambda s: s.shift(1).notna().cumsum())
        use_same = out["prior_same_demand_starts"] >= 2
        out["demand_fit_aci"] = np.where(use_same, out["prev3_same_demand_aci_median"], out["prev3_aci_median"])
        out["reproducibility_mad"] = np.where(out["prior_same_demand_starts"] >= 3, out["prev6_same_demand_aci_mad"], out["prev6_aci_mad"])
    else:
        out["prev_same_demand_aci"] = np.nan
        out["prev3_same_demand_aci_median"] = np.nan
        out["prev6_same_demand_aci_mad"] = np.nan
        out["prior_same_demand_starts"] = 0
        out["demand_fit_aci"] = out["prev3_aci_median"]
        out["reproducibility_mad"] = out["prev6_aci_mad"]
    out["reproducibility_score"] = (100.0 * np.exp(-out["reproducibility_mad"].fillna(12.0) / 12.0)).clip(0, 100)
    out["aci_v11_confidence_score"] = out["demand_fit_aci"] - 0.15 * out["reproducibility_mad"].fillna(8.0)
    return out
