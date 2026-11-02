#!/usr/bin/env python3
"""Read-only prestart Stage B pilot capture for Tokyo/Kyoto (NOT full STEP1).

Output is a study sidecar only. Never counts toward formal paired Grade A races.
Never changes the formal prompt, bets, reviews or canonical web data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from baba_models_v2.predict import update_to_race_time

ALLOWED_TRACKS = {"tokyo", "kyoto"}
ALLOWED_SURFACES = {"turf", "dirt"}


def utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("time must be ISO8601 with a timezone")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("timezone required on all timestamps")
    return d.astimezone(timezone.utc)


def finite_number(value, key: str) -> float:
    import math
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric, not guessed text")
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return float(value)


def capture(payload: dict, *, now: datetime | None = None) -> dict:
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    race_id = payload.get("race_id")
    if not isinstance(race_id, str) or not race_id.strip():
        raise ValueError("race_id required")
    track, surface = payload.get("track"), payload.get("surface")
    if track not in ALLOWED_TRACKS or surface not in ALLOWED_SURFACES:
        raise ValueError("Tokyo/Kyoto turf/dirt only; no cross-track substitution")
    start = utc(payload["scheduled_start_at"])
    cutoff = utc(payload["information_cutoff_at"])
    measured = utc(payload["morning_moisture_observed_at"])
    weather = payload["weather"]
    weather_until = utc(weather["observed_through_at"])
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not (measured <= cutoff and weather_until <= cutoff <= instant < start):
        raise ValueError("data/cutoff/run must precede official start; no postrace fill")
    for key in ("jra_moisture_source_url",):
        if not str(payload.get(key, "")).startswith("https://www.jra.go.jp/"):
            raise ValueError("official JRA moisture source URL required")
    if not str(weather.get("source_url", "")).startswith(("https://www.data.jma.go.jp/", "https://www.jma.go.jp/")):
        raise ValueError("official JMA weather source URL required")
    moisture = finite_number(payload["morning_moisture"], "morning_moisture")
    if moisture < 0:
        raise ValueError("moisture cannot be negative")
    rain = finite_number(weather["rain_after_measurement_mm"], "rain_after_measurement_mm")
    hours = finite_number(weather["hours_since_last_rain"], "hours_since_last_rain")
    temp = finite_number(weather["temperature_c"], "temperature_c")
    wind = finite_number(weather["wind_mps"], "wind_mps")
    sun = finite_number(weather["sunshine_hours"], "sunshine_hours")
    target = finite_number(weather["elapsed_hours_since_measurement"], "elapsed_hours_since_measurement")
    if min(rain, hours, wind, sun, target) < 0:
        raise ValueError("rain, elapsed hours, wind, sunshine must be nonnegative")
    if target > (cutoff - measured).total_seconds() / 3600 + 0.001:
        raise ValueError("elapsed_hours_since_measurement extends beyond cutoff")
    result = update_to_race_time(
        track, surface, moisture, rain_after_measurement_mm=rain,
        hours_since_last_rain=hours, temperature_c=temp,
        wind_mps=wind, sunshine_hours=sun, target_hours=target)
    if result.get("legacy_model_replaced") is not False:
        raise ValueError("pilot must never replace formal model")
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return {
        "schema_version": 1,
        "race_id": race_id,
        "candidate": "v3.13-tokyo-kyoto-track-condition-shadow-v0.1",
        "study_stage": "stage_b_pilot_features_only",
        "not_full_step1_prediction": True,
        "counts_toward_formal_new_old_pairs": False,
        "grade_a_formal_pair": False,
        "proof_commit": None,
        "information_cutoff_at": payload["information_cutoff_at"],
        "captured_at": instant.isoformat(),
        "input_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "prediction": result
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing capture")
    record = json.loads(args.input.read_text(encoding="utf-8"))
    result = capture(record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE_STAGE_B_PILOT_ONLY {args.output}")


if __name__ == "__main__":
    main()
