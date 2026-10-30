"""Tokyo/Kyoto Stage B retrospective evaluation only; never routes into formal JRA predictions.

Inputs are externally verified official race labels, JRA morning observations, and JMA
hourly observations. A retrospective hourly timestamp does NOT establish that a
record was publicly available to a real-time bettor at that timestamp.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from predict import condition_probs, update_to_race_time

CLASSES = ("良", "稍重", "重", "不良")
STATIONS = {
    "tokyo": {"rain": "fuchu", "full": "fuchu"},
    "kyoto": {"rain": "nagaokakyo", "full": "kyotanabe"},
}
REQUIRED_LABEL_FIELDS = (
    "race_id", "track", "surface", "race_date", "post_time_jst",
    "official_condition", "official_result_url", "verified_at_jst",
)
REQUIRED_OBSERVATION_FIELDS = (
    "track", "observed_date", "race_day", "moisture_time",
    "turf_goal", "turf_corner", "dirt_goal", "dirt_corner", "source_url",
)
REQUIRED_WEATHER_FIELDS = (
    "station", "end_at", "precipitation_mm", "temperature_c",
    "wind_mps", "sunshine_hours",
)


def load_csv(path: Path, required: tuple[str, ...]) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        missing = set(required) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns: {sorted(missing)}")
        return list(reader)


def official_jra(url: str) -> bool:
    try:
        u = urlparse(url)
        return u.scheme == "https" and u.hostname in {"www.jra.go.jp", "jra.go.jp", "jra.jp", "www.jra.jp"}
    except ValueError:
        return False


def parse_local(value: str) -> datetime:
    """Require a timezone-free full local timestamp; inputs are documented as JST."""
    dt = datetime.fromisoformat(value.strip())
    if dt.tzinfo is not None:
        raise ValueError("timestamps must be local JST without a UTC offset")
    return dt


def norm_probs(p: dict[str, float]) -> dict[str, float]:
    if set(p) != set(CLASSES) or any(not math.isfinite(p[x]) or p[x] < 0 for x in CLASSES):
        raise ValueError("invalid four-class probability output")
    total = sum(p.values())
    if total <= 0:
        raise ValueError("zero probability")
    return {x: p[x] / total for x in CLASSES}


def score(records: list[dict], key: str) -> dict | None:
    if not records:
        return None
    loss = brier = hits = adjacent = 0.0
    bins: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for row in records:
        probs = row[key]
        truth = row["official_condition"]
        loss -= math.log(max(probs[truth], 1e-12))
        brier += sum((probs[k] - (1 if k == truth else 0)) ** 2 for k in CLASSES)
        best = max(CLASSES, key=lambda k: probs[k])
        hit = int(best == truth)
        hits += hit
        adjacent += int(abs(CLASSES.index(best) - CLASSES.index(truth)) <= 1)
        bins[min(9, int(max(probs.values()) * 10))].append((max(probs.values()), hit))
    n = len(records)
    # Expected calibration error for the maximum-class confidence; 10 fixed bins.
    ece = sum(
        len(v) / n * abs(sum(x[0] for x in v) / len(v) - sum(x[1] for x in v) / len(v))
        for v in bins.values()
    )
    return {
        "n": n, "multiclass_log_loss": round(loss / n, 6),
        "brier_score": round(brier / n, 6),
        "top1_accuracy": round(hits / n, 6),
        "adjacent_class_accuracy": round(adjacent / n, 6),
        "calibration_error": round(ece, 6),
    }


def _number(raw: dict, name: str) -> float | None:
    value = (raw.get(name) or "").strip()
    if value == "":
        return None
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"non-finite {name}")
    return v


def replay(labels: list[dict], observations: list[dict], weather: list[dict]) -> dict:
    anchors: dict[tuple[str, str], dict] = {}
    for row in observations:
        if row["track"] not in STATIONS or row["race_day"].lower() not in {"true", "1"}:
            continue
        key = (row["track"], row["observed_date"])
        if key in anchors:
            raise ValueError(f"ambiguous morning anchor: {key}")
        anchors[key] = row

    by_station: dict[str, list[dict]] = defaultdict(list)
    for row in weather:
        entry = dict(row)
        entry["_end"] = parse_local(row["end_at"])
        by_station[row["station"]].append(entry)
    for rows in by_station.values():
        rows.sort(key=lambda row: row["_end"])

    accepted: list[dict] = []
    rejected = Counter()
    seen: set[str] = set()
    for label in labels:
        rid = label["race_id"].strip()
        if not rid or rid in seen:
            raise ValueError(f"empty/duplicate race ID: {rid!r}")
        seen.add(rid)
        track, surface = label["track"].strip(), label["surface"].strip()
        try:
            if track not in STATIONS or surface not in {"turf", "dirt"}:
                raise ValueError("unsupported_track_or_surface")
            d = date.fromisoformat(label["race_date"])
            if track == "kyoto" and d < date(2023, 4, 22):
                raise ValueError("pre_rebuild_kyoto_regime")
            start = parse_local(f"{d.isoformat()}T{label['post_time_jst'].strip()}")
            verified = parse_local(label["verified_at_jst"])
            if not (datetime.combine(d, datetime.min.time()) + timedelta(hours=9) <= start <=
                    datetime.combine(d, datetime.min.time()) + timedelta(hours=18)):
                raise ValueError("implausible_official_post_time")
            if verified <= start or not official_jra(label["official_result_url"]):
                raise ValueError("missing_postrace_official_evidence")
            truth = label["official_condition"].strip()
            if truth not in CLASSES:
                raise ValueError("unknown_official_condition")
            obs = anchors.get((track, d.isoformat()))
            if obs is None or not obs.get("moisture_time"):
                raise ValueError("missing_timed_morning_JRA_anchor")
            if not official_jra(obs["source_url"]):
                raise ValueError("nonofficial_morning_anchor")
            measured = parse_local(f"{d.isoformat()}T{obs['moisture_time'].strip()}")
            if not datetime.combine(d, datetime.min.time()) <= measured < start:
                raise ValueError("morning_anchor_after_post")
            moisture = (float(obs[f"{surface}_goal"]) + float(obs[f"{surface}_corner"])) / 2
            if not 0 <= moisture <= 50:
                raise ValueError("invalid_morning_moisture")
            # Conservative 1-hour data publication buffer. This is NOT proof of
            # historical online availability, hence no automatic promotion.
            cutoff = start - timedelta(hours=1)
            rain_station = STATIONS[track]["rain"]
            full_station = STATIONS[track]["full"]
            precip_rows = [w for w in by_station.get(rain_station, [])
                           if measured < w["_end"] <= cutoff]
            full_rows = [w for w in by_station.get(full_station, [])
                         if measured < w["_end"] <= cutoff]
            expected_hours = max(1, int((cutoff - measured).total_seconds() / 3600))
            rains = [_number(w, "precipitation_mm") for w in precip_rows]
            if (not rains or any(x is None or x < 0 for x in rains)
                    or len(rains) < max(1, math.ceil(expected_hours * 0.8))):
                raise ValueError("insufficient_prerace_precipitation_coverage")
            temps = [_number(w, "temperature_c") for w in full_rows]
            winds = [_number(w, "wind_mps") for w in full_rows]
            sun = [_number(w, "sunshine_hours") for w in full_rows]
            valid_temp = [v for v in temps if v is not None]
            valid_wind = [v for v in winds if v is not None]
            if (not valid_temp or not valid_wind or
                    len(valid_temp) < max(1, math.ceil(expected_hours * 0.6)) or
                    len(valid_wind) < max(1, math.ceil(expected_hours * 0.6))):
                raise ValueError("insufficient_prerace_weather_coverage")
            rain = sum(rains)
            wet_endings = [w["_end"] for w, mm in zip(precip_rows, rains) if mm >= 0.5]
            since_rain = (start - max(wet_endings)).total_seconds() / 3600 if wet_endings else None
            output = update_to_race_time(
                track, surface, moisture, rain_after_measurement_mm=rain,
                hours_since_last_rain=since_rain,
                temperature_c=sum(valid_temp) / len(valid_temp),
                wind_mps=sum(valid_wind) / len(valid_wind),
                sunshine_hours=sum(v for v in sun if v is not None),
                target_hours=(start - measured).total_seconds() / 3600,
            )
            accepted.append({
                "race_id": rid, "track": track, "surface": surface,
                "date": d.isoformat(), "official_condition": truth,
                "rain_after_anchor_mm": round(rain, 2),
                "rain_transition": rain >= 1.0,
                "baseline": norm_probs(condition_probs(track, surface, moisture)),
                "existing_pilot": norm_probs(output["condition_probs_operational"]),
                "source_url": label["official_result_url"],
                "jra_morning_source_url": obs["source_url"],
                "weather_latest_used_jst": max(
                    [w["_end"] for w in precip_rows + full_rows]
                ).isoformat(timespec="minutes"),
                "post_time_jst": start.isoformat(timespec="minutes"),
            })
        except (ValueError, KeyError, OverflowError) as exc:
            reason = str(exc) if str(exc) in {
                "unsupported_track_or_surface", "pre_rebuild_kyoto_regime",
                "implausible_official_post_time", "missing_postrace_official_evidence",
                "unknown_official_condition", "missing_timed_morning_JRA_anchor",
                "nonofficial_morning_anchor", "morning_anchor_after_post",
                "invalid_morning_moisture", "insufficient_prerace_precipitation_coverage",
                "insufficient_prerace_weather_coverage",
            } else "invalid_or_incomplete_source_field"
            rejected[reason] += 1

    by_model: dict[str, dict] = {}
    for track in STATIONS:
        for surface in ("turf", "dirt"):
            subset = [r for r in accepted if r["track"] == track and r["surface"] == surface]
            rain = [r for r in subset if r["rain_transition"]]
            baseline, pilot = score(subset, "baseline"), score(subset, "existing_pilot")
            by_model[f"{track}_{surface}"] = {
                "labelled_races": len(subset),
                "independent_meeting_days": len({r["date"] for r in subset}),
                "years": len({r["date"][:4] for r in subset}),
                "rain_transition_days": len({r["date"] for r in rain}),
                "morning_static_baseline": baseline,
                "existing_operational_pilot": pilot,
                "rain_transition_baseline": score(rain, "baseline"),
                "rain_transition_pilot": score(rain, "existing_pilot"),
                "stage_b_candidate": False,
                "promotion_blockers": [
                    "No distinct trained challenger against current operational heuristic",
                    "No independently verified feature publication timestamp / forward-time holdout",
                    "Insufficient evidence until official race-level dataset and calibration are audited",
                ],
            }
    return {
        "schema_version": 1, "status": "retrospective_research_only",
        "production_router_changed": False,
        "current_jra_prediction_changed": False,
        "metrics_are_not_live_forecast_hit_rates": True,
        "audit": {
            "input_labels": len(labels), "accepted_races": len(accepted),
            "rejected_races": sum(rejected.values()), "rejection_reasons": dict(sorted(rejected.items())),
            "feature_end_time_precedes_post_with_one_hour_buffer": True,
            "historical_publication_availability_verified": False,
            "formal_promotion_eligible": False,
            "note": "Hour-end filtering prevents clock-time leakage; publication latency and source revisions still require an independent audit.",
        },
        "models": by_model,
        "race_audit": accepted,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--observations", type=Path, required=True)
    p.add_argument("--weather", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = replay(
        load_csv(args.labels, REQUIRED_LABEL_FIELDS),
        load_csv(args.observations, REQUIRED_OBSERVATION_FIELDS),
        load_csv(args.weather, REQUIRED_WEATHER_FIELDS),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k in {"status", "audit", "models"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
