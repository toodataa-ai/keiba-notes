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

    # New Oct18 formal Grade A cases also lack original prestart E0/E1/E2 race_category.
    # Preserve and SHA-pin both earlier ledgers; disclose exact new omissions only.
    extra_meta=json.loads((ROOT/"docs/data/jra_current_e2e_ci_supersession_v1.json").read_text(encoding="utf-8")).get("new_reviewed_shadow_gap_ledger_20261018")
    if not isinstance(extra_meta,dict) or extra_meta.get("path")!="e2e_validation/experience_new_gaps_20261018_v1.json":
        raise RuntimeError("missing reviewed 2026-10-18 shadow gap supplement")
    extra_path=ROOT/extra_meta["path"]
    extra_sha=subprocess.check_output(["git","hash-object",str(extra_path)],cwd=ROOT,text=True).strip()
    if extra_sha!=extra_meta.get("git_blob_sha"):
        raise RuntimeError("reviewed 2026-10-18 shadow supplement SHA changed")
    extra=json.loads(extra_path.read_text(encoding="utf-8"))
    required={"2026-10-18-brazil-cup","2026-10-18-niigata-himba-stakes","2026-10-18-shuka-sho"}
    if (extra.get("schema_version")!=1 or extra.get("scope")!="explicitly_reviewed_additional_missing_prerace_shadow_evidence"
        or {e.get("race_id") for e in extra.get("entries",[])}!=required
        or len(extra["entries"])!=3
        or not all(extra.get("policy",{}).get(k) is True for k in
            ("case_git_blob_sha_required","exact_error_set_required","do_not_backfill_postrace","formal_grade_a_independent","shadow_promotion_blocked"))):
        raise RuntimeError("2026-10-18 shadow omissions not separately reviewed and pinned")
    # Oct 24 Grade A cases are valid but missing separate prestart E0/E1/E2 fields.
    # SHA-pin each additional deficiency without rewriting historical gap ledgers.
    today_meta=json.loads((ROOT/"docs/data/jra_current_e2e_ci_supersession_v1.json").read_text(encoding="utf-8")).get("new_reviewed_shadow_gap_ledger_20261024")
    today_rel="e2e_validation/experience_new_gaps_20261024_v1.json"
    if not isinstance(today_meta,dict) or today_meta.get("path")!=today_rel:
        raise RuntimeError("missing 2026-10-24 research-only omission supplement")
    today_path=ROOT/today_rel
    today_sha=subprocess.check_output(["git","hash-object",str(today_path)],cwd=ROOT,text=True).strip()
    if today_sha!=today_meta.get("git_blob_sha"):
        raise RuntimeError("2026-10-24 research gap ledger SHA mismatch")
    today=json.loads(today_path.read_text(encoding="utf-8"))
    required_today={"2026-10-24-artemis-stakes","2026-10-24-cassiopeia-stakes","2026-10-24-uonuma-stakes"}
    if (today.get("schema_version")!=1 or today.get("scope")!="explicitly_reviewed_additional_missing_prerace_shadow_evidence"
        or {e.get("race_id") for e in today.get("entries",[])}!=required_today
        or len(today["entries"])!=3
        or not all(today.get("policy",{}).get(k) is True for k in
            ("case_git_blob_sha_required","exact_error_set_required","do_not_backfill_postrace","formal_grade_a_independent","shadow_promotion_blocked"))):
        raise RuntimeError("2026-10-24 research gaps not separately reviewed and pinned")
    # 2026-10-25 three formal Grade A cases are valid, but E0/E1/E2 race_category
    # was not present in the immutable prereace records. Record exact original
    # blob SHAs and errors in a distinct research-only supplement; never alter
    # any prior ledger or synthesize postrace context.
    oct25_meta=json.loads((ROOT/"docs/data/jra_current_e2e_ci_supersession_v1.json").read_text(encoding="utf-8")).get("new_reviewed_shadow_gap_ledger_20261025")
    oct25_rel="e2e_validation/experience_new_gaps_20261025_v1.json"
    if not isinstance(oct25_meta,dict) or oct25_meta.get("path")!=oct25_rel:
        raise RuntimeError("missing separately reviewed 2026-10-25 research omissions")
    oct25_path=ROOT/oct25_rel
    oct25_sha=subprocess.check_output(["git","hash-object",str(oct25_path)],cwd=ROOT,text=True).strip()
    if oct25_sha!=oct25_meta.get("git_blob_sha"):
        raise RuntimeError("2026-10-25 pinned research gap ledger SHA mismatch")
    oct25=json.loads(oct25_path.read_text(encoding="utf-8"))
    required_oct25={"2026-10-25-kannazuki-stakes","2026-10-25-kikka-sho","2026-10-25-lumiere-autumn-dash"}
    if (oct25.get("schema_version")!=1
        or oct25.get("scope")!="explicitly_reviewed_additional_missing_prerace_shadow_evidence"
        or {e.get("race_id") for e in oct25.get("entries",[])}!=required_oct25
        or len(oct25["entries"])!=3
        or oct25.get("earlier_baseline_path")!=today_rel
        or not all(oct25.get("policy",{}).get(k) is True for k in
            ("case_git_blob_sha_required","exact_error_set_required","do_not_backfill_postrace","formal_grade_a_independent","shadow_promotion_blocked"))):
        raise RuntimeError("2026-10-25 missing prereace research evidence not fully reviewed and pinned")
    result=validate_known_gaps(report.get("errors"),ledger["entries"]+addition["entries"]+extra["entries"]+today["entries"]+oct25["entries"],hash_case)
    # This is a CI success for no NEW integrity regressions, NOT a claim that
    # research evidence is complete. Existing missing cases remain unusable.
    print("SHADOW_CI_INTEGRITY_PASS:",json.dumps(result,ensure_ascii=False))
    print("SHADOW_RESEARCH_NOT_PROMOTABLE: verified prestart omissions retained and excluded")
if __name__=="__main__":
    main()
