#!/usr/bin/env python3
"""Audit the prereace evidence / model contract and only then score true future A/B.

No synthetic probabilities, retrospectively generated challenger, or outcome-based
model choices. This scorer is called only with two independent predictions that
were committed before the race, plus later official verified results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REGIMES=("E0","E1","E2")


def load(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))


def when(text:str):
    value=datetime.fromisoformat(text.replace("Z","+00:00"))
    if not value.tzinfo: raise ValueError("timezone_required")
    return value


def first_commit_verified(path:Path, deadline:datetime, *, root:Path=ROOT)->dict:
    relative=path.relative_to(root).as_posix()
    entries=subprocess.check_output(
        ["git","log","--diff-filter=A","--reverse","--format=%H %cI","--",relative],
        cwd=root,text=True).strip().splitlines()
    if len(entries)!=1: raise ValueError("no_unique_first_introduction_git_proof:"+relative)
    commit,at=entries[0].split()
    if when(at)>=deadline:raise ValueError("after_start_prediction_or_evidence_prohibited:"+relative)
    original=subprocess.check_output(["git","show",commit+":"+relative],cwd=root)
    if original!=path.read_bytes():
        raise ValueError("original_predictive_snapshot_modified:"+relative)
    return {"first_commit":commit,"first_committed_at":at,
            "sha256":hashlib.sha256(original).hexdigest()}


def validate_source_proof(proof:dict, capture:dict, deadline:datetime):
    if proof["proof_type"]!="prestart_Git_introduction_source_hash_commitment_no_predictions":
        raise ValueError("not_source_evidence_proof")
    if when(proof["start_at"])!=deadline or capture["race_id"]!=proof["race_id"]:
        raise ValueError("race_identity_mismatch")
    if when(capture["source"]["fetched_at"])>=deadline:
        raise ValueError("poststart_evidence")
    canon=(json.dumps(capture,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"))+"\n").encode("utf-8")
    digest=hashlib.sha256(canon).hexdigest()
    if digest!=proof["factual_observations_canonical_sha256"]:
        raise ValueError("workout_artifact_sha_mismatch")
    if capture["source"]["html_sha256"]!=proof["source_page_html_sha256"]:
        raise ValueError("source_page_sha_mismatch")
    if not proof["formal_step1_2_and_bets_untouched"] or proof["production_effect"]:
        raise ValueError("source_proof_changed_production")


def validate_pred(pred:dict, rid:str, start:datetime)->dict:
    if pred["race_id"]!=rid or when(pred["start_at"])!=start or when(pred["frozen_at"])>=start:
        raise ValueError("prerace_prediction_identity_or_timing_invalid")
    if pred.get("odds_used_in_STEP1") is not False or pred.get("no_results_or_outcomes_used") is not True:
        raise ValueError("STEP1_not_proved_price_and_result_blind")
    runners=pred.get("runners",[])
    if not runners: raise ValueError("no_probabilistic_runner_predictions")
    seen=set()
    summation=0
    parsed={}
    for x in runners:
        n=x["horse_number"]
        if n in seen or not isinstance(n,int) or n<1:
            raise ValueError("duplicated_horse_number")
        seen.add(n)
        win=x.get("win_probability")
        top3=x.get("top3_probability")
        if not all(isinstance(t,(float,int)) and not isinstance(t,bool) and 0<=t<=1
                   for t in (win,top3)):
            raise ValueError("not_calibrated_float_input")
        if top3+1e-10<win:
            raise ValueError("top3_below_win")
        reg=x["regime"]
        if reg not in REGIMES:raise ValueError("unknown_immutable_experience_regime")
        summation+=win
        parsed[n]={"win":float(win),"top3":float(top3),"regime":reg}
    if abs(summation-1)>0.025:raise ValueError("win_probability_sum_not_normalized")
    return parsed


def _brier(vs:dict, actual:dict)->dict:
    def val(predictions, label):
        return round(sum((x[label]-int(actual[n][label]))**2 for n,x in predictions.items())/len(predictions),7)
    byreg={}
    for reg in REGIMES:
        r={n:x for n,x in vs.items() if x["regime"]==reg}
        byreg[reg]={"horses":len(r), "brier_win":val(r,"win") if r else None,
                   "brier_top3":val(r,"top3") if r else None}
    return {"horses":len(vs),"brier_win":val(vs,"win"),
            "brier_top3":val(vs,"top3"),"by_regime":byreg}


def compare(*, proof:dict, captured:dict, legacy:dict|None,
            challenger:dict|None, result:dict|None)->dict:
    start=when(proof["start_at"])
    validate_source_proof(proof,captured,start)
    common={
        "race_id":proof["race_id"],"source_evidence_sha_verified":True,
        "original_JRA_bets_untouched":True,
        "workout_prediction_effect_not_assumed":True,
        "roi_old":None,"roi_new":None,
        "user_e012_grade_a_not_claimed":True
    }
    if legacy is None or challenger is None:
        return {**common,"status":"awaiting_both_independently_frozen_prestart_predictions",
                "prediction_accuracy":None}
    old=validate_pred(legacy,proof["race_id"],start)
    new=validate_pred(challenger,proof["race_id"],start)
    if set(old)!=set(new) or any(old[n]["regime"]!=new[n]["regime"] for n in old):
        raise ValueError("same_field_and_regime_required")
    if result is None:
        return {**common,"status":"awaiting_official_verified_results",
                "prediction_accuracy":None,"field_size":len(old)}
    if result.get("official_result_final") is not True or result.get("race_id")!=proof["race_id"]:
        raise ValueError("official_result_finalization_required")
    if when(result["published_at"])<start:raise ValueError("result_time_precedes_race")
    finishing=result.get("finish_order")
    if (not isinstance(finishing,list) or len(finishing)<3 or
            set(finishing)!=set(old) or len(finishing)!=len(set(finishing))):
        raise ValueError("official_finish_order_and_field_mismatch")
    actual={n:{"win":n==finishing[0],"top3":n in finishing[:3]} for n in old}
    a=_brier(old,actual)
    b=_brier(new,actual)
    return {**common,"status":"prospective_brier_computed_descriptive_not_approval",
            "field_size":len(old),"legacy":a,"challenger":b,
            "challenger_minus_legacy_brier_win":round(b["brier_win"]-a["brier_win"],7),
            "challenger_minus_legacy_brier_top3":round(b["brier_top3"]-a["brier_top3"],7),
            "interpretation":"Lower Brier is better. One race cannot establish stable improvement or ROI.",
            "formal_promotion_allowed":False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--proof-json",required=True)
    ap.add_argument("--evidence-json",required=True)
    ap.add_argument("--legacy-json")
    ap.add_argument("--challenger-json")
    ap.add_argument("--result-json")
    args=ap.parse_args()
    if bool(args.legacy_json)!=bool(args.challenger_json):
        raise SystemExit("Both prestart predictions required, not one posthoc comparator")
    proofpath=Path(args.proof_json)
    p=load(proofpath)
    deadline=when(p["start_at"])
    gitproof=first_commit_verified(proofpath,deadline)
    # A real existing legacy and a separately sealed challenger are required.
    # Comparing against a newly invented historical forecast is prohibited.
    prediction_proofs=None
    if args.legacy_json and args.challenger_json:
        prediction_proofs={
            "legacy":first_commit_verified(Path(args.legacy_json),deadline),
            "challenger":first_commit_verified(Path(args.challenger_json),deadline)
        }
    result=compare(proof=p,captured=load(Path(args.evidence_json)),
                   legacy=load(Path(args.legacy_json)) if args.legacy_json else None,
                   challenger=load(Path(args.challenger_json)) if args.challenger_json else None,
                   result=load(Path(args.result_json)) if args.result_json else None)
    result["source_hash_proof_first_commit"]=gitproof
    result["two_prestart_prediction_first_commit_proofs"]=prediction_proofs
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
