#!/usr/bin/env python3
"""Publish E0/E1/E2 research-only aggregate status after immutable first proof.
Never rewrites formal prediction, existing E2E, betting, or legacy analytical scores.
"""
import json
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def build_run(week,date):
    folder=ROOT/"experience_regime_v1"/"collection"/week
    pool=read(folder/"race_pool.json")
    plan=read(folder/"sample_plan.json")
    proof=read(folder/("proof_commit_"+date+".json"))
    summary=read(folder/("coverage_gap_"+date+".json"))
    verified=Counter()
    per_category={}
    captured_ids=[]
    complete_ids=[]
    audit_errors=[]
    for race in proof["races"]:
        rid=race["race_id"]
        snap=folder/"snapshots"/(rid+".json")
        audit=folder/"audits"/(rid+".json")
        if not snap.exists() or not audit.exists():
            audit_errors.append({"race_id":rid,"reason":"missing_snapshot_or_audit"})
            continue
        s=read(snap);a=read(audit)
        if not race.get("proof_prestart_valid"):
            audit_errors.append({"race_id":rid,"reason":"proof_not_before_start"})
            continue
        captured_ids.append(rid)
        if a["usable_for_e012_shadow"]:
            complete_ids.append(rid)
        else:
            audit_errors.append({"race_id":rid,"reason":"incomplete_source_evidence",
                  "missing":a.get("missing_prerace_evidence",[])})
        cat=s["race_context"]["race_category"]
        for entry in s["experience"]["horses"].values():
            regime=entry.get("regime")
            if regime not in ("E0","E1","E2"):continue
            if entry.get("starts_before_race") is None:continue
            verified[regime+"_horse_observations"]+=1
            per_category.setdefault(cat,Counter())[regime]+=1
    planned_today=[x for x in plan["selected_races"] if x["date"]==date]
    gap_reasons=Counter(x["reason"] for x in summary["coverage_gaps"])
    planned_exclusions=gap_reasons.get("not_selected_by_fixed_weekly_plan",0)
    collection_failures=sum(v for k,v in gap_reasons.items() if k!="not_selected_by_fixed_weekly_plan")
    types={c:dict(r) for c,r in per_category.items()}
    run={"week_id":week,"date":date,"population_today":summary["population_today_count"],
         "population_week":len(pool["races"]),"target_stratified_week":sum(
              x["target_stratified_races"] for x in plan["category_summary"].values()),
         "selected_week":plan["selected_race_count"],"selected_today":len(planned_today),
         "selected_today_races":[{"race_id":x["race_id"],"venue":x["venue"],"race_no":x["race_no"],
           "race_category":x["race_category"],"sample_origin":x["sample_origin"]} for x in planned_today],
         "category_plan_summary":plan["category_summary"],
         "proof_commit":proof["proof_commit"],"proof_commit_at":proof["proof_commit_at"],
         "prerace_proof_valid_races":len(captured_ids),
         "complete_evidence_races":len(complete_ids),
         "complete_evidence_race_ids":complete_ids,
         "regimes":{k:{"horse_observations":verified[k+"_horse_observations"],
                 "races":sum(1 for x in proof["races"] if x["proof_prestart_valid"] and
                         k in x.get("regime_counts",{}))}
                     for k in ("E0","E1","E2")},
         "category_regime_verified_horses":types,
         "collection_gaps":len(summary["coverage_gaps"]),
         "planned_exclusions":planned_exclusions,
         "collection_failures":collection_failures,
         "gap_reasons":dict(gap_reasons),
         "collection_errors":audit_errors,
         "step1_prediction_scope":"only preserved official control if a verified immutable source exists; otherwise unavailable",
         "models_automatically_promoted":False,"production_effect":False}
    return run

def main(week,date):
    out=ROOT/"docs/data/experience_regime_status.json"
    existing=read(out)
    run=build_run(week,date)
    existing.setdefault("collection_runs",{})[date]=run
    # Proof-derived stable timestamp avoids repeated E2E-generated no-op commits.
    proof=read(ROOT/"experience_regime_v1"/"collection"/week/("proof_commit_"+date+".json"))
    existing["last_collection_audit_at"]=proof["generated_at"]
    out.write_text(json.dumps(existing,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("E012_PUBLIC_STATUS_UPDATED",date,run["prerace_proof_valid_races"],run["complete_evidence_races"],run["regimes"],flush=True)
if __name__=="__main__":
    main(*sys.argv[1:])
