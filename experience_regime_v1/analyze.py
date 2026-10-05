#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from e2e_validation.evaluate import ValidationError, load_prediction, parse_dt, read_json
from experience_regime_v1.model import (
    ExperienceValidationError,
    aggregate_rows,
    build_horse_rows,
)

VALID_GRADES = {"prospective_strict", "historical_replay", "synthetic"}


def discover_cases(cases_dir: Path) -> List[Path]:
    if not cases_dir.exists():
        return []
    return sorted(cases_dir.rglob("case.json"))


def load_collection_policy(repo_root: Path) -> dict:
    cfg = read_json(repo_root / "experience_regime_v1/config.json")
    collection = cfg.get("collection") or {}
    required_from_raw = collection.get("required_from")
    required_from = date.fromisoformat(required_from_raw) if required_from_raw else None
    return {
        "required_from": required_from,
        "required_from_raw": required_from_raw,
        "required_grades": set(collection.get("required_grades") or []),
        "scope": collection.get("scope"),
        "publish_per_horse_shadow_on_site": bool(
            collection.get("publish_per_horse_shadow_on_site", False)
        ),
        "public_disclosure": collection.get("public_disclosure"),
    }


def collection_required(case: dict, grade: str, cutoff: datetime, policy: dict) -> bool:
    required_from = policy.get("required_from")
    if required_from is None or grade not in policy.get("required_grades", set()):
        return False
    raw = case.get("date")
    case_date = date.fromisoformat(raw) if raw else cutoff.date()
    return case_date >= required_from


def run(repo_root: Path, cases_dir: Path) -> dict:
    policy = load_collection_policy(repo_root)
    rows_by_version: Dict[str, List[dict]] = defaultdict(list)
    coverage_by_version: Dict[str, dict] = defaultdict(
        lambda: {
            "prediction_entries": 0,
            "entries_with_experience": 0,
            "missing_experience": 0,
            "required_entries": 0,
        }
    )
    errors: List[dict] = []

    for case_path in discover_cases(cases_dir):
        try:
            case = read_json(case_path)
            grade = case.get("grade")
            if grade not in VALID_GRADES:
                raise ValidationError(f"invalid grade: {grade}")
            cutoff = parse_dt(case.get("cutoff_at"))
            is_required = collection_required(case, grade, cutoff, policy)
            result_path = case.get("result_path")
            if not result_path:
                raise ValidationError("case.result_path is required")
            result = read_json(repo_root / result_path)

            for spec in case.get("predictions", []):
                version = spec.get("version", "unknown")
                coverage_by_version[version]["prediction_entries"] += 1
                if is_required:
                    coverage_by_version[version]["required_entries"] += 1
                try:
                    prediction, _proof = load_prediction(repo_root, spec, grade, cutoff)
                    rows = build_horse_rows(prediction, result)
                    if rows:
                        coverage_by_version[version]["entries_with_experience"] += 1
                        rows_by_version[version].extend(rows)
                    else:
                        coverage_by_version[version]["missing_experience"] += 1
                        if is_required:
                            raise ExperienceValidationError(
                                "experience_required_after_start_date: "
                                f"grade={grade} date={case.get('date') or cutoff.date().isoformat()} "
                                f"required_from={policy['required_from_raw']}"
                            )
                except (ValidationError, ExperienceValidationError) as exc:
                    errors.append(
                        {
                            "case": str(case_path.relative_to(repo_root)),
                            "race_id": case.get("race_id"),
                            "version": version,
                            "grade": grade,
                            "error": str(exc),
                        }
                    )
        except (ValidationError, ValueError) as exc:
            errors.append(
                {
                    "case": str(case_path.relative_to(repo_root)),
                    "race_id": None,
                    "version": None,
                    "grade": None,
                    "error": str(exc),
                }
            )

    versions = {}
    all_versions = sorted(set(coverage_by_version) | set(rows_by_version))
    for version in all_versions:
        coverage = dict(coverage_by_version[version])
        total = coverage["prediction_entries"]
        covered = coverage["entries_with_experience"]
        required = coverage["required_entries"]
        coverage["coverage_rate"] = round(covered / total, 6) if total else None
        coverage["required_coverage_rate"] = (
            round(covered / required, 6) if required else None
        )
        versions[version] = {
            "coverage": coverage,
            "regimes": aggregate_rows(rows_by_version.get(version, [])),
        }

    return {
        "schema_version": 1,
        "model_version": "e012-shadow-v0.1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "shadow_observation_only",
        "production_effect": False,
        "collection": {
            "required_from": policy["required_from_raw"],
            "required_grades": sorted(policy["required_grades"]),
            "scope": policy["scope"],
            "publish_per_horse_shadow_on_site": policy[
                "publish_per_horse_shadow_on_site"
            ],
            "public_disclosure": policy["public_disclosure"],
        },
        "definitions": {
            "E0": "0 starts before race",
            "E1": "1-3 starts before race",
            "E2": "4+ starts before race",
        },
        "versions": versions,
        "errors": errors,
        "interpretation": {
            "missing_experience_before_collection_start_is_allowed": True,
            "missing_required_experience_is_validation_failure": True,
            "no_ranking_or_mark_change": True,
            "no_automatic_promotion": True,
            "next_step": "Accumulate regime coverage, then estimate uncertainty/shrinkage as a separate challenger.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="e2e_validation/cases")
    parser.add_argument("--output", default="docs/data/experience_regime_status.json")
    parser.add_argument("--allow-errors", action="store_true")
    args = parser.parse_args()

    status = run(REPO_ROOT, REPO_ROOT / args.cases)
    output = REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if args.allow_errors or not status["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
