#!/usr/bin/env python3
"""Guard design registration for the Tokyo/Kyoto prospective track condition trial.

This does NOT start or count a comparison. Fail closed if a design record is
mistakenly represented as an active or proven formal candidate.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIAL_ID = "track_condition_tokyo_kyoto_20261101_v1"
TARGET = {("tokyo", "turf"), ("tokyo", "dirt"),
          ("kyoto", "turf"), ("kyoto", "dirt")}


def validate(experiments: dict, latest: dict, models: dict) -> list[str]:
    errors: list[str] = []
    entries = [x for x in experiments.get("experiments", [])
               if x.get("id") == TRIAL_ID]
    if len(entries) != 1:
        return ["expected exactly one Tokyo/Kyoto experiment"]
    trial = entries[0]
    if trial.get("status") != "design":
        errors.append("candidate is not runnable/Grade A sealed; status must remain design")
    if trial.get("baseline") != latest.get("version"):
        errors.append("baseline must match actual formal latest_prompt version")
    if not trial.get("challenger") or trial.get("challenger") == trial.get("baseline"):
        errors.append("challenger must have a distinct immutable identifier")
    if trial.get("hypothesis_ids") != ["track_condition"]:
        errors.append("experiment must not mix unrelated hypotheses")
    scope = trial.get("scope") or {}
    actual = {(t, s) for t in scope.get("venues", [])
              for s in scope.get("surfaces", [])}
    if actual != TARGET:
        errors.append("scope must be exactly Tokyo/Kyoto turf and dirt")
    pair = trial.get("prestart_pairing") or {}
    needed = ("same_race", "same_information_cutoff",
              "both_predictions_before_official_start",
              "immutable_proof_commit_for_both", "cannot_backfill")
    if any(pair.get(k) is not True for k in needed):
        errors.append("strict prospective pairing safeguards missing")
    if pair.get("grade") != "prospective_strict":
        errors.append("not Grade A prospective")
    if pair.get("minimum_valid_pairs", 0) < 20:
        errors.append("fewer than 20 prospectively matched races")
    if trial.get("valid_pairs_count") != 0:
        errors.append("design state cannot claim validated new/old pairs")
    if models.get("production_router_changed") is not False:
        errors.append("production router changed")
    actual_models = {(m.get("track"), m.get("surface")): m
                     for m in models.get("models", [])
                     if (m.get("track"), m.get("surface")) in TARGET}
    if set(actual_models) != TARGET:
        errors.append("Tokyo/Kyoto model registry incomplete")
    else:
        for (track, surface), m in actual_models.items():
            if m.get("routing", {}).get("production"):
                errors.append(f"{track}/{surface}: shadow candidate routed to production")
            if m.get("stage_a", {}).get("status") != "candidate":
                errors.append(f"{track}/{surface}: Stage A candidate missing")
            if m.get("stage_b", {}).get("status") != "pilot":
                errors.append(f"{track}/{surface}: Stage B is not declared pilot")
    if experiments.get("policy", {}).get("automatic_promotion") is not False:
        errors.append("automatic promotion guard missing")
    return errors


def main() -> None:
    e = json.loads((ROOT / "e2e_validation/improvement_experiments_v1.json").read_text(encoding="utf-8"))
    latest = json.loads((ROOT / "docs/data/latest_prompt.json").read_text(encoding="utf-8"))
    models = json.loads((ROOT / "baba_models_v2/model_registry.json").read_text(encoding="utf-8"))
    errors = validate(e, latest, models)
    if errors:
        raise SystemExit("TRACK_CONDITION_DESIGN_FAIL:\n" + "\n".join(errors))
    print("TRACK_CONDITION_DESIGN_PASS: planned only; no counted paired cases")


if __name__ == "__main__":
    main()
