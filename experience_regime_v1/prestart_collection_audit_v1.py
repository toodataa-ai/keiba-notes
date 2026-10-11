#!/usr/bin/env python3
"""Pre-race E0/E1/E2 source-evidence audit; no inferred lifetime starts.

Runs before immutable JRA proof. This audit is separate from official STEP1 and
bets and cannot modify either. Formal prediction can proceed with an explicitly
incomplete Shadow audit; Shadow research cannot use incomplete observations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

CATEGORIES={"debut","maiden","class_1","class_2","class_3","open_listed","graded"}
ORIGINS={"official_prediction","stratified_sample"}
ROOT=Path(__file__).resolve().parents[1]

def audit(payload, input_bytes:bytes, at:datetime):
    ctx=payload.get("race_context") or {}
    if not isinstance(ctx,dict):
        raise ValueError("race_context must be a dictionary")
    start_raw=ctx.get("start_at")
    if not start_raw:
        raise ValueError("start_at must exist for the before-race audit")
    start=datetime.fromisoformat(start_raw.replace("Z","+00:00"))
    if start.tzinfo is None or at.tzinfo is None:
        raise ValueError("timezone-aware start and observation timestamps required")
    if at>=start:
        raise ValueError("race already started; do not create new prereace evidence")
    runners=((payload.get("step1") or {}).get("runners") or [])
    if not runners:
        raise ValueError("cannot audit unpopulated horse field")
    field={str(int(x["horse_number"])) for x in runners}
    gaps=[]
    if ctx.get("race_category") not in CATEGORIES:
        gaps.append("race_context.race_category")
    if ctx.get("sample_origin") not in ORIGINS:
        gaps.append("race_context.sample_origin")
    exp=payload.get("experience") or {}
    entries=exp.get("horses") if isinstance(exp,dict) else None
    if not isinstance(entries,dict):
        gaps.extend("experience.horses["+key+"]" for key in sorted(field,key=int))
    else:
        from experience_regime_v1.model import classify_regime
        for key in sorted(field,key=int):
            horse=entries.get(key)
            if not isinstance(horse,dict):
                gaps.append("experience.horses["+key+"]")
                continue
            try:
                regime=classify_regime(horse.get("starts_before_race"))
                if horse.get("regime") not in (None,regime):
                    raise ValueError("regime mismatch")
                source_url=horse.get("source_url")
                observed_at=horse.get("observed_at")
                if not source_url or not isinstance(source_url,str) or not source_url.startswith("https://"):
                    raise ValueError("missing HTTPS source")
                if not observed_at:
                    raise ValueError("missing observation time")
                observed=datetime.fromisoformat(observed_at.replace("Z","+00:00"))
                if observed.tzinfo is None or observed>at or observed>=start:
                    raise ValueError("observation not verified before start")
            except (ValueError,TypeError):
                gaps.append("experience.horses["+key+"] verified start/source")
    return {"schema_version":1,"race_id":payload.get("race_id"),
            "mode":"shadow_only","production_effect":False,"origin":"prestart_collection_input",
            "source_input_sha256":hashlib.sha256(input_bytes).hexdigest(),
            "captured_at":at.isoformat(),"race_start_at":start.isoformat(),
            "required_horse_count":len(field),"status":"evidence_incomplete" if gaps else "complete",
            "usable_for_e012_shadow":not bool(gaps),"missing_prerace_evidence":gaps,
            "rules":{"lifetime_starts_must_be_source_verified":True,
                     "past_performances_count_is_not_lifetime_starts":True,
                     "never_fill_gaps_after_start":True,
                     "formal_step1_and_final_bets_unaffected":True}}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--require-complete",action="store_true")
    args=parser.parse_args()
    inp=Path(args.input);out=Path(args.output)
    if inp.is_absolute() or out.is_absolute() or ".." in inp.parts or ".." in out.parts:
        raise SystemExit("Unsafe path")
    if not inp.is_file() or out.exists():
        raise SystemExit("Source input missing or immutable audit already exists")
    b=inp.read_bytes()
    report=audit(json.loads(b),b,datetime.now(timezone.utc))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("JRA_SHADOW_PRERACE_AUDIT",report["race_id"],report["status"],
          "missing_fields",len(report["missing_prerace_evidence"]))
    return 1 if args.require_complete and not report["usable_for_e012_shadow"] else 0

if __name__=="__main__":
    raise SystemExit(main())
