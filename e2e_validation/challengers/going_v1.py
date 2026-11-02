#!/usr/bin/env python3
"""EXP-002 challenger: track-condition (going) overlay on the frozen formal STEP1.

Deterministic and pre-registered. Input is ONLY the sealed formal prestart
prediction: the official going observed before the start
(race_context.official_going) and the JRA past-performance excerpts frozen in
STEP1. No odds, no results, no post-start going changes.

Method (parameters fixed in PARAMS, code pinned by git blob SHA in
e2e_validation/improvement_experiments_v1.json; any edit = a new challenger):
  1. Race category: wet if the sealed official going is 稍重/重/不良, else dry.
  2. For each runner, use past runs on the SAME surface (芝/ダ) only. Each
     finished run scores 1-(finish-1)/(field-1): 1 = won, 0 = last.
  3. If the runner has at least one dry and one wet run on that surface,
     diff = mean score in the race's category - mean score in the other.
     Otherwise the runner is left unchanged.
  4. Multiply the formal win probability by exp(k*diff), k = 0.8 on wet races
     and 0.4 on dry races, clamped to [0.80, 1.25]; renormalise to 1.
"""
from __future__ import annotations

import math
import re
from statistics import mean

CHALLENGER_ID = "v3.13+going_v1"

PARAMS = {
    "wet_goings": ["稍重", "重", "不良"],
    "k_wet_race": 0.8,
    "k_dry_race": 0.4,
    "min_multiplier": 0.80,
    "max_multiplier": 1.25,
}

_RUN = re.compile(r"(\d+) 着 (\d+) 頭.*?kg \d{3,4}(芝|ダ)\s.*?(良|稍重|重|不良)\s")
MARKS = ["◎", "○", "▲", "△", "☆"]


def surface_key(surface: str):
    if not surface:
        return None
    return "芝" if surface.startswith("芝") else "ダ" if surface.startswith("ダ") else None


def parse_run(excerpt: str):
    m = _RUN.search(excerpt or "")
    if not m:
        return None
    finish, field = int(m.group(1)), int(m.group(2))
    if field < 2 or not 1 <= finish <= field:
        return None
    return {"surface": m.group(3), "wet": m.group(4) in PARAMS["wet_goings"],
            "score": 1 - (finish - 1) / (field - 1)}


def going_diff(horse: dict, surface: str, race_wet: bool):
    runs = [r for r in (parse_run(p.get("source_excerpt", ""))
                        for p in horse.get("past_performances") or [])
            if r and r["surface"] == surface]
    wet = [r["score"] for r in runs if r["wet"]]
    dry = [r["score"] for r in runs if not r["wet"]]
    if not wet or not dry:
        return None, len(wet), len(dry)
    same, other = (wet, dry) if race_wet else (dry, wet)
    return mean(same) - mean(other), len(wet), len(dry)


def predict(formal: dict) -> dict:
    """Return challenger win probabilities from a sealed formal v3.13 prediction."""
    ranking = [h for h in formal.get("step1_ranking") or [] if isinstance(h, dict)]
    if not ranking or not all(isinstance(h.get("win_probability"), (int, float)) for h in ranking):
        raise ValueError("sealed STEP1 win probabilities are required")
    ctx = formal.get("race_context") or {}
    going, surface = ctx.get("official_going"), surface_key(ctx.get("surface"))
    if going not in ("良", *PARAMS["wet_goings"]) or not surface:
        raise ValueError("sealed prestart official going and surface are required")
    race_wet = going in PARAMS["wet_goings"]
    k = PARAMS["k_wet_race"] if race_wet else PARAMS["k_dry_race"]
    rows, raw = [], {}
    for h in ranking:
        diff, n_wet, n_dry = going_diff(h, surface, race_wet)
        mult = 1.0 if diff is None else min(PARAMS["max_multiplier"],
                                            max(PARAMS["min_multiplier"], math.exp(k * diff)))
        raw[h["horse_number"]] = h["win_probability"] * mult
        rows.append({"horse_number": h["horse_number"], "wet_runs": n_wet, "dry_runs": n_dry,
                     "going_diff": None if diff is None else round(diff, 4),
                     "multiplier": round(mult, 4),
                     "formal_win_probability": h["win_probability"]})
    total = sum(raw.values())
    for r in rows:
        r["challenger_win_probability"] = raw[r["horse_number"]] / total
    order = sorted(raw, key=lambda n: (-raw[n], n))
    return {
        "challenger": CHALLENGER_ID,
        "official_going_prestart": going,
        "race_category": "wet" if race_wet else "dry",
        "adjusted_runners": sum(r["going_diff"] is not None for r in rows),
        "runners": rows,
        "marks": {MARKS[i]: order[i] for i in range(min(len(MARKS), len(order)))},
    }
