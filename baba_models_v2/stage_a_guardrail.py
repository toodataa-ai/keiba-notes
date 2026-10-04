from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from stage_a_weather_model import PredictionRow, metric_values


def load_predictions(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            rows.append({
                **raw,
                "target_year": int(raw["target_year"]),
                "wet": raw["wet"].lower() == "true",
                "actual": float(raw["actual"]),
                "baseline_prediction": float(raw["baseline_prediction"]),
                "model_prediction": float(raw["model_prediction"]),
            })
    return rows


def _summarize(rows: list[dict]) -> dict:
    def one(part: list[dict]):
        return {
            "baseline": metric_values([r["actual"] for r in part], [r["baseline_prediction"] for r in part]),
            "raw_model": metric_values([r["actual"] for r in part], [r["model_prediction"] for r in part]),
            "guarded_model": metric_values([r["actual"] for r in part], [r["guarded_prediction"] for r in part]),
        }
    return {
        "all": one(rows),
        "wet": one([r for r in rows if r["wet"]]),
        "dry": one([r for r in rows if not r["wet"]]),
        "guardrail_applied": sum(r["guardrail_applied"] for r in rows),
    }


def apply_guard(rows: list[dict]) -> tuple[list[dict], dict]:
    # LOYO rows contain one actual for every target pair and therefore provide the
    # complete target history needed to reconstruct each fold's training envelope.
    actual_by_year: dict[int, list[float]] = {}
    for r in rows:
        if r["scheme"] == "loyo":
            actual_by_year.setdefault(r["target_year"], []).append(r["actual"])

    guarded: list[dict] = []
    for r in rows:
        year = r["target_year"]
        if r["scheme"] == "forward":
            train_actual = [v for y, values in actual_by_year.items() if y < year for v in values]
        elif r["scheme"] == "loyo":
            train_actual = [v for y, values in actual_by_year.items() if y != year for v in values]
        else:
            continue
        if not train_actual:
            continue
        lower, upper = min(train_actual), max(train_actual)
        raw = r["model_prediction"]
        clipped = min(max(raw, lower), upper)
        guarded.append({
            **r,
            "training_target_min": lower,
            "training_target_max": upper,
            "guarded_prediction": clipped,
            "guardrail_applied": clipped != raw,
            "guarded_error": clipped - r["actual"],
        })

    metrics = {
        "guardrail": "clip prediction to min/max target moisture observed in that fold's training data",
        "no_test_target_used_for_guard": True,
        "forward": _summarize([r for r in guarded if r["scheme"] == "forward"]),
        "loyo": _summarize([r for r in guarded if r["scheme"] == "loyo"]),
    }
    return guarded, metrics


def write_rows(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "scheme", "surface", "target_year", "previous_date", "target_date", "wet",
        "actual", "baseline_prediction", "model_prediction", "training_target_min",
        "training_target_max", "guarded_prediction", "guardrail_applied", "guarded_error",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--metrics", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    rows = load_predictions(args.input)
    guarded, metrics = apply_guard(rows)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_rows(guarded, args.output)
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
