#!/usr/bin/env python3
"""Fail-closed CI gate for SHA-pinned historical Shadow gaps.

Formal E2E is independently validated in evaluate.py. An exact list of immutable
research omissions is permitted as DISCLOSED in general CI, never represented
as complete Shadow evidence. Any unexpected error or modified archived case
fails this gate.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"e2e_validation/experience_archived_gaps_v1.json"
REPORT=ROOT/"docs/data/experience_regime_status.json"

def validate_known_gaps(errors, entries, blob_sha_lookup):
    if not isinstance(errors,list) or not isinstance(entries,list):
        raise ValueError("invalid Shadow error/ledger list")
    indexed={}
    for item in entries:
        path=item["case"]
        if path in indexed or not path.startswith("e2e_validation/cases/") or not path.endswith("/case.json"):
            raise ValueError("invalid or duplicate pinned case path: "+path)
        expected_sha=item["sha"]
        if not isinstance(expected_sha,str) or len(expected_sha)!=40:
            raise ValueError("invalid pinned blob SHA")
        actual_sha=blob_sha_lookup(path)
        if actual_sha!=expected_sha:
            raise ValueError("frozen case modified: "+path)
        indexed[path]={k:item[k] for k in ("case","race_id","version","grade","error")}
    if len({e.get("case") for e in errors}) != len(errors):
        raise ValueError("duplicate Shadow errors")
    observed={e.get("case"):e for e in errors}
    if set(observed)!=set(indexed):
        raise ValueError("unexpected or missing Shadow errors: "+json.dumps({
            "new":sorted(set(observed)-set(indexed)),
            "disappeared":sorted(set(indexed)-set(observed))},ensure_ascii=False))
    for key, baseline in indexed.items():
        if observed[key]!=baseline:
            raise ValueError("historical Shadow error changed: "+key)
    return {"disclosed_archived_gaps":len(entries),"new_shadow_regressions":0,
            "shadow_promotable":not bool(entries),"formal_grade_a_gate_independent":True}

def hash_case(path):
    return subprocess.check_output(["git","hash-object",path],cwd=ROOT,text=True).strip()

def main():
    p=subprocess.run([sys.executable,"experience_regime_v1/analyze.py",
         "--cases","e2e_validation/cases","--output",
         "docs/data/experience_regime_status.json","--allow-errors"],
         cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    if p.returncode:
        raise RuntimeError("E0/E1/E2 analyzer failed: "+p.stderr)
    ledger=json.loads(LEDGER.read_text(encoding="utf-8"))
    if ledger.get("schema_version")!=1 or ledger.get("scope")!="historical_known_prerace_e012_shadow_gaps":
        raise RuntimeError("unrecognized research gap ledger")
    if not all(ledger.get("policy",{}).get(k) is True for k in
               ("exact_case_blob_sha_required","exact_error_set_required",
                "unknown_error_blocks_ci","historical_source_reconstruction_forbidden",
                "graded_studies_must_exclude_gaps","shadow_promotion_blocked_while_gaps_exist")):
        raise RuntimeError("Shadow protection policy weakened")
    report=json.loads(REPORT.read_text(encoding="utf-8"))
    # The original five missing-prestart research cases are historically SHA-pinned.
    # Subsequent cases are separately reviewed and SHA-pinned without rewriting
    # the immutable v1 archived-gap ledger.
    supplement_meta=json.loads((ROOT/"docs/data/jra_current_e2e_ci_supersession_v1.json").read_text(encoding="utf-8")).get("new_reviewed_shadow_gap_ledger")
    if not isinstance(supplement_meta,dict) or supplement_meta.get("path")!="e2e_validation/experience_new_gaps_20261017_v1.json":
        raise RuntimeError("missing reviewed 2026-10-17 shadow gap supplement")
    supplement_path=ROOT/supplement_meta["path"]
    actual_ledger_sha=subprocess.check_output(["git","hash-object",str(supplement_path)],cwd=ROOT,text=True).strip()
    if actual_ledger_sha!=supplement_meta["git_blob_sha"]:
        raise RuntimeError("reviewed shadow gap supplement SHA changed")
    addition=json.loads(supplement_path.read_text(encoding="utf-8"))
    expected_ids={"2026-10-17-fuji-stakes","2026-10-17-hokuriku-stakes","2026-10-17-tourmaline-stakes"}
    observed_ids={e.get("race_id") for e in addition.get("entries",[])}
    if (addition.get("schema_version")!=1 or addition.get("scope")!="explicitly_reviewed_additional_missing_prerace_shadow_evidence"
        or observed_ids!=expected_ids or len(addition["entries"])!=3 or
        not all(addition.get("policy",{}).get(k) is True for k in ("case_git_blob_sha_required","exact_error_set_required","do_not_backfill_postrace","formal_grade_a_independent","shadow_promotion_blocked"))):
        raise RuntimeError("reviewed shadow gap supplement not explicitly authorized")
    result=validate_known_gaps(report.get("errors"),ledger["entries"]+addition["entries"],hash_case)
    # This is a CI success for no NEW integrity regressions, NOT a claim that
    # research evidence is complete. Existing missing cases remain unusable.
    print("SHADOW_CI_INTEGRITY_PASS:",json.dumps(result,ensure_ascii=False))
    print("SHADOW_RESEARCH_NOT_PROMOTABLE: verified prestart omissions retained and excluded")
if __name__=="__main__":
    main()
