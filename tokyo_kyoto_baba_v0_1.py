"""Tokyo/Kyoto baba model v0.1.

Operational Stage-B model for Tokyo/Kyoto turf and dirt.
It anchors on the JRA same-day morning moisture reading and updates to race time
using rainfall and drying conditions. It intentionally does NOT provide a learned
Stage-A previous-day -> morning prediction until venue-specific historical data
has been joined and backtested.
"""
import math

CONFIG = {
    ("tokyo", "turf"): {
        "centers": {"良": 15.0, "稍重": 19.0, "重": 21.5, "不良": 24.0},
        "scales": {"良": 2.2, "稍重": 1.9, "重": 2.0, "不良": 2.3},
        "sigma": 1.8,
        "wet_sqrt": 0.20, "wet_linear": 0.012,
        "dry_base": 0.035, "dry_temp": 0.003, "dry_wind": 0.010, "dry_sun": 0.020,
        "range_base": 1.5, "range_rain": 0.12,
        "jra_reference": "良<=19 / 稍重17-21 / 重18-23 / 不良>=20 (overlapping reference bands)",
    },
    ("kyoto", "turf"): {
        "centers": {"良": 10.0, "稍重": 12.5, "重": 14.5, "不良": 17.0},
        "scales": {"良": 1.6, "稍重": 1.4, "重": 1.5, "不良": 1.8},
        "sigma": 1.6,
        "wet_sqrt": 0.20, "wet_linear": 0.012,
        "dry_base": 0.035, "dry_temp": 0.003, "dry_wind": 0.010, "dry_sun": 0.020,
        "range_base": 1.4, "range_rain": 0.12,
        "jra_reference": "良<=13 / 稍重11-14 / 重13-16 / 不良>=14 (overlapping reference bands)",
    },
    ("tokyo", "dirt"): {
        "centers": {"良": 5.5, "稍重": 9.8, "重": 13.4, "不良": 16.8},
        "scales": {"良": 1.7, "稍重": 1.8, "重": 1.8, "不良": 2.0},
        "sigma": 2.0,
        "wet_sqrt": 1.00, "wet_linear": 0.08,
        "dry_base": 0.10, "dry_temp": 0.006, "dry_wind": 0.018, "dry_sun": 0.035,
        "range_base": 2.0, "range_rain": 0.18,
        "jra_reference": "all JRA dirt: 良<=9 / 稍重7-13 / 重11-16 / 不良>=14 (overlapping reference bands)",
    },
    ("kyoto", "dirt"): {
        "centers": {"良": 5.5, "稍重": 9.8, "重": 13.4, "不良": 16.8},
        "scales": {"良": 1.7, "稍重": 1.8, "重": 1.8, "不良": 2.0},
        "sigma": 2.0,
        "wet_sqrt": 1.00, "wet_linear": 0.08,
        "dry_base": 0.10, "dry_temp": 0.006, "dry_wind": 0.018, "dry_sun": 0.035,
        "range_base": 2.0, "range_rain": 0.18,
        "jra_reference": "all JRA dirt: 良<=9 / 稍重7-13 / 重11-16 / 不良>=14 (overlapping reference bands)",
    },
}


def condition_probs(venue, surface, moisture, sigma=None):
    c = CONFIG[(venue.lower(), surface.lower())]
    sigma = c["sigma"] if sigma is None else sigma
    raw = {}
    for label, center in c["centers"].items():
        s = math.sqrt(c["scales"][label] ** 2 + sigma ** 2)
        raw[label] = math.exp(-0.5 * ((moisture - center) / s) ** 2) / s
    z = sum(raw.values())
    return {k: v / z for k, v in raw.items()}


def update_to_race_time(venue, surface, morning_moist,
                        rain_after_measurement_mm=0,
                        hours_since_last_rain=None,
                        temperature_c=22, wind_mps=2,
                        sunshine_hours=0, target_hours=6.25):
    key = (venue.lower(), surface.lower())
    if key not in CONFIG:
        raise ValueError(f"unsupported venue/surface: {key}")
    c = CONFIG[key]
    rain = max(float(rain_after_measurement_mm), 0.0)
    wet = c["wet_sqrt"] * math.sqrt(rain) + c["wet_linear"] * rain
    dry_rate = (c["dry_base"]
                + c["dry_temp"] * max(temperature_c - 18, 0)
                + c["dry_wind"] * max(wind_mps - 1, 0)
                + c["dry_sun"] * sunshine_hours / max(target_hours, 1))
    dry_hours = target_hours if rain == 0 else min(max(hours_since_last_rain or 0, 0), target_hours)
    midpoint = max(0.0, morning_moist + wet - dry_rate * dry_hours)
    half_width = c["range_base"] + c["range_rain"] * math.sqrt(rain)
    probs = condition_probs(venue, surface, midpoint)
    return {
        "model": f"{venue.lower()}_{surface.lower()}_v0_1_stage_b",
        "race_time_moisture_midpoint_heuristic": round(midpoint, 2),
        "race_time_moisture_range_heuristic": [round(max(0, midpoint-half_width), 2), round(midpoint+half_width, 2)],
        "condition_probs_operational": {k: round(v, 4) for k, v in probs.items()},
        "jra_reference_band": c["jra_reference"],
        "validation_status": "provisional operational heuristic; venue-specific Stage A and Stage B backtest not completed",
        "warning": "JRA track condition is a comprehensive judgement and is not mechanically determined by moisture percentage alone.",
    }


def predict_sunday_morning(*args, **kwargs):
    raise NotImplementedError(
        "Tokyo/Kyoto v0.1 deliberately has no learned Stage-A predictor. "
        "Use JRA same-day measured moisture when available; otherwise use the prompt's normal inference path and widen uncertainty."
    )
