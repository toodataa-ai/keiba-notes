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
    result=validate_known_gaps(report.get("errors"),ledger["entries"],hash_case)
    # This is a CI success for no NEW integrity regressions, NOT a claim that
    # research evidence is complete. Existing missing cases remain unusable.
    print("SHADOW_CI_INTEGRITY_PASS:",json.dumps(result,ensure_ascii=False))
    print("SHADOW_RESEARCH_NOT_PROMOTABLE: verified prestart omissions retained and excluded")
if __name__=="__main__":
    main()
