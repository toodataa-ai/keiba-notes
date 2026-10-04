from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--track", required=True)
    p.add_argument("--min-rows", type=int, default=1)
    p.add_argument("--min-race-days", type=int, default=1)
    args = p.parse_args()

    with args.input.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    errors: list[str] = []

    if len(rows) < args.min_rows:
        errors.append(f"rows {len(rows)} < min {args.min_rows}")
    race_days = [r for r in rows if r.get("race_day", "").lower() in {"true", "1"}]
    if len(race_days) < args.min_race_days:
        errors.append(f"race days {len(race_days)} < min {args.min_race_days}")

    keys = [(r.get("track"), r.get("meeting"), r.get("observed_date")) for r in rows]
    dupes = [k for k, n in Counter(keys).items() if n > 1]
    if dupes:
        errors.append(f"duplicate observation keys: {dupes[:5]}")

    years = set()
    formats = set()
    for i, r in enumerate(rows, start=2):
        if r.get("track") != args.track:
            errors.append(f"line {i}: unexpected track {r.get('track')}")
        try:
            d = date.fromisoformat(r["observed_date"])
            years.add(d.year)
        except Exception:
            errors.append(f"line {i}: invalid date {r.get('observed_date')}")
        formats.add(r.get("source_format"))
        for col in ("turf_goal", "turf_corner", "dirt_goal", "dirt_corner"):
            try:
                v = float(r[col])
                if not 0.0 <= v <= 50.0:
                    errors.append(f"line {i}: implausible {col}={v}")
            except Exception:
                errors.append(f"line {i}: invalid {col}={r.get(col)}")
        if r.get("cushion_value") not in {None, ""}:
            try:
                v = float(r["cushion_value"])
                if not 4.0 <= v <= 20.0:
                    errors.append(f"line {i}: implausible cushion_value={v}")
            except Exception:
                errors.append(f"line {i}: invalid cushion_value={r.get('cushion_value')}")

    if errors:
        raise SystemExit("OBSERVATION DATA INVALID:\n- " + "\n- ".join(errors[:30]))

    print(
        f"OBSERVATION DATA OK: track={args.track} rows={len(rows)} "
        f"race_days={len(race_days)} years={sorted(years)} formats={sorted(x for x in formats if x)}"
    )


if __name__ == "__main__":
    main()
