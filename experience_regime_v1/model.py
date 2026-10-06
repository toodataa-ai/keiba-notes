from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

REGIMES = ("E0", "E1", "E2")
SAMPLE_ORIGINS = (
    "official_prediction",
    "stratified_sample",
    "historical_replay",
    "synthetic",
)


class ExperienceValidationError(ValueError):
    pass


def classify_regime(starts_before_race: int) -> str:
    if isinstance(starts_before_race, bool) or not isinstance(starts_before_race, int):
        raise ExperienceValidationError("starts_before_race must be an integer")
    if starts_before_race < 0:
        raise ExperienceValidationError("starts_before_race must be >= 0")
    if starts_before_race == 0:
        return "E0"
    if starts_before_race <= 3:
        return "E1"
    return "E2"


def validate_race_context(
    prediction: dict,
    allowed_categories: Optional[Iterable[str]] = None,
    required: bool = False,
) -> Dict[str, Any]:
    context = prediction.get("race_context")
    if context is None:
        if required:
            raise ExperienceValidationError("race_context is required for selected Shadow races")
        return {}
    if not isinstance(context, dict):
        raise ExperienceValidationError("race_context must be an object")

    race_no = context.get("race_no")
    category = context.get("race_category")
    sample_origin = context.get("sample_origin")

    if isinstance(race_no, bool) or not isinstance(race_no, int) or not 1 <= race_no <= 12:
        raise ExperienceValidationError("race_context.race_no must be an integer from 1 to 12")
    if not isinstance(category, str) or not category:
        raise ExperienceValidationError("race_context.race_category is required")
    if allowed_categories is not None and category not in set(allowed_categories):
        raise ExperienceValidationError(f"unknown race_category: {category}")
    if sample_origin not in SAMPLE_ORIGINS:
        raise ExperienceValidationError(
            "race_context.sample_origin must be one of: " + ",".join(SAMPLE_ORIGINS)
        )

    return {
        "race_no": race_no,
        "race_category": category,
        "sample_origin": sample_origin,
        "race_name": context.get("race_name"),
        "venue": context.get("venue"),
    }


def validate_experience_block(prediction: dict, field: Optional[Iterable[int]] = None) -> Dict[str, dict]:
    block = prediction.get("experience")
    if block is None:
        return {}
    if not isinstance(block, dict):
        raise ExperienceValidationError("experience must be an object")
    horses = block.get("horses")
    if not isinstance(horses, dict) or not horses:
        raise ExperienceValidationError("experience.horses must be a non-empty object")

    normalized: Dict[str, dict] = {}
    for horse_no, item in horses.items():
        key = str(horse_no)
        if not isinstance(item, dict):
            raise ExperienceValidationError(f"experience.horses[{key}] must be an object")
        starts = item.get("starts_before_race")
        regime = classify_regime(starts)
        declared = item.get("regime")
        if declared is not None and declared != regime:
            raise ExperienceValidationError(
                f"experience regime mismatch horse={key}: declared={declared} calculated={regime}"
            )
        normalized[key] = {"starts_before_race": starts, "regime": regime}

    if field is not None:
        expected = {str(int(x)) for x in field}
        missing = sorted(expected - set(normalized), key=int)
        if missing:
            raise ExperienceValidationError(
                "experience.horses missing finishers: " + ",".join(missing)
            )
    return normalized


def _mean_or_none(values: Iterable[Optional[float]]) -> Optional[float]:
    clean = [float(v) for v in values if v is not None]
    return round(mean(clean), 6) if clean else None


def build_horse_rows(prediction: dict, result: dict) -> List[dict]:
    finish = [int(x) for x in result.get("finish_order", [])]
    if not finish:
        raise ExperienceValidationError("result.finish_order is required")
    exp = validate_experience_block(prediction, finish)
    if not exp:
        return []

    context = validate_race_context(prediction, required=False)
    winner = finish[0]
    top3 = set(finish[:3])
    ranking = prediction.get("step1_ranking") or []
    ranking = [int(x) for x in ranking] if isinstance(ranking, list) else []
    marks = prediction.get("marks") or {}
    marked = set()
    for key in ("win", "second", "third"):
        value = marks.get(key)
        if value is not None:
            marked.add(int(value))

    probs = prediction.get("probabilities") or {}
    win_probs = probs.get("win") if isinstance(probs.get("win"), dict) else {}
    top3_probs = probs.get("top3") if isinstance(probs.get("top3"), dict) else {}

    rows: List[dict] = []
    race_id = prediction.get("race_id")
    version = prediction.get("prompt_version")
    for position, horse_no in enumerate(finish, start=1):
        key = str(horse_no)
        item = exp[key]
        wp = win_probs.get(key)
        tp = top3_probs.get(key)
        row = {
            "race_id": race_id,
            "version": version,
            "horse_no": horse_no,
            "race_no": context.get("race_no"),
            "race_category": context.get("race_category"),
            "sample_origin": context.get("sample_origin"),
            "regime": item["regime"],
            "starts_before_race": item["starts_before_race"],
            "finish_position": position,
            "actual_win": int(horse_no == winner),
            "actual_top3": int(horse_no in top3),
            "predicted_win": float(wp) if isinstance(wp, (int, float)) else None,
            "predicted_top3": float(tp) if isinstance(tp, (int, float)) else None,
            "step1_rank": ranking.index(horse_no) + 1 if horse_no in ranking else None,
            "marked_top3": int(horse_no in marked),
        }
        if row["predicted_win"] is not None:
            row["win_brier"] = round((row["predicted_win"] - row["actual_win"]) ** 2, 6)
        else:
            row["win_brier"] = None
        if row["predicted_top3"] is not None:
            row["top3_brier"] = round((row["predicted_top3"] - row["actual_top3"]) ** 2, 6)
        else:
            row["top3_brier"] = None
        rows.append(row)
    return rows


def aggregate_rows(rows: List[dict]) -> dict:
    by_regime: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        regime = row.get("regime")
        if regime not in REGIMES:
            raise ExperienceValidationError(f"unknown regime: {regime}")
        by_regime[regime].append(row)

    out: Dict[str, Any] = {}
    for regime in REGIMES:
        group = by_regime.get(regime, [])
        out[regime] = {
            "horse_observations": len(group),
            "races": len({r.get("race_id") for r in group}),
            "actual_win_rate": _mean_or_none(r.get("actual_win") for r in group),
            "actual_top3_rate": _mean_or_none(r.get("actual_top3") for r in group),
            "mean_predicted_win": _mean_or_none(r.get("predicted_win") for r in group),
            "mean_predicted_top3": _mean_or_none(r.get("predicted_top3") for r in group),
            "win_brier": _mean_or_none(r.get("win_brier") for r in group),
            "top3_brier": _mean_or_none(r.get("top3_brier") for r in group),
            "mean_step1_rank": _mean_or_none(r.get("step1_rank") for r in group),
            "mark_top3_rate": _mean_or_none(r.get("marked_top3") for r in group),
        }
    return out
