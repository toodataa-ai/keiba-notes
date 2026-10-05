#!/usr/bin/env python3
"""Leakage-safe E2E evaluator for horse-racing prompt versions.

Grade A (prospective_strict) predictions are read from the pre-race proof commit,
not from HEAD. This makes post-race edits incapable of changing the scored
prediction.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

EPS = 1e-12
VALID_GRADES = {"prospective_strict", "historical_replay", "synthetic"}
GOING_LABELS = ["良", "稍重", "重", "不良"]
PACE_LABELS = ["S", "M", "M-H", "H"]


class ValidationError(Exception):
    pass


def parse_dt(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"invalid datetime: {value!r}")
    value = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"invalid ISO datetime: {value}") from exc
    if dt.tzinfo is None:
        raise ValidationError(f"timezone required: {value}")
    return dt


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {path}: {exc}") from exc


def git_text(repo_root: Path, commit: str, path: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise ValidationError(
            f"prediction_missing_from_proof_commit: {commit}:{path}: {proc.stderr.strip()}"
        )
    return proc.stdout


def git_commit_time(repo_root: Path, commit: str) -> datetime:
    proc = subprocess.run(
        ["git", "show", "-s", "--format=%cI", commit],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise ValidationError(f"cannot read proof commit time: {commit}")
    return parse_dt(proc.stdout.strip())


def load_prediction(
    repo_root: Path,
    spec: dict,
    grade: str,
    cutoff: datetime,
) -> Tuple[dict, dict]:
    path = spec.get("path")
    version = spec.get("version")
    if not path or not version:
        raise ValidationError("prediction spec requires path and version")

    proof = {
        "grade": grade,
        "proof_commit": spec.get("proof_commit"),
        "proof_commit_at": None,
        "read_from_proof_commit": False,
    }

    if grade == "prospective_strict":
        commit = spec.get("proof_commit")
        if not commit:
            raise ValidationError("prospective_strict prediction requires proof_commit")
        commit_at = git_commit_time(repo_root, commit)
        proof["proof_commit_at"] = commit_at.isoformat()
        if commit_at > cutoff:
            raise ValidationError(
                f"proof_commit_after_cutoff: {commit_at.isoformat()} > {cutoff.isoformat()}"
            )
        raw = git_text(repo_root, commit, path)
        try:
            prediction = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid prediction JSON in proof commit: {path}") from exc
        proof["read_from_proof_commit"] = True
    else:
        prediction = read_json(repo_root / path)

    if prediction.get("prompt_version") != version:
        raise ValidationError(
            f"prompt_version_mismatch: spec={version}, prediction={prediction.get('prompt_version')}"
        )

    generated_at = parse_dt(prediction.get("generated_at"))
    info_cutoff = parse_dt(prediction.get("information_cutoff_at"))
    if generated_at > cutoff:
        raise ValidationError(
            f"prediction_after_cutoff: {generated_at.isoformat()} > {cutoff.isoformat()}"
        )
    if info_cutoff > cutoff:
        raise ValidationError(
            f"information_after_cutoff: {info_cutoff.isoformat()} > {cutoff.isoformat()}"
        )

    for source in prediction.get("sources", []):
        published_at = source.get("published_at")
        if grade == "prospective_strict" and not published_at:
            raise ValidationError("strict prediction source requires published_at")
        if published_at and parse_dt(published_at) > cutoff:
            raise ValidationError(
                f"information_after_cutoff: source {source.get('name', source.get('url', 'unknown'))}"
            )

    validate_probability_block(prediction.get("probabilities"), prediction)
    validate_distribution(
        prediction.get("track", {}).get("going_probabilities"),
        expected_labels=GOING_LABELS,
        allow_partial=False,
        label="going_probabilities",
    )
    validate_distribution(
        prediction.get("pace", {}).get("probabilities"),
        expected_labels=PACE_LABELS,
        allow_partial=False,
        label="pace_probabilities",
    )

    return prediction, proof


def validate_distribution(
    probs: Optional[dict],
    expected_labels: Optional[List[str]] = None,
    allow_partial: bool = True,
    label: str = "probabilities",
) -> None:
    if probs is None:
        return
    if not isinstance(probs, dict) or not probs:
        raise ValidationError(f"invalid_probability_distribution: {label}")
    if expected_labels is not None and not allow_partial:
        if set(probs) != set(expected_labels):
            raise ValidationError(
                f"invalid_probability_distribution: {label} labels={sorted(probs)} expected={expected_labels}"
            )
    total = 0.0
    for key, value in probs.items():
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            raise ValidationError(
                f"invalid_probability_distribution: {label}[{key}]={value}"
            )
        total += float(value)
    if abs(total - 1.0) > 0.02:
        raise ValidationError(
            f"invalid_probability_distribution: {label} sum={total:.6f}"
        )


def validate_probability_block(block: Optional[dict], prediction: dict) -> None:
    if block is None:
        return
    if not isinstance(block, dict):
        raise ValidationError("invalid_probability_distribution: probabilities")
    win = block.get("win")
    if win is not None:
        validate_distribution(win, label="win_probabilities")
    top3 = block.get("top3")
    if top3 is not None:
        if not isinstance(top3, dict) or not top3:
            raise ValidationError("invalid_probability_distribution: top3_probabilities")
        for key, value in top3.items():
            if not isinstance(value, (int, float)) or value < 0 or value > 1:
                raise ValidationError(
                    f"invalid_probability_distribution: top3_probabilities[{key}]={value}"
                )
        # Independent top-3 probabilities should sum to roughly 3 for a complete field.
        # Do not hard fail when only a subset is emitted; coverage is handled separately.


def check_manifest(repo_root: Path, prediction: dict) -> dict:
    manifest_path = prediction.get("prompt_manifest")
    if not manifest_path:
        return {"present": False, "valid": False, "reason": "missing_prompt_manifest"}
    manifest = read_json(repo_root / manifest_path)
    if manifest.get("prompt_version") != prediction.get("prompt_version"):
        raise ValidationError(
            f"prompt_version_mismatch: manifest={manifest.get('prompt_version')} prediction={prediction.get('prompt_version')}"
        )
    return {
        "present": True,
        "valid": True,
        "path": manifest_path,
        "component_count": len(manifest.get("components", [])),
    }


def safe_log_loss(prob: float) -> float:
    p = min(max(float(prob), EPS), 1.0)
    return -math.log(p)


def mean_or_none(values: Iterable[Optional[float]]) -> Optional[float]:
    clean = [float(v) for v in values if v is not None]
    return round(mean(clean), 6) if clean else None


def rate_or_none(values: Iterable[Optional[float]]) -> Optional[float]:
    value = mean_or_none(values)
    return round(value, 6) if value is not None else None


def eval_probabilities(prediction: dict, result: dict) -> dict:
    block = prediction.get("probabilities") or {}
    finish = [int(x) for x in result["finish_order"]]
    field = [str(x) for x in finish]
    winner = str(finish[0])
    top3 = {str(x) for x in finish[:3]}
    out = {
        "win_brier": None,
        "win_log_loss": None,
        "top3_brier": None,
        "win_probability_coverage": False,
        "top3_probability_coverage": False,
    }

    win = block.get("win")
    if isinstance(win, dict) and all(h in win for h in field):
        probs = [float(win[h]) for h in field]
        labels = [1.0 if h == winner else 0.0 for h in field]
        out["win_brier"] = round(mean((p - y) ** 2 for p, y in zip(probs, labels)), 6)
        out["win_log_loss"] = round(safe_log_loss(float(win[winner])), 6)
        out["win_probability_coverage"] = True

    t3 = block.get("top3")
    if isinstance(t3, dict) and all(h in t3 for h in field):
        probs = [float(t3[h]) for h in field]
        labels = [1.0 if h in top3 else 0.0 for h in field]
        out["top3_brier"] = round(mean((p - y) ** 2 for p, y in zip(probs, labels)), 6)
        out["top3_probability_coverage"] = True
    return out


def evaluate_prediction(prediction: dict, result: dict) -> dict:
    if prediction.get("race_id") != result.get("race_id"):
        raise ValidationError(
            f"race_id_mismatch: prediction={prediction.get('race_id')} result={result.get('race_id')}"
        )
    finish = [int(x) for x in result.get("finish_order", [])]
    if len(finish) < 3 or len(set(finish)) != len(finish):
        raise ValidationError("result.finish_order must contain unique horses and at least 3 finishers")

    marks = prediction.get("marks") or {}
    try:
        mark_win = int(marks["win"])
        mark_second = int(marks["second"])
        mark_third = int(marks["third"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("prediction marks.win/second/third are required integer horse numbers") from exc

    actual_top3 = set(finish[:3])
    mark_top3 = {mark_win, mark_second, mark_third}
    metrics: Dict[str, Any] = {
        "honmei_win": int(mark_win == finish[0]),
        "honmei_top3": int(mark_win in actual_top3),
        "top3_marks_capture": round(len(mark_top3 & actual_top3) / 3.0, 6),
        "winner_in_top3_marks": int(finish[0] in mark_top3),
        "winner_rank": None,
        "winner_mrr": None,
        "stake_yen": None,
        "payout_yen": None,
        "roi_pct": None,
        "going_log_loss": None,
        "pace_log_loss": None,
    }

    ranking = prediction.get("step1_ranking")
    if isinstance(ranking, list):
        ranking_int = [int(x) for x in ranking]
        if finish[0] in ranking_int:
            r = ranking_int.index(finish[0]) + 1
            metrics["winner_rank"] = r
            metrics["winner_mrr"] = round(1.0 / r, 6)

    prob_metrics = eval_probabilities(prediction, result)
    metrics.update(prob_metrics)

    going_probs = prediction.get("track", {}).get("going_probabilities")
    official_going = result.get("official_going")
    if going_probs and official_going in going_probs:
        metrics["going_log_loss"] = round(safe_log_loss(going_probs[official_going]), 6)

    pace_probs = prediction.get("pace", {}).get("probabilities")
    official_pace = result.get("pace_label")
    if pace_probs and official_pace in pace_probs:
        metrics["pace_log_loss"] = round(safe_log_loss(pace_probs[official_pace]), 6)

    bets = prediction.get("bets")
    settlements = result.get("settlements")
    if isinstance(bets, list) and isinstance(settlements, dict):
        stake = 0
        payout = 0
        complete = True
        for bet in bets:
            bet_id = str(bet.get("id", ""))
            bet_stake = bet.get("stake_yen")
            if not bet_id or not isinstance(bet_stake, int) or bet_stake < 0:
                complete = False
                break
            if bet_id not in settlements:
                complete = False
                break
            stake += bet_stake
            payout += int(settlements[bet_id])
        if complete:
            metrics["stake_yen"] = stake
            metrics["payout_yen"] = payout
            metrics["roi_pct"] = round((payout / stake * 100.0), 3) if stake else None

    return metrics


def aggregate(entries: List[dict]) -> dict:
    if not entries:
        return {
            "cases": 0,
            "honmei_win_rate": None,
            "honmei_top3_rate": None,
            "top3_marks_capture_rate": None,
            "winner_in_top3_marks_rate": None,
            "winner_mean_rank": None,
            "winner_mrr": None,
            "win_brier": None,
            "win_log_loss": None,
            "top3_brier": None,
            "going_log_loss": None,
            "pace_log_loss": None,
            "stake_yen": 0,
            "payout_yen": 0,
            "roi_pct": None,
            "probability_cases": {"win": 0, "top3": 0},
        }
    m = [x["metrics"] for x in entries]
    stake = sum(x["stake_yen"] for x in m if x["stake_yen"] is not None)
    payout = sum(x["payout_yen"] for x in m if x["payout_yen"] is not None)
    bet_cases = sum(1 for x in m if x["stake_yen"] is not None)
    return {
        "cases": len(entries),
        "honmei_win_rate": rate_or_none(x["honmei_win"] for x in m),
        "honmei_top3_rate": rate_or_none(x["honmei_top3"] for x in m),
        "top3_marks_capture_rate": mean_or_none(x["top3_marks_capture"] for x in m),
        "winner_in_top3_marks_rate": rate_or_none(x["winner_in_top3_marks"] for x in m),
        "winner_mean_rank": mean_or_none(x["winner_rank"] for x in m),
        "winner_mrr": mean_or_none(x["winner_mrr"] for x in m),
        "win_brier": mean_or_none(x["win_brier"] for x in m),
        "win_log_loss": mean_or_none(x["win_log_loss"] for x in m),
        "top3_brier": mean_or_none(x["top3_brier"] for x in m),
        "going_log_loss": mean_or_none(x["going_log_loss"] for x in m),
        "pace_log_loss": mean_or_none(x["pace_log_loss"] for x in m),
        "stake_yen": stake,
        "payout_yen": payout,
        "roi_pct": round(payout / stake * 100.0, 3) if stake and bet_cases else None,
        "bet_cases": bet_cases,
        "probability_cases": {
            "win": sum(1 for x in m if x["win_probability_coverage"]),
            "top3": sum(1 for x in m if x["top3_probability_coverage"]),
        },
    }


def paired_comparison(entries: List[dict], config: dict) -> dict:
    baseline = config.get("baseline_version")
    candidate = config.get("candidate_version")
    min_cases = int(config.get("minimum_strict_shared_cases", 20))
    if not baseline or not candidate:
        return {
            "baseline": baseline,
            "candidate": candidate,
            "state": "waiting_for_candidate",
            "strict_shared_cases": 0,
            "minimum_strict_shared_cases": min_cases,
            "deltas_candidate_minus_baseline": {},
        }

    strict_grades = set(config.get("strict_grades", ["prospective_strict"]))
    by_race: Dict[str, Dict[str, dict]] = defaultdict(dict)
    for entry in entries:
        if entry["grade"] in strict_grades:
            by_race[entry["race_id"]][entry["version"]] = entry
    shared = [
        pair for pair in by_race.values() if baseline in pair and candidate in pair
    ]

    def delta(metric: str) -> Optional[float]:
        values = []
        for pair in shared:
            b = pair[baseline]["metrics"].get(metric)
            c = pair[candidate]["metrics"].get(metric)
            if b is not None and c is not None:
                values.append(float(c) - float(b))
        return round(mean(values), 6) if values else None

    state = "ready_for_review" if len(shared) >= min_cases else "insufficient_data"
    return {
        "baseline": baseline,
        "candidate": candidate,
        "state": state,
        "strict_shared_cases": len(shared),
        "minimum_strict_shared_cases": min_cases,
        "deltas_candidate_minus_baseline": {
            "honmei_win": delta("honmei_win"),
            "honmei_top3": delta("honmei_top3"),
            "top3_marks_capture": delta("top3_marks_capture"),
            "winner_in_top3_marks": delta("winner_in_top3_marks"),
            "win_brier": delta("win_brier"),
            "win_log_loss": delta("win_log_loss"),
            "top3_brier": delta("top3_brier"),
            "roi_pct_per_case": delta("roi_pct"),
        },
        "note": "Lower is better for Brier/log loss; higher is better for hit/capture/ROI metrics.",
    }


def discover_cases(cases_dir: Path) -> List[Path]:
    if not cases_dir.exists():
        return []
    return sorted(cases_dir.rglob("case.json"))


def run(repo_root: Path, cases_dir: Path, config_path: Path) -> dict:
    config = read_json(config_path)
    case_paths = discover_cases(cases_dir)
    entries: List[dict] = []
    errors: List[dict] = []

    for case_path in case_paths:
        try:
            case = read_json(case_path)
            grade = case.get("grade")
            if grade not in VALID_GRADES:
                raise ValidationError(f"invalid grade: {grade}")
            cutoff = parse_dt(case.get("cutoff_at"))
            result_path = case.get("result_path")
            if not result_path:
                raise ValidationError("case.result_path is required")
            result = read_json(repo_root / result_path)
            if result.get("race_id") != case.get("race_id"):
                raise ValidationError(
                    f"race_id_mismatch: case={case.get('race_id')} result={result.get('race_id')}"
                )
            result_at = result.get("official_result_at")
            if result_at and parse_dt(result_at) <= cutoff and grade != "synthetic":
                raise ValidationError("official result timestamp must be after cutoff")

            for spec in case.get("predictions", []):
                try:
                    prediction, proof = load_prediction(repo_root, spec, grade, cutoff)
                    if prediction.get("race_id") != case.get("race_id"):
                        raise ValidationError(
                            f"race_id_mismatch: case={case.get('race_id')} prediction={prediction.get('race_id')}"
                        )
                    manifest = check_manifest(repo_root, prediction)
                    metrics = evaluate_prediction(prediction, result)
                    entries.append(
                        {
                            "race_id": case["race_id"],
                            "date": case.get("date"),
                            "venue": case.get("venue"),
                            "surface": case.get("surface"),
                            "race": case.get("race"),
                            "grade": grade,
                            "version": spec["version"],
                            "prediction_path": spec["path"],
                            "proof": proof,
                            "manifest": manifest,
                            "metrics": metrics,
                        }
                    )
                except ValidationError as exc:
                    errors.append(
                        {
                            "case": str(case_path.relative_to(repo_root)),
                            "race_id": case.get("race_id"),
                            "version": spec.get("version"),
                            "grade": grade,
                            "error": str(exc),
                        }
                    )
        except ValidationError as exc:
            errors.append(
                {
                    "case": str(case_path.relative_to(repo_root)),
                    "race_id": None,
                    "version": None,
                    "grade": None,
                    "error": str(exc),
                }
            )

    by_version: Dict[str, List[dict]] = defaultdict(list)
    strict_by_version: Dict[str, List[dict]] = defaultdict(list)
    strict_grades = set(config.get("strict_grades", ["prospective_strict"]))
    for entry in entries:
        by_version[entry["version"]].append(entry)
        if entry["grade"] in strict_grades:
            strict_by_version[entry["version"]].append(entry)

    strict_race_ids = {
        entry["race_id"] for entry in entries if entry["grade"] in strict_grades
    }
    historical_race_ids = {
        entry["race_id"] for entry in entries if entry["grade"] == "historical_replay"
    }
    synthetic_race_ids = {
        entry["race_id"] for entry in entries if entry["grade"] == "synthetic"
    }

    status = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": config.get("mode", "report_only"),
        "case_counts": {
            "strict": len(strict_race_ids),
            "historical_replay": len(historical_race_ids),
            "synthetic": len(synthetic_race_ids),
            "prediction_entries": len(entries),
        },
        "versions": {
            version: {
                "all_non_synthetic": aggregate(
                    [e for e in version_entries if e["grade"] != "synthetic"]
                ),
                "strict": aggregate(strict_by_version.get(version, [])),
            }
            for version, version_entries in sorted(by_version.items())
        },
        "comparison": paired_comparison(entries, config),
        "coverage": {
            "strict_probability_win_cases": sum(
                1
                for e in entries
                if e["grade"] in strict_grades
                and e["metrics"]["win_probability_coverage"]
            ),
            "strict_probability_top3_cases": sum(
                1
                for e in entries
                if e["grade"] in strict_grades
                and e["metrics"]["top3_probability_coverage"]
            ),
            "strict_bet_cases": sum(
                1
                for e in entries
                if e["grade"] in strict_grades
                and e["metrics"]["stake_yen"] is not None
            ),
        },
        "errors": errors,
        "entries": entries,
        "interpretation": {
            "strict_only_for_promotion": True,
            "historical_replay_is_supporting_only": True,
            "synthetic_excluded_from_real_performance": True,
            "automatic_promotion": False,
        },
    }
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="e2e_validation/cases")
    parser.add_argument("--config", default="e2e_validation/config.json")
    parser.add_argument("--output", default="docs/data/e2e_status.json")
    parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="Write report but return success even when validation errors exist.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    status = run(repo_root, repo_root / args.cases, repo_root / args.config)
    output = repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if args.allow_errors or not status["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
