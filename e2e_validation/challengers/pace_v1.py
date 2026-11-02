#!/usr/bin/env python3
"""EXP-001 challenger: pace/position overlay on the frozen formal STEP1.

Deterministic and pre-registered. Input is ONLY the sealed formal prestart
prediction (STEP1 win probabilities + JRA past-performance excerpts that were
frozen before the start). No odds, no results, no post-start information.

Method (parameters are fixed in PARAMS and pinned by git blob SHA in
e2e_validation/improvement_experiments_v1.json; any edit = a new challenger):
  1. For each runner, read the first-corner passing position of up to the last
     4 runs from the sealed excerpt ("... 514 kg 5 5 4 3 3F 35.2 ...") and the
     field size ("18 頭"). early_ratio = (pos-1)/(field-1): 0 = led, 1 = last.
  2. Running style: front if mean early_ratio <= 0.33, closer if >= 0.67,
     otherwise mid. No corner data -> unknown (left unchanged).
  3. Race pace forecast from the number of habitual leaders
     (mean early_ratio <= 0.20): H if >= max(4, 30% of field), S if <= 1,
     otherwise M.
  4. Multiply the formal win probability by the style multiplier for that pace,
     then renormalise to 1. Marks are re-ranked by the new probability.
"""
from __future__ import annotations

import re
from statistics import mean

CHALLENGER_ID = "v3.13+pace_v1"

PARAMS = {
    "max_runs": 4,
    "front_max_ratio": 0.33,
    "closer_min_ratio": 0.67,
    "leader_max_ratio": 0.20,
    "high_pace_min_leaders": 4,
    "high_pace_min_leader_share": 0.30,
    "slow_pace_max_leaders": 1,
    "multipliers": {
        "S": {"front": 1.25, "mid": 1.00, "closer": 0.80},
        "M": {"front": 1.10, "mid": 1.00, "closer": 0.92},
        "H": {"front": 0.85, "mid": 1.00, "closer": 1.15},
    },
}

_CORNERS = re.compile(r"kg ((?:\d{1,2} ){1,4})3F")
_FIELD = re.compile(r"(\d+) 頭")
MARKS = ["◎", "○", "▲", "△", "☆"]


def early_ratio(excerpt: str):
    corners, field = _CORNERS.search(excerpt or ""), _FIELD.search(excerpt or "")
    if not corners or not field:
        return None
    first = int(corners.group(1).split()[0])
    n = int(field.group(1))
    if n < 2 or not 1 <= first <= n:
        return None
    return (first - 1) / (n - 1)


def runner_style(horse: dict):
    ratios = [r for r in (early_ratio(p.get("source_excerpt", ""))
                          for p in (horse.get("past_performances") or [])[:PARAMS["max_runs"]])
              if r is not None]
    if not ratios:
        return None, "unknown"
    m = mean(ratios)
    if m <= PARAMS["front_max_ratio"]:
        return m, "front"
    if m >= PARAMS["closer_min_ratio"]:
        return m, "closer"
    return m, "mid"


def forecast_pace(styles: dict):
    n = len(styles)
    leaders = sum(1 for ratio, _ in styles.values()
                  if ratio is not None and ratio <= PARAMS["leader_max_ratio"])
    if leaders >= max(PARAMS["high_pace_min_leaders"], PARAMS["high_pace_min_leader_share"] * n):
        return "H", leaders
    if leaders <= PARAMS["slow_pace_max_leaders"]:
        return "S", leaders
    return "M", leaders


def predict(formal: dict) -> dict:
    """Return challenger win probabilities from a sealed formal v3.13 prediction."""
    ranking = [h for h in formal.get("step1_ranking") or [] if isinstance(h, dict)]
    if not ranking or not all(isinstance(h.get("win_probability"), (int, float)) for h in ranking):
        raise ValueError("sealed STEP1 win probabilities are required")
    styles = {h["horse_number"]: runner_style(h) for h in ranking}
    pace, leaders = forecast_pace(styles)
    mult = PARAMS["multipliers"][pace]
    raw = {h["horse_number"]: h["win_probability"] * mult.get(styles[h["horse_number"]][1], 1.0)
           for h in ranking}
    total = sum(raw.values())
    probs = {k: v / total for k, v in raw.items()}
    order = sorted(probs, key=lambda k: (-probs[k], k))
    return {
        "challenger": CHALLENGER_ID,
        "pace_forecast": pace,
        "habitual_leaders": leaders,
        "runners": [{
            "horse_number": h["horse_number"],
            "style": styles[h["horse_number"]][1],
            "mean_early_ratio": (round(styles[h["horse_number"]][0], 4)
                                 if styles[h["horse_number"]][0] is not None else None),
            "formal_win_probability": h["win_probability"],
            "challenger_win_probability": probs[h["horse_number"]],
        } for h in ranking],
        "marks": {MARKS[i]: order[i] for i in range(min(len(MARKS), len(order)))},
    }
