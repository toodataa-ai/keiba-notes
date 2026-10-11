#!/usr/bin/env python3
"""Independent completion gates for a JRA meeting; never edits predictions/bets.

Formal Grade A completion and E0/E1/E2 research completeness are deliberately
separate. A missing pre-race research input is NEVER backfilled after a result.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def evaluate(registry, e2e, shadow, calendar, latest_version):
    formal_errors=e2e.get("errors") or []
    strict={x.get("race_id") for x in (e2e.get("entries") or []) if x.get("grade")=="prospective_strict" and (x.get("proof") or {}).get("read_from_proof_commit")}
    by_id={r["id"]:r for r in registry.get("races",[]) if r.get("scope")=="jra-main"}
    meetings=[]
    for meeting in calendar["meetings"]:
        evaluated=[]
        for rid in meeting["expected_main_race_ids"]:
            r=by_id.get(rid)
            reasons=[]
            if not r:
                reasons.append("missing_registry_entry")
            elif r.get("status")!="reviewed":
                reasons.append("awaiting_official_result_and_review")
            else:
                for field in ("result","settlements","performance","review","e2e_case"):
                    if not r.get(field):
                        reasons.append("missing_"+field)
                if rid not in strict:
                    reasons.append("grade_a_proof_not_validated")
                if r.get("id") not in strict:
                    reasons.append("missing_strict_e2e_entry")
            evaluated.append({"race_id":rid,"date":r.get("date") if r else None,
                              "formal_state":"complete" if not reasons else "pending",
                              "reasons":list(dict.fromkeys(reasons))})
        complete=bool(evaluated) and all(x["formal_state"]=="complete" for x in evaluated) and not formal_errors
        comparable=(e2e.get("comparison") or {}).get("state") not in (None,"insufficient_data")
        decision="not_evaluated" if not complete else ("pending_A_B_C_approval" if comparable else "no_change")
        meetings.append({"meeting_id":meeting["meeting_id"],"dates":meeting["dates"],
                         "registered_races":sum(rid in by_id for rid in meeting["expected_main_race_ids"]),
                         "expected_races":len(meeting["expected_main_race_ids"]),
                         "formal_grade_a_review_state":"complete" if complete else "pending",
                         "races":evaluated,
                         "weekly_improvement_decision":decision,
                         "decision_reason":("all_main_races_reviewed_and_comparable_evidence_needs_manual_approval" if decision=="pending_A_B_C_approval" else
                            "all_main_races_reviewed_but_insufficient_paired_e2e_evidence" if decision=="no_change" else
                            "all_registered_main_races_including_holiday_monday_must_be_reviewed_before_weekly_decision")})
    gaps=shadow.get("errors") or []
    shadow_observations=sum(v.get("coverage",{}).get("entries_with_experience",0) for v in (shadow.get("versions") or {}).values())
    return {
        "schema_version":1,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "policy":{"formal_grade_a_independent_of_research":True,
                  "never_reconstruct_missing_prerace_experience":True,
                  "no_changes_to_frozen_predictions_or_final_bets":True,
                  "automatic_promotion":False,
                  "weekly_approval":"A/B/C manual rules retained"},
        "latest_formal_prompt_version":latest_version,
        "formal_grade_a":{"passed":not formal_errors,"validated_case_count":(e2e.get("case_counts") or {}).get("strict",0),
                          "errors":formal_errors},
        "shadow_research":{"state":"evidence_incomplete" if gaps else ("observations_ready" if shadow_observations else "no_observations"),
                           "prerace_evidence_gap_count":len(gaps),
                           "evidence_gaps":[{"race_id":g.get("race_id"),"version":g.get("version"),"cause":g.get("error"),
                                             "source":"sealed_prediction_missing_prerace_fields"} for g in gaps],
                           "covered_prediction_entries":shadow_observations,
                           "does_not_block_formal_grade_a":True,
                           "does_block_shadow_promotion":bool(gaps) or not shadow_observations},
        "meetings":meetings,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="docs/data/jra_review_completion.json")
    args=p.parse_args()
    data=evaluate(read("docs/data/races.json"),read("docs/data/e2e_status.json"),
                  read("docs/data/experience_regime_status.json"),read("docs/data/jra_postrace_meetings_v1.json"),
                  read("docs/data/latest_prompt.json").get("version"))
    dest=ROOT/args.output;dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"formal":data["formal_grade_a"]["passed"],
                      "shadow":data["shadow_research"]["state"],
                      "meetings":[{"id":m["meeting_id"],"state":m["formal_grade_a_review_state"],"decision":m["weekly_improvement_decision"]} for m in data["meetings"]]},ensure_ascii=False))
    return 0 if data["formal_grade_a"]["passed"] else 1

if __name__=="__main__":
    raise SystemExit(main())
