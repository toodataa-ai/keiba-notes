"""Additive JRA all-track Stage B pilot.

This module does not replace legacy Nakayama/Hanshin model files.
It is opt-in and safe to import independently.
"""
from __future__ import annotations
import json, math
from pathlib import Path

_CONFIG = Path(__file__).with_name("config.json")

def _cfg():
    return json.loads(_CONFIG.read_text(encoding="utf-8"))

def supported_tracks():
    return tuple(_cfg()["tracks"].keys())

def _surface(track: str, surface: str):
    c = _cfg()["tracks"]
    if track not in c:
        raise ValueError(f"unsupported track: {track}")
    if surface not in ("turf", "dirt"):
        raise ValueError("surface must be turf or dirt")
    return c[track][surface]

def condition_probs(track: str, surface: str, moisture: float, sigma: float | None = None):
    s = _surface(track, surface)
    sigma = float(sigma if sigma is not None else (1.7 if surface == "turf" else 2.0))
    scale = 1.65 if surface == "turf" else 1.85
    raw = {}
    for name, center in s["centers"].items():
        width = math.sqrt(scale * scale + sigma * sigma)
        raw[name] = math.exp(-0.5 * ((float(moisture) - center) / width) ** 2) / width
    z = sum(raw.values())
    return {k: round(v / z, 4) for k, v in raw.items()}

def update_to_race_time(track: str, surface: str, morning_moist: float,
                        rain_after_measurement_mm: float = 0.0,
                        hours_since_last_rain: float | None = None,
                        temperature_c: float = 20.0,
                        wind_mps: float = 2.0,
                        sunshine_hours: float = 0.0,
                        target_hours: float = 6.25):
    """Operational Stage B heuristic. Not a replacement for validated venue models."""
    _surface(track, surface)
    rain = max(float(rain_after_measurement_mm), 0.0)
    target = max(float(target_hours), 0.0)
    if surface == "turf":
        wet = 0.20 * math.sqrt(rain) + 0.012 * rain
        dry_rate = 0.035 + 0.003 * max(temperature_c - 18, 0) + 0.010 * max(wind_mps - 1, 0) + 0.020 * sunshine_hours / max(target, 1)
        half_width = 1.5 + 0.12 * math.sqrt(rain)
    else:
        wet = 1.0 * math.sqrt(rain) + 0.08 * rain
        dry_rate = 0.10 + 0.006 * max(temperature_c - 18, 0) + 0.018 * max(wind_mps - 1, 0) + 0.035 * sunshine_hours / max(target, 1)
        half_width = 2.0 + 0.18 * math.sqrt(rain)
    dry_hours = target if rain == 0 else min(max(float(hours_since_last_rain or 0), 0), target)
    midpoint = max(0.0, float(morning_moist) + wet - dry_rate * dry_hours)
    return {
        "track": track,
        "surface": surface,
        "race_time_moisture_midpoint_heuristic": round(midpoint, 2),
        "race_time_moisture_range_heuristic": [round(max(0, midpoint-half_width), 2), round(midpoint+half_width, 2)],
        "condition_probs_operational": condition_probs(track, surface, midpoint),
        "validation_status": "pilot operational heuristic; not venue-backtested",
        "legacy_model_replaced": False
    }
