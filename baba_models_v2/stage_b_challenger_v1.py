"""Time-forward, four-model-only Stage B temperature calibration research.

A one-parameter challenger of the *existing* operational Stage B probabilities.
Evaluates on genuinely later whole calendar years, never the training year.
NOT an approved probability model and never a formal STEP1/STEP2 dependency.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from stage_b_tokyo_kyoto_v1 import CLASSES, STATIONS, norm_probs, score

TEMPERATURES = (0.5, 0.65, 0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 3.0)
MIN_TRAIN_RACES = 24
MIN_TRAIN_DAYS = 8
MIN_TEST_RACES = 5


def adjusted(probs: dict[str, float], temperature: float) -> dict[str, float]:
    """Positive probabilities only, preserving labels without race-outcome leakage."""
    if temperature <= 0 or not math.isfinite(temperature):
        raise ValueError("invalid calibration temperature")
    p = norm_probs(probs)
    raw = {k: max(p[k], 1e-12) ** (1.0 / temperature) for k in CLASSES}
    return norm_probs(raw)


def _log_loss(records: list[dict], temperature: float) -> float:
    return sum(-math.log(max(adjusted(r["existing_pilot"], temperature)[r["official_condition"]], 1e-12))
               for r in records) / len(records)


def fit_temperature(train: list[dict]) -> float:
    """Fit only on preceding-year truth; ties choose the unmodified model."""
    if not train:
        raise ValueError("empty training data")
    return min(TEMPERATURES, key=lambda t: (round(_log_loss(train, t), 12), abs(t - 1.0)))


def evaluate(replay: dict) -> dict:
    if replay.get("status") != "retrospective_research_only":
        raise ValueError("input must be non-production retrospective replay")
    if replay.get("production_router_changed") is not False:
        raise ValueError("research input cannot alter production routing")
    rows = replay.get("race_audit")
    if not isinstance(rows, list):
        raise ValueError("race audit absent")

    by_model = defaultdict(list)
    ids = set()
    for r in rows:
        rid = r["race_id"]
        if not rid or rid in ids:
            raise ValueError("duplicate/empty race ID")
        ids.add(rid)
        key = (r["track"], r["surface"])
        if r["track"] not in STATIONS or r["surface"] not in ("turf", "dirt"):
            raise ValueError("unsupported track")
        if r["official_condition"] not in CLASSES:
            raise ValueError("invalid official label")
        norm_probs(r["existing_pilot"])
        by_model[key].append(r)

    results = {}
    for track in STATIONS:
        for surface in ("turf", "dirt"):
            data = sorted(by_model[(track, surface)], key=lambda r: (r["date"], r["race_id"]))
            years = sorted({r["date"][:4] for r in data})
            folds, predictions, blockers = [], [], []
            for year in years[1:]:
                train = [r for r in data if r["date"][:4] < year]
                test = [r for r in data if r["date"][:4] == year]
                # At least 24 independent race examples and 8 distinct days in
                # preceding years. No train/test intersection even within dates.
                if (len(train) < MIN_TRAIN_RACES or
                    len({r["date"] for r in train}) < MIN_TRAIN_DAYS or
                    len(test) < MIN_TEST_RACES):
                    blockers.append(f"{year}:insufficient_prior_train_or_holdout_samples")
                    continue
                temperature = fit_temperature(train)
                for r in test:
                    predictions.append({
                        "race_id": r["race_id"], "date": r["date"],
                        "official_condition": r["official_condition"],
                        "existing_pilot": r["existing_pilot"],
                        "challenger": adjusted(r["existing_pilot"], temperature),
                    })
                folds.append({
                    "held_out_year": year,
                    "max_train_date": max(r["date"] for r in train),
                    "min_test_date": min(r["date"] for r in test),
                    "train_races": len(train), "train_days": len({r["date"] for r in train}),
                    "test_races": len(test), "temperature": temperature,
                    "temporal_leakage": False,
                })
            if not folds:
                blockers.append("No qualifying forward-time held-out year")
            b, c = score(predictions, "existing_pilot"), score(predictions, "challenger")
            results[f"{track}_{surface}"] = {
                "eligible_races": len(data), "years": years, "forward_folds": folds,
                "paired_test_races": len(predictions),
                "baseline_metrics": b, "challenger_metrics": c,
                "paired_log_loss_improvement_pct": None if not b or b["multiclass_log_loss"] == 0 else
                    round(100 * (b["multiclass_log_loss"] - c["multiclass_log_loss"]) / b["multiclass_log_loss"], 3),
                "paired_brier_improvement_pct": None if not b or b["brier_score"] == 0 else
                    round(100 * (b["brier_score"] - c["brier_score"]) / b["brier_score"], 3),
                "insufficient_evidence": blockers,
                "ready_for_candidate": False,
                "ready_for_production": False,
            }
    return {
        "schema_version": 1, "status": "forward_time_research_only",
        "method": "stage_b_temperature_scaling_v1",
        "source_replay_status": replay["status"],
        "historical_publication_availability_verified": False,
        "models": results,
        "promotion_allowed": False,
        "reason": ("Research minimums are only for diagnostic folds, not candidate promotion. "
                   "Published-before-post evidence and the 80-label Stage B policy still apply."),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--replay", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    obj = json.loads(args.replay.read_text(encoding="utf-8"))
    output = evaluate(obj)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: {"paired_test_races": v["paired_test_races"],
                          "blockers": v["insufficient_evidence"]}
                      for k, v in output["models"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
