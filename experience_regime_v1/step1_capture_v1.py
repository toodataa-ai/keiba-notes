#!/usr/bin/env python3
"""Capture genuine, prestart-proved formal STEP1 into separate immutable E012 research files.

This module never scores horses, estimates missing probabilities, touches existing
research snapshots, or modifies JRA formal predictions. Absence is explicit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experience_regime_v1"
JST = ZoneInfo("Asia/Tokyo")
SHA = re.compile(r"^[a-f0-9]{40}$")
PREDICTIONS = Path("e2e_validation/predictions")

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

def when(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("naive_timestamp_not_allowed")
    return stamp

def proof_of_file(path, start):
    relative = str(path.relative_to(ROOT))
    if not path.is_file():
        raise ValueError("source_file_missing")
    lines = git("log", "--diff-filter=A", "--reverse", "--format=%H %cI", "--", relative).splitlines()
    if len(lines) != 1:
        raise ValueError("source_first_introduction_unverifiable")
    sha, fixed_at = lines[0].split()
    if when(fixed_at) >= start:
        raise ValueError("source_first_commit_after_start")
    original = subprocess.check_output(["git", "show", sha + ":" + relative], cwd=ROOT)
    if original != path.read_bytes():
        raise ValueError("source_changed_since_first_proof")
    return sha, fixed_at

def path_inside(path):
    if not isinstance(path, str) or not path.startswith(str(PREDICTIONS) + "/"):
        raise ValueError("source_not_formal_prediction")
    p = Path(path)
    if p.is_absolute() or ".." in p.parts or p.suffix != ".json":
        raise ValueError("unsafe_source_path")
    return ROOT / p

def check_runners(source, frozen):
    original = source.get("step1_ranking")
    if source.get("stage") != "formal_prestart" or source.get("no_odds_used_to_change_marks") is not True:
        raise ValueError("formal_independent_STEP1_not_proved")
    if not isinstance(original, list) or not original:
        raise ValueError("formal_STEP1_ranking_absent")
    exp = frozen["experience"]["horses"]
    numbers = [r.get("horse_number") for r in original]
    if set(numbers) != {int(k) for k in exp} or len(set(numbers)) != len(exp):
        raise ValueError("formal_STEP1_full_field_mismatch")
    probs = [r.get("win_probability") for r in original]
    if not all(isinstance(p, (float, int)) and not isinstance(p, bool) and 0 < p < 1 for p in probs):
        raise ValueError("formal_win_probabilities_missing_or_invalid")
    if abs(sum(probs) - 1) > 0.00001:
        raise ValueError("formal_win_probabilities_not_normalized")
    # Reuse only outcome probabilities computed and frozen by the genuine
    # formal STEP1-anchored prereace model; never derive from finish results.
    top3_from_frozen = {}
    distribution = (source.get("outcome_distributions") or {}).get("central")
    if distribution is not None:
        if not isinstance(distribution, list) or not distribution:
            raise ValueError("frozen_outcome_distribution_invalid")
        top3_from_frozen = {n: 0.0 for n in numbers}
        mass = 0.0
        for event in distribution:
            finish = event.get("finish")
            probability = event.get("probability")
            if (not isinstance(finish, list) or len(finish) != 3 or
                    len(set(finish)) != 3 or not set(finish).issubset(top3_from_frozen) or
                    not isinstance(probability, (float, int)) or isinstance(probability, bool) or
                    probability < 0):
                raise ValueError("invalid_frozen_outcome_event")
            mass += probability
            for n in finish:
                top3_from_frozen[n] += probability
        if abs(mass - 1) > 0.0001:
            raise ValueError("frozen_outcome_distribution_not_normalized")
    rows = []
    for rank, row in enumerate(original, 1):
        n = row["horse_number"]
        grades = row.get("factor_grades")
        if not isinstance(grades, list) or len(grades) != 9:
            raise ValueError("formal_nine_factor_grades_missing")
        if not isinstance(row.get("mark"), str) or not row["mark"]:
            raise ValueError("formal_STEP1_mark_missing")
        if row.get("horse_name") != exp[str(n)]["horse_name"]:
            raise ValueError("formal_horse_name_mismatch_" + str(n))
        result = {
            "horse_number": n, "horse_name": row["horse_name"], "step1_rank": rank,
            "mark": row["mark"], "factor_grades": grades,
            "predicted_win_probability": row["win_probability"],
        }
        top3 = row.get("top3_probability")
        if isinstance(top3, (int, float)) and not isinstance(top3, bool) and 0 <= top3 <= 1:
            result["predicted_top3_probability"] = top3
        elif n in top3_from_frozen:
            result["predicted_top3_probability"] = min(1.0, max(0.0, top3_from_frozen[n]))
        rows.append(result)
    return rows

def formal_source(item, frozen, registry):
    matched = [r for r in registry if r.get("scope") == "jra-main" and
               r.get("date") == item["date"] and r.get("venue") == item["venue"]]
    if len(matched) != 1:
        raise ValueError("unique_canonical_formal_race_not_available")
    canonical = matched[0]
    current_path = path_inside(canonical.get("e2e_prediction"))
    current = read(current_path)
    source_name = current.get("source_prediction_path")
    original_path = path_inside(source_name) if source_name else current_path
    source = read(original_path)
    if source_name:
        expected = current.get("source_prediction_sha256")
        actual = hashlib.sha256(original_path.read_bytes()).hexdigest()
        if not expected or expected != actual:
            raise ValueError("canonical_source_prediction_sha256_mismatch")
        if current.get("source_prediction_proof") != source.get("proof_commit"):
            raise ValueError("canonical_source_proof_mismatch")
    ctx = source.get("race_context") or {}
    if (ctx.get("venue") != item["venue"] or ctx.get("race_no") != item["race_no"] or
            ctx.get("start_at") != item["start_at"] or source.get("race_id") != canonical["id"]):
        raise ValueError("formal_race_identity_mismatch")
    start = when(item["start_at"])
    proof = source.get("proof_commit")
    if not isinstance(proof, str) or not SHA.fullmatch(proof):
        raise ValueError("formal_proof_commit_absent")
    proof_at = when(git("show", "-s", "--format=%cI", proof))
    if proof_at >= start or when(source.get("step1_fixed_at")) >= start:
        raise ValueError("formal_STEP1_not_fixed_prestart")
    first_sha, first_at = proof_of_file(original_path, start)
    rows = check_runners(source, frozen)
    return {
        "schema_version": 1, "race_id": item["race_id"],
        "date": item["date"], "venue": item["venue"], "race_no": item["race_no"],
        "start_at": item["start_at"], "sample_origin": item["sample_origin"],
        "capture_type": "copy_of_proof_verified_existing_formal_STEP1",
        "source_race_id": source["race_id"],
        "source_prediction_path": str(original_path.relative_to(ROOT)),
        "source_prediction_sha256": hashlib.sha256(original_path.read_bytes()).hexdigest(),
        "source_first_commit": first_sha, "source_first_commit_at": first_at,
        "source_proof_commit": proof, "source_proof_commit_at": proof_at.isoformat(),
        "step1_fixed_at": source["step1_fixed_at"],
        "no_odds_used": True, "no_synthetic_predictions": True,
        "production_effect": False, "runners": rows,
    }

def run(week, day):
    if day != datetime.now(JST).date().isoformat():
        raise ValueError("only_current_JST_date_can_be_frozen")
    root = BASE / "collection" / week
    plan = read(root / "sample_plan.json")
    if plan.get("week_id") != week:
        raise ValueError("week_plan_mismatch")
    selected = [x for x in plan["selected_races"] if x["date"] == day]
    registry = read(ROOT / "docs/data/races.json")["races"]
    report = {"schema_version": 1, "date": day, "week_id": week,
              "selected_races": len(selected), "step1_frozen_races": 0,
              "missing_step1": [], "completed": [], "production_effect": False,
              "no_synthetic_prediction": True}
    for item in selected:
        rid = item["race_id"]
        target = BASE / "step1_frozen" / week / (rid + ".json")
        if target.exists():
            report["step1_frozen_races"] += 1
            report["completed"].append(rid)
            continue
        if datetime.now(JST) >= when(item["start_at"]):
            reason = "start_already_passed_no_retroactive_step1"
        else:
            snap = root / "snapshots" / (rid + ".json")
            proof_file = root / ("proof_commit_" + day + ".json")
            if not snap.is_file() or not proof_file.is_file():
                reason = "original_prerace_experience_proof_not_yet_frozen"
            elif item["sample_origin"] != "official_prediction":
                reason = "no_independent_audited_STEP1_predictor_for_sampled_race"
            else:
                try:
                    frozen = read(snap)
                    proof = read(proof_file)
                    entry = next(x for x in proof["races"] if x["race_id"] == rid)
                    if not entry["proof_prestart_valid"]:
                        raise ValueError("missing_verified_original_prestart_proof")
                    # Verification of the primary research proof remains in postrace verifier.
                    result = formal_source(item, frozen, registry)
                    if datetime.now(JST) >= when(item["start_at"]):
                        raise ValueError("start_passed_before_step1_freeze")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("x", encoding="utf-8") as fp:
                        json.dump(result, fp, ensure_ascii=False, indent=2)
                        fp.write("\n")
                    report["step1_frozen_races"] += 1
                    report["completed"].append(rid)
                    print("E012_STEP1_FROZEN", rid, len(result["runners"]), flush=True)
                    continue
                except Exception as exc:
                    reason = str(exc)[:180]
        report["missing_step1"].append({"race_id": rid, "reason": reason})
        print("E012_STEP1_NOT_AVAILABLE", rid, reason, flush=True)
    status = ROOT / "docs/data/experience_regime_step1_status.json"
    status.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("E012_STEP1_STATUS", report["step1_frozen_races"], "/", len(selected), flush=True)
    return report

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-id", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    run(args.week_id, args.date)
