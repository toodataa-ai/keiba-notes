#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]


class SamplingValidationError(ValueError):
    pass


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_sampling_policy(config_path: Path) -> dict:
    cfg = read_json(config_path)
    sampling = ((cfg.get("collection") or {}).get("sampling") or {})
    categories = sampling.get("categories") or {}
    if not categories:
        raise SamplingValidationError("collection.sampling.categories is required")
    return {
        "version": sampling.get("version", "unknown"),
        "seed_namespace": sampling.get("seed_namespace", "experience-regime"),
        "race_number_min": int(sampling.get("race_number_min", 1)),
        "race_number_max": int(sampling.get("race_number_max", 12)),
        "categories": categories,
        "always_include": sampling.get("always_include") or {},
        "shortage_policy": sampling.get("shortage_policy"),
        "selection_policy": sampling.get("selection_policy"),
    }


def _stable_score(seed_namespace: str, week_id: str, race_id: str) -> str:
    raw = f"{seed_namespace}|{week_id}|{race_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_pool(pool: dict, policy: dict) -> List[dict]:
    week_id = pool.get("week_id")
    if not isinstance(week_id, str) or not week_id:
        raise SamplingValidationError("pool.week_id is required")
    races = pool.get("races")
    if not isinstance(races, list) or not races:
        raise SamplingValidationError("pool.races must be a non-empty array")

    allowed_categories = set(policy["categories"])
    seen = set()
    normalized: List[dict] = []
    for idx, race in enumerate(races):
        if not isinstance(race, dict):
            raise SamplingValidationError(f"pool.races[{idx}] must be an object")
        race_id = race.get("race_id")
        if not isinstance(race_id, str) or not race_id:
            raise SamplingValidationError(f"pool.races[{idx}].race_id is required")
        if race_id in seen:
            raise SamplingValidationError(f"duplicate race_id: {race_id}")
        seen.add(race_id)

        race_no = race.get("race_no")
        if isinstance(race_no, bool) or not isinstance(race_no, int):
            raise SamplingValidationError(f"race_no must be integer: {race_id}")
        if not policy["race_number_min"] <= race_no <= policy["race_number_max"]:
            raise SamplingValidationError(
                f"race_no out of scope: {race_id} race_no={race_no}"
            )

        category = race.get("race_category")
        if category not in allowed_categories:
            raise SamplingValidationError(
                f"unknown race_category: {race_id} category={category}"
            )

        normalized.append(
            {
                **race,
                "race_id": race_id,
                "race_no": race_no,
                "race_category": category,
                "official_prediction": bool(race.get("official_prediction", False)),
            }
        )
    return normalized


def select_races(pool: dict, policy: dict) -> dict:
    week_id = pool["week_id"]
    races = validate_pool(pool, policy)
    categories: Dict[str, dict] = policy["categories"]

    selected: Dict[str, dict] = {}
    summary: Dict[str, dict] = {}

    official_enabled = bool(
        (policy.get("always_include") or {}).get("official_prediction_races", True)
    )
    if official_enabled:
        for race in races:
            if race["official_prediction"]:
                selected[race["race_id"]] = {
                    **race,
                    "sample_origin": "official_prediction",
                    "selection_score": None,
                }

    for category, meta in categories.items():
        candidates = [r for r in races if r["race_category"] == category]
        official_count = sum(1 for r in candidates if r["official_prediction"])
        non_official = [r for r in candidates if not r["official_prediction"]]
        ranked: List[Tuple[str, dict]] = sorted(
            (
                _stable_score(policy["seed_namespace"], week_id, r["race_id"]),
                r,
            )
            for r in non_official
        )
        target = int(meta.get("target_per_week", 0))
        chosen = ranked[:target]
        for score, race in chosen:
            selected[race["race_id"]] = {
                **race,
                "sample_origin": "stratified_sample",
                "selection_score": score,
            }

        summary[category] = {
            "label": meta.get("label", category),
            "population_races": len(candidates),
            "official_prediction_races": official_count,
            "eligible_non_official_races": len(non_official),
            "target_stratified_races": target,
            "selected_stratified_races": len(chosen),
            "shortfall": max(0, target - len(chosen)),
        }

    selected_list = sorted(
        selected.values(),
        key=lambda r: (
            str(r.get("date", "")),
            str(r.get("venue", "")),
            int(r.get("race_no", 0)),
            r["race_id"],
        ),
    )
    return {
        "schema_version": 1,
        "sampling_version": policy["version"],
        "week_id": week_id,
        "seed_namespace": policy["seed_namespace"],
        "population_scope": "JRA 1R-12R",
        "population_races": len(races),
        "selected_races": selected_list,
        "selected_race_count": len(selected_list),
        "category_summary": summary,
        "shortage_policy": policy.get("shortage_policy"),
        "selection_policy": policy.get("selection_policy"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", required=True)
    parser.add_argument(
        "--config", default="experience_regime_v1/config.json"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    policy = load_sampling_policy(REPO_ROOT / args.config)
    pool = read_json(REPO_ROOT / args.pool)
    result = select_races(pool, policy)

    output = Path(args.output)
    if not output.is_absolute():
        output = REPO_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
