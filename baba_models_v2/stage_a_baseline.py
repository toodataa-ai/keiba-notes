from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from statistics import mean


@dataclass
class Pair:
    track: str
    surface: str
    meeting: int
    previous_date: str
    target_date: str
    gap_days: int
    previous_moisture: float
    target_moisture: float
    persistence_prediction: float
    error: float
    abs_error: float


def avg_moisture(row: dict[str, str], surface: str) -> float:
    if surface == "turf":
        return (float(row["turf_goal"]) + float(row["turf_corner"])) / 2.0
    if surface == "dirt":
        return (float(row["dirt_goal"]) + float(row["dirt_corner"])) / 2.0
    raise ValueError("surface must be turf or dirt")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_pairs(rows: list[dict[str, str]], surface: str) -> list[Pair]:
    ordered = sorted(rows, key=lambda r: (int(r["year"]), int(r["meeting"]), r["observed_date"]))
    by_meeting: dict[tuple[int, int, str], list[dict[str, str]]] = {}
    for row in ordered:
        by_meeting.setdefault((int(row["year"]), int(row["meeting"]), row["track"]), []).append(row)

    pairs: list[Pair] = []
    for (_, meeting, track), group in by_meeting.items():
        group = sorted(group, key=lambda r: r["observed_date"])
        for previous, target in zip(group, group[1:]):
            # Stage A evaluates only a following official race-day observation.
            if target.get("race_day", "").lower() not in {"true", "1"}:
                continue
            d0 = date.fromisoformat(previous["observed_date"])
            d1 = date.fromisoformat(target["observed_date"])
            gap = (d1 - d0).days
            if gap < 1 or gap > 3:
                continue
            prev = avg_moisture(previous, surface)
            actual = avg_moisture(target, surface)
            pred = prev
            err = pred - actual
            pairs.append(Pair(
                track=track, surface=surface, meeting=meeting,
                previous_date=previous["observed_date"], target_date=target["observed_date"], gap_days=gap,
                previous_moisture=round(prev, 4), target_moisture=round(actual, 4),
                persistence_prediction=round(pred, 4), error=round(err, 4), abs_error=round(abs(err), 4),
            ))
    return pairs


def metrics(pairs: list[Pair]) -> dict[str, float | int | None]:
    if not pairs:
        return {"n": 0, "mae": None, "rmse": None, "within_0_5pt": None, "within_1_0pt": None, "within_1_5pt": None, "within_2_0pt": None, "max_abs_error": None}
    errors = [p.error for p in pairs]
    ae = [abs(x) for x in errors]
    n = len(pairs)
    return {
        "n": n,
        "mae": mean(ae),
        "rmse": math.sqrt(mean([x * x for x in errors])),
        "within_0_5pt": sum(x <= 0.5 for x in ae) / n,
        "within_1_0pt": sum(x <= 1.0 for x in ae) / n,
        "within_1_5pt": sum(x <= 1.5 for x in ae) / n,
        "within_2_0pt": sum(x <= 2.0 for x in ae) / n,
        "max_abs_error": max(ae),
    }


def write_pairs(pairs: list[Pair], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(Pair.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in pairs:
            w.writerow(asdict(p))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--surface", choices=["turf", "dirt"], required=True)
    p.add_argument("--metrics", type=Path, required=True)
    p.add_argument("--pairs", type=Path, required=True)
    args = p.parse_args()
    pairs = build_pairs(load_csv(args.input), args.surface)
    result = {"baseline": "previous official observation (persistence)", "surface": args.surface, **metrics(pairs)}
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_pairs(pairs, args.pairs)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
