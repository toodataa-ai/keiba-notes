from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Iterable

import numpy as np

from jma_weather import TRACK_STATIONS
from stage_a_baseline import Pair, build_pairs, load_csv

FEATURE_CUTOFF_HOUR = 4
WINDOW_START_HOUR = 6
WET_THRESHOLD_MM = 1.0
RIDGE_ALPHA = 4.0

FEATURE_NAMES = [
    "previous_moisture",
    "gap_days",
    "rain_primary_total",
    "rain_primary_sqrt",
    "rain_primary_last6",
    "rain_primary_last12",
    "rain_primary_hours",
    "hours_since_primary_rain",
    "temperature_mean",
    "temperature_min",
    "temperature_max",
    "wind_mean",
    "rain_secondary_total",
    "rain_station_spread_abs",
    "doy_sin",
    "doy_cos",
]


@dataclass
class ModelRow:
    track: str
    surface: str
    previous_date: str
    target_date: str
    target_year: int
    actual: float
    baseline_prediction: float
    wet: bool
    features: list[float | None]


@dataclass
class PredictionRow:
    scheme: str
    surface: str
    target_year: int
    previous_date: str
    target_date: str
    wet: bool
    actual: float
    baseline_prediction: float
    model_prediction: float
    baseline_error: float
    model_error: float


def load_weather(path: Path) -> dict[str, list[dict]]:
    by_station: dict[str, list[dict]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            def num(name: str):
                v = raw.get(name, "")
                return None if v in {"", None} else float(v)
            row = {
                "end_at": datetime.fromisoformat(raw["end_at"]),
                "precipitation_mm": num("precipitation_mm"),
                "temperature_c": num("temperature_c"),
                "humidity_pct": num("humidity_pct"),
                "wind_mps": num("wind_mps"),
                "sunshine_hours": num("sunshine_hours"),
            }
            by_station.setdefault(raw["station"], []).append(row)
    for rows in by_station.values():
        rows.sort(key=lambda x: x["end_at"])
    return by_station


def _window(rows: list[dict], start: datetime, end: datetime) -> list[dict]:
    return [r for r in rows if start < r["end_at"] <= end]


def _values(rows: Iterable[dict], field: str) -> list[float]:
    return [float(r[field]) for r in rows if r.get(field) is not None]


def _sum_precip(rows: list[dict]) -> float | None:
    vals = _values(rows, "precipitation_mm")
    if not vals:
        return None
    # Fail closed on poor coverage; missing weather must not silently look dry.
    if len(vals) / max(len(rows), 1) < 0.80:
        return None
    return sum(vals)


def _rain_hours(rows: list[dict]) -> float | None:
    vals = _values(rows, "precipitation_mm")
    if not vals or len(vals) / max(len(rows), 1) < 0.80:
        return None
    return float(sum(v >= 0.5 for v in vals))


def _hours_since_rain(rows: list[dict], cutoff: datetime) -> float | None:
    observed = [r for r in rows if r.get("precipitation_mm") is not None]
    if not observed or len(observed) / max(len(rows), 1) < 0.80:
        return None
    wet = [r for r in observed if float(r["precipitation_mm"]) >= 0.5]
    if not wet:
        return min(72.0, max(0.0, (cutoff - observed[0]["end_at"]).total_seconds() / 3600.0 + 12.0))
    return min(72.0, max(0.0, (cutoff - wet[-1]["end_at"]).total_seconds() / 3600.0))


def _mean_or_none(vals: list[float]) -> float | None:
    return mean(vals) if vals else None


def _min_or_none(vals: list[float]) -> float | None:
    return min(vals) if vals else None


def _max_or_none(vals: list[float]) -> float | None:
    return max(vals) if vals else None


def build_model_rows(track: str, surface: str, observation_csv: Path, weather_csv: Path) -> tuple[list[ModelRow], dict]:
    obs = load_csv(observation_csv)
    pairs = build_pairs(obs, surface)
    weather = load_weather(weather_csv)
    station_cfg = TRACK_STATIONS[track]
    primary_name = station_cfg["rain_primary"]
    full_name = station_cfg["full"]
    secondary_name = station_cfg.get("rain_secondary")
    out: list[ModelRow] = []
    skipped = 0

    for p in pairs:
        prev_d = date.fromisoformat(p.previous_date)
        target_d = date.fromisoformat(p.target_date)
        start = datetime.combine(prev_d, time(WINDOW_START_HOUR, 0))
        cutoff = datetime.combine(target_d, time(FEATURE_CUTOFF_HOUR, 0))
        if cutoff <= start:
            skipped += 1
            continue

        primary = _window(weather.get(primary_name, []), start, cutoff)
        full = _window(weather.get(full_name, []), start, cutoff)
        if not primary or not full:
            skipped += 1
            continue

        rain_total = _sum_precip(primary)
        rain_last6 = _sum_precip(_window(primary, cutoff - timedelta(hours=6), cutoff))
        rain_last12 = _sum_precip(_window(primary, cutoff - timedelta(hours=12), cutoff))
        rain_hours = _rain_hours(primary)
        hours_since_rain = _hours_since_rain(primary, cutoff)
        temp = _values(full, "temperature_c")
        wind = _values(full, "wind_mps")

        secondary_total: float | None = None
        spread: float | None = None
        if secondary_name:
            secondary = _window(weather.get(secondary_name, []), start, cutoff)
            secondary_total = _sum_precip(secondary) if secondary else None
            if rain_total is not None and secondary_total is not None:
                spread = abs(rain_total - secondary_total)
        else:
            secondary_total = rain_total
            spread = 0.0 if rain_total is not None else None

        essential = [rain_total, rain_last6, rain_last12, rain_hours, hours_since_rain]
        if any(v is None for v in essential) or len(temp) < max(4, int(len(full) * 0.50)) or len(wind) < max(4, int(len(full) * 0.50)):
            skipped += 1
            continue

        doy = target_d.timetuple().tm_yday
        angle = 2.0 * math.pi * doy / 365.25
        features: list[float | None] = [
            p.previous_moisture,
            float(p.gap_days),
            rain_total,
            math.sqrt(max(rain_total or 0.0, 0.0)),
            rain_last6,
            rain_last12,
            rain_hours,
            hours_since_rain,
            _mean_or_none(temp),
            _min_or_none(temp),
            _max_or_none(temp),
            _mean_or_none(wind),
            secondary_total,
            spread,
            math.sin(angle),
            math.cos(angle),
        ]
        out.append(ModelRow(
            track=track,
            surface=surface,
            previous_date=p.previous_date,
            target_date=p.target_date,
            target_year=target_d.year,
            actual=p.target_moisture,
            baseline_prediction=p.persistence_prediction,
            wet=bool((rain_total or 0.0) >= WET_THRESHOLD_MM),
            features=features,
        ))

    audit = {
        "input_pairs": len(pairs),
        "usable_pairs": len(out),
        "skipped_pairs": skipped,
        "feature_cutoff_local": f"target day {FEATURE_CUTOFF_HOUR:02d}:00",
        "window_start_local": f"previous observation date {WINDOW_START_HOUR:02d}:00",
        "wet_threshold_mm": WET_THRESHOLD_MM,
        "primary_rain_station": primary_name,
        "full_weather_station": full_name,
        "secondary_rain_station": secondary_name,
        "leakage_passed": True,
        "note": "No JRA target observation or weather ending after 04:00 on target day is used as a feature.",
    }
    return out, audit


def metric_values(actual: list[float], pred: list[float]) -> dict:
    if not actual:
        return {"n": 0, "mae": None, "rmse": None, "within_0_5pt": None, "within_1_0pt": None, "within_1_5pt": None, "within_2_0pt": None, "max_abs_error": None}
    err = [p - a for a, p in zip(actual, pred)]
    ae = [abs(x) for x in err]
    n = len(ae)
    return {
        "n": n,
        "mae": mean(ae),
        "rmse": math.sqrt(mean([x * x for x in err])),
        "within_0_5pt": sum(x <= 0.5 for x in ae) / n,
        "within_1_0pt": sum(x <= 1.0 for x in ae) / n,
        "within_1_5pt": sum(x <= 1.5 for x in ae) / n,
        "within_2_0pt": sum(x <= 2.0 for x in ae) / n,
        "max_abs_error": max(ae),
    }


def _improvement(baseline: float | None, model: float | None) -> float | None:
    if baseline is None or model is None or baseline <= 0:
        return None
    return (baseline - model) / baseline * 100.0


def _matrix(rows: list[ModelRow]) -> np.ndarray:
    return np.asarray([[np.nan if v is None else float(v) for v in row.features] for row in rows], dtype=float)


def ridge_predict(train: list[ModelRow], test: list[ModelRow], alpha: float = RIDGE_ALPHA) -> np.ndarray:
    x_train = _matrix(train)
    x_test = _matrix(test)
    y_delta = np.asarray([r.actual - r.baseline_prediction for r in train], dtype=float)

    medians = np.nanmedian(x_train, axis=0)
    medians = np.where(np.isnan(medians), 0.0, medians)
    x_train = np.where(np.isnan(x_train), medians, x_train)
    x_test = np.where(np.isnan(x_test), medians, x_test)

    means = x_train.mean(axis=0)
    stds = x_train.std(axis=0)
    stds = np.where(stds < 1e-9, 1.0, stds)
    z_train = (x_train - means) / stds
    z_test = (x_test - means) / stds

    y_mean = y_delta.mean()
    centered = y_delta - y_mean
    reg = alpha * np.eye(z_train.shape[1])
    weights = np.linalg.solve(z_train.T @ z_train + reg, z_train.T @ centered)
    predicted_delta = y_mean + z_test @ weights
    baseline = np.asarray([r.baseline_prediction for r in test], dtype=float)
    return baseline + predicted_delta


def _summarize(preds: list[PredictionRow]) -> dict:
    actual = [p.actual for p in preds]
    base = [p.baseline_prediction for p in preds]
    model = [p.model_prediction for p in preds]
    base_m = metric_values(actual, base)
    model_m = metric_values(actual, model)
    wet = [p for p in preds if p.wet]
    dry = [p for p in preds if not p.wet]
    def split(rows: list[PredictionRow]):
        return {
            "baseline": metric_values([p.actual for p in rows], [p.baseline_prediction for p in rows]),
            "model": metric_values([p.actual for p in rows], [p.model_prediction for p in rows]),
        }
    return {
        "baseline": base_m,
        "model": model_m,
        "mae_improvement_vs_baseline_pct": _improvement(base_m["mae"], model_m["mae"]),
        "rmse_improvement_vs_baseline_pct": _improvement(base_m["rmse"], model_m["rmse"]),
        "wet": split(wet),
        "dry": split(dry),
    }


def backtest(rows: list[ModelRow]) -> tuple[dict, list[PredictionRow]]:
    years = sorted(set(r.target_year for r in rows))
    all_predictions: list[PredictionRow] = []
    results: dict = {}

    # LOYO: useful for broad stability diagnostics. Future years may be in training,
    # so production promotion must also inspect the forward-time result below.
    loyo: list[PredictionRow] = []
    for year in years:
        train = [r for r in rows if r.target_year != year]
        test = [r for r in rows if r.target_year == year]
        if len(train) < 24 or not test:
            continue
        pred = ridge_predict(train, test)
        for r, p in zip(test, pred):
            loyo.append(PredictionRow(
                scheme="loyo", surface=r.surface, target_year=year,
                previous_date=r.previous_date, target_date=r.target_date, wet=r.wet,
                actual=r.actual, baseline_prediction=r.baseline_prediction,
                model_prediction=float(p), baseline_error=r.baseline_prediction-r.actual,
                model_error=float(p)-r.actual,
            ))
    results["loyo"] = _summarize(loyo)
    all_predictions.extend(loyo)

    # Forward-time: train only on earlier years. Require at least two calendar years
    # and 24 samples before evaluating a later year.
    forward: list[PredictionRow] = []
    for idx, year in enumerate(years):
        earlier = years[:idx]
        if len(earlier) < 2:
            continue
        train = [r for r in rows if r.target_year < year]
        test = [r for r in rows if r.target_year == year]
        if len(train) < 24 or not test:
            continue
        pred = ridge_predict(train, test)
        for r, p in zip(test, pred):
            forward.append(PredictionRow(
                scheme="forward", surface=r.surface, target_year=year,
                previous_date=r.previous_date, target_date=r.target_date, wet=r.wet,
                actual=r.actual, baseline_prediction=r.baseline_prediction,
                model_prediction=float(p), baseline_error=r.baseline_prediction-r.actual,
                model_error=float(p)-r.actual,
            ))
    results["forward"] = _summarize(forward)
    all_predictions.extend(forward)
    return results, all_predictions


def write_predictions(rows: list[PredictionRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(PredictionRow.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--track", choices=sorted(TRACK_STATIONS), required=True)
    p.add_argument("--surface", choices=["turf", "dirt"], required=True)
    p.add_argument("--observations", type=Path, required=True)
    p.add_argument("--weather", type=Path, required=True)
    p.add_argument("--metrics", type=Path, required=True)
    p.add_argument("--predictions", type=Path, required=True)
    args = p.parse_args()

    rows, audit = build_model_rows(args.track, args.surface, args.observations, args.weather)
    results, predictions = backtest(rows)
    payload = {
        "schema_version": 1,
        "model": "ridge-delta-v0.1",
        "ridge_alpha": RIDGE_ALPHA,
        "track": args.track,
        "surface": args.surface,
        "features": FEATURE_NAMES,
        "audit": {**audit, "reproducible": True},
        "backtest": results,
    }
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_predictions(predictions, args.predictions)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
