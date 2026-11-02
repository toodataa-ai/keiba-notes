#!/usr/bin/env python3
"""Fail-closed checks and status output for all JRA improvement experiments.

This file validates DESIGN READINESS only. It cannot create a prospective
prestart prediction, proof_commit, paired Grade A case, or formal approval.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAL = {"pace_positioning", "track_condition", "ticket_portfolio", "field_experience"}
RESEARCH = {"E0", "E1", "E2"}
REQUIRED = {"same_race", "same_information_cutoff",
            "both_predictions_before_official_start",
            "immutable_proof_commit_for_both", "cannot_backfill"}


def validate(registry: dict, evidence: dict, latest: dict, models: dict) -> tuple[list[str], dict]:
    errors = []
    plans = registry.get("experiments") or []
    ids = [p.get("id") for p in plans]
    if len(ids) != len(set(ids)):
        errors.append("duplicate experiment IDs")
    if len(plans) != 7:
        errors.append("expected seven theme plans: four formal, three research")
    formal = evidence.get("formal") or {}
    topics = {x["id"]: x for x in formal.get("hypotheses", [])}
    regimes = {x["id"].upper().replace("EXPERIENCE_", ""): x
               for x in (evidence.get("research") or {}).get("regimes", [])}
    if set(topics) != FORMAL:
        errors.append("formal topic coverage does not match latest roadmap")
    if set(regimes) != RESEARCH:
        errors.append("research E0 E1 E2 coverage incomplete")
    formal_ids = set()
    research_ids = set()
    output = []
    for p in plans:
        id_ = p.get("id") or "unnamed"
        kind = p.get("experiment_family")
        pair = p.get("prestart_pairing") or {}
        if not p.get("challenger"):
            errors.append(id_ + ": no candidate identity")
        if not REQUIRED.issubset({k for k, v in pair.items() if v is True}):
            errors.append(id_ + ": strict before-start pairing contract incomplete")
        if p.get("runner_ready") is not False:
            errors.append(id_ + ": not allowed to represent unimplemented candidate runner as ready")
        if p.get("strict_pairs_count") != 0:
            errors.append(id_ + ": no candidate prestart proof; paired case count must stay zero")
        if p.get("status") not in {"design", "awaiting_evidence"}:
            errors.append(id_ + ": status cannot claim activated or completed comparison")
        source_ready = False
        source_count = 0
        gap = None
        if kind == "formal_jra":
            h_ids = p.get("hypothesis_ids") or []
            if len(h_ids) != 1 or h_ids[0] not in FORMAL:
                errors.append(id_ + ": invalid formal hypothesis mapping")
                continue
            theme = h_ids[0]
            if theme in formal_ids:
                errors.append(id_ + ": duplicate formal theme")
            formal_ids.add(theme)
            if p.get("baseline") != latest.get("version") or p.get("baseline") != evidence.get("latest_formal_prompt_version"):
                errors.append(id_ + ": baseline must be current official JRA prompt")
            if pair.get("grade") != "prospective_strict" or (pair.get("minimum_valid_pairs") or 0) < 20:
                errors.append(id_ + ": 20 future Grade A pairs required")
            h = topics.get(theme) or {}
            screen = (h.get("next_decision") or {}).get("screening") or {}
            source_ready = screen.get("ready_to_design_experiment") is True
            source_count = screen.get("qualifying_race_reviews", 0)
            gap = screen.get("remaining_qualifying_race_reviews")
            expected = "design" if source_ready else "awaiting_evidence"
            if p.get("status") != expected:
                errors.append(id_ + ": formal observation gate requires " + expected)
        elif kind == "experience_regime_research":
            group = p.get("research_regime")
            if group not in RESEARCH:
                errors.append(id_ + ": invalid experience group")
                continue
            if group in research_ids:
                errors.append(id_ + ": duplicate research group")
            research_ids.add(group)
            rec = regimes.get(group) or {}
            source_count = min(int(rec.get("strict_win_probability_observations") or 0),
                               int(rec.get("strict_top3_probability_observations") or 0))
            target = rec.get("diagnostic_initial_target") or {}
            source_ready = (target.get("minimum_data_counts_observed") is True
                            and target.get("needs_record_level_overlap_and_proof_audit") is False)
            gap = max(0, int(target.get("win_probability_cases") or 30) - int(rec.get("strict_win_probability_observations") or 0),
                      int(target.get("top3_probability_cases") or 30) - int(rec.get("strict_top3_probability_observations") or 0))
            if not source_ready and p.get("status") != "awaiting_evidence":
                errors.append(id_ + ": unscored research cannot advance beyond awaiting_evidence")
        else:
            errors.append(id_ + ": unrecognized experiment family")
            continue
        output.append({
            "id": id_, "title": p.get("title"), "family": kind,
            "stage": p.get("status"), "observation_or_probability_gate_ready": source_ready,
            "qualified_observations": source_count, "remaining_required_observations": gap,
            "candidate_runner_ready": False, "prospective_strict_paired_cases": 0,
            "minimum_paired_cases": 20 if kind == "formal_jra" else None,
            "can_promote": False, "unresolved": [
                "implement prospective candidate and immutable prestart proof",
                "collect qualifying future outcomes after both forecasts sealed",
                "validate accuracy, harmful regressions, and explicit A/B/C approval",
            ]
        })
    if formal_ids != FORMAL:
        errors.append("missing formal topics: " + repr(sorted(FORMAL - formal_ids)))
    if research_ids != RESEARCH:
        errors.append("missing research groups: " + repr(sorted(RESEARCH - research_ids)))
    if registry.get("policy", {}).get("automatic_promotion") is not False:
        errors.append("auto promotion must be disabled")
    if models.get("production_router_changed") is not False:
        errors.append("model router cannot change as a side effect of registration")
    status = {
        "schema_version": 1,
        "kind": "design_readiness_only_not_execution",
        "formal_baseline": latest.get("version"),
        "experiment_count": len(plans),
        "registered_design_count": sum(p.get("status") == "design" for p in plans),
        "awaiting_evidence_count": sum(p.get("status") == "awaiting_evidence" for p in plans),
        "strict_paired_cases_total": 0,
        "never_infer_cases_from_observations": True,
        "candidate_execution_implemented": False,
        "formal_originals_unchanged": True,
        "experiments": output,
    }
    return errors, status


def load() -> tuple[list[str], dict]:
    load_json = lambda p: json.loads((ROOT / p).read_text(encoding="utf-8"))
    errors, status = validate(
        load_json("e2e_validation/improvement_experiments_v1.json"),
        load_json("docs/data/jra_improvement_cycle_v1.json"),
        load_json("docs/data/latest_prompt.json"),
        load_json("baba_models_v2/model_registry.json"))
    # Preserve the original v1 design records. Execution counts come exclusively
    # from the separately audited runtime, never from their hand-edited fields.
    sys.path.insert(0, str(ROOT))
    from shadow_lab.runtime import status as runtime_status
    runtime = runtime_status()
    status['kind'] = 'design_and_audited_shadow_runtime'
    status['runtime'] = runtime
    status['candidate_execution_implemented'] = True
    status['strict_paired_cases_total'] = sum(x['valid_pairs'] for x in runtime['experiments'] if x['paired_target'])
    return errors, status


def main() -> None:
    errors, status = load()
    if errors:
        raise SystemExit("ALL_EXPERIMENT_DESIGN_FAIL:\n" + "\n".join(errors))
    out = ROOT / "docs/data/jra_shadow_experiment_status_v1.json"
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ALL_EXPERIMENT_DESIGNS_PASS:", status['experiment_count'], "plans; audited formal pairs:",status['strict_paired_cases_total'])
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
