"""Collect bounded 2026 Tokyo/Kyoto official morning evidence for Stage B replay.

Research only: writes artifacts, not forecasts, racing results or production registry.
Any upstream failures are reported in the acquisition audit, not replaced by guesses.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

import requests

from jma_weather import TRACK_STATIONS, collect as _unused_weather_collect, fetch_day, write_csv as write_weather
from jra_observations import collect as collect_jra, write_csv as write_jra, Observation
from stage_b_tokyo_kyoto_v1 import load_csv, REQUIRED_LABEL_FIELDS


def needed_jobs(labels: list[dict]) -> tuple[dict[str, set[date]], list[tuple[str, date]]]:
    days = {"tokyo": set(), "kyoto": set()}
    weather = set()
    for r in labels:
        track = r["track"]
        if track not in days:
            continue
        d = date.fromisoformat(r["race_date"])
        if d.year != 2026:
            raise ValueError("this bounded acquisition script is only for 2026 evidence")
        days[track].add(d)
        for station in (TRACK_STATIONS[track]["rain_primary"], TRACK_STATIONS[track]["full"]):
            weather.add((station, d))
    return days, sorted(weather)


def collect(labels: list[dict], outdir: Path) -> dict:
    days, jobs = needed_jobs(labels)
    outdir.mkdir(parents=True, exist_ok=True)
    all_jra: list[Observation] = []
    all_weather = []
    blockers: list[str] = []
    for track in ("tokyo", "kyoto"):
        try:
            official_rows = collect_jra([2026], track)
            selected = [r for r in official_rows if
                        date.fromisoformat(r.observed_date) in days[track] and r.race_day]
            all_jra.extend(selected)
            present = {date.fromisoformat(r.observed_date) for r in selected if r.moisture_time}
            for missing in sorted(days[track] - present):
                blockers.append(f"{track}/{missing}: timed JRA morning observation missing")
        except Exception as exc:
            blockers.append(f"{track}: JRA archive unavailable or parsing failed: {type(exc).__name__}: {exc}")
    write_jra(all_jra, outdir / "jra_morning.csv")

    for station, d in jobs:
        try:
            with requests.Session() as session:
                all_weather.extend(fetch_day(session, station, d, retries=2))
        except Exception as exc:
            blockers.append(f"{station}/{d}: JMA hourly unavailable: {type(exc).__name__}: {exc}")
    write_weather(all_weather, outdir / "jma_hourly.csv")

    audit = {
        "status": "retrospective_source_collection_no_production_changes",
        "target_tracks": ["tokyo", "kyoto"],
        "target_days": {k: sorted(d.isoformat() for d in ds) for k, ds in days.items()},
        "jra_observation_rows": len(all_jra),
        "jra_timed_race_day_rows": sum(bool(r.moisture_time) for r in all_jra),
        "jma_hourly_rows": len(all_weather),
        "jma_station_day_jobs": len(jobs),
        "blocked_sources": blockers,
        "accuracy_claim": "none; evaluate only eligible pairs and retain all exclusions",
        "feature_published_before_post_verified": False,
    }
    (outdir / "acquisition_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))
    return audit


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    args = p.parse_args()
    collect(load_csv(args.labels, REQUIRED_LABEL_FIELDS), args.outdir)


if __name__ == "__main__":
    main()
