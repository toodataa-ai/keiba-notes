#!/usr/bin/env python3
"""Prospective-only source permission gate and non-publishing hash commitment.

Never evaluates horse performance and never changes JRA/Shadow predictions.
Before collecting from a third party, require independent explicit permission.
Persist only a source/evidence digest and counts in Git before scheduled post.
A Git first-introduction timestamp is the real proof, not a declared timestamp.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
JST=ZoneInfo("Asia/Tokyo")
ALLOWED_STATUSES={"permission_unverified","permission_denied","explicitly_granted"}


def _read(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _time(value:str):
    stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("naive_datetime_prohibited")
    return stamp


def permission_gate(source_url:str, policy:dict)->dict:
    p=urlparse(source_url)
    if p.scheme!="https" or not p.hostname or p.username or p.password:
        raise ValueError("https_public_source_only")
    if policy.get("schema_version")!=1 or policy.get("default_decision")!="block_automated_git_commit_until_explicit_reuse_grant":
        raise ValueError("permission_policy_invalid_or_default_open")
    entry=next((s for s in policy.get("sources",[])
       if s.get("host")==p.hostname and p.path.startswith(s.get("approved_article_prefix","/INVALID/"))),None)
    if not entry: raise ValueError("source_not_in_permission_registry")
    status=entry.get("automatic_reuse")
    if status not in ALLOWED_STATUSES:raise ValueError("unknown_permission_state")
    if status!="explicitly_granted":
        raise PermissionError("PUBLISHER_PERMISSION_NOT_VERIFIED: must obtain explicit consent before automatic reuse")
    evidence=entry.get("permission_evidence_url")
    granted=entry.get("permission_granted_at")
    if not (entry.get("rights_owner_verified") is True and isinstance(evidence,str) and
            evidence.startswith("https://") and isinstance(granted,str) and _time(granted)):
        raise ValueError("unverified_permission_document_or_rights_owner")
    if entry.get("public_redistribution") not in ("approved","not_approved"):
        raise ValueError("redistribution_scope_must_be_explicit")
    return {"host":p.hostname, "permission_evidence_url":evidence,
            "permission_granted_at":granted,
            "public_redistribution":entry["public_redistribution"]}


def user_requested_single_article_gate(source_url:str, policy:dict, *, request_id:str)->dict:
    """One public article explicitly requested now, not permission for a crawler.

    Do not infer publisher consent. This mode only permits a minimal, nonpublic
    factual analysis, source attribution and a hash-only Git proof.
    A recurring workflow, autonomous URL discovery, scraping results,
    external redistribution or article copies remain disallowed.
    """
    p=urlparse(source_url)
    if (p.scheme!="https" or not p.hostname or p.username or p.password or
            p.query or p.fragment or p.port):
        raise ValueError("manual_public_https_exact_url_required")
    if (not isinstance(request_id,str) or not request_id.strip() or
            len(request_id)>128):
        raise ValueError("explicit_user_request_identifier_required")
    if policy.get("default_decision")!="block_automated_git_commit_until_explicit_reuse_grant":
        raise ValueError("scheduled_collection_must_remain_denied")
    entry=next((s for s in policy.get("sources",[]) if
        s.get("host")==p.hostname and
        p.path.startswith(s.get("approved_article_prefix","/INVALID/"))),None)
    if entry is None:
        raise ValueError("single_article_host_not_allowlisted")
    manual=entry.get("manual_user_initiated_single_article") or {}
    expected={
        "decision":"allow_limited_factual_research_with_safeguards",
        "max_article_requests_per_user_dispatch":1,
        "require_explicit_source_url":True,
        "require_robots_allow":True,
        "allow_article_text_copy":False,
        "allow_editor_grade_copy":False,
        "allow_copyrighted_media_copy":False,
        "allow_public_clock_table_republication":False,
        "require_source_attribution_url":True,
        "require_prestart_frozen_jra_roster":True,
        "require_prestart_git_first_commit_for_proof":True,
    }
    for key,value in expected.items():
        if manual.get(key)!=value:
            raise ValueError("manual_one_article_safeguard_missing:"+key)
    if entry.get("public_redistribution")!="not_approved":
        raise ValueError("manual_mode_cannot_authorize_public_republication")
    if entry.get("automatic_reuse") not in ALLOWED_STATUSES:
        raise ValueError("unknown_scheduled_permission")
    return {"host":p.hostname,"permission_evidence_url":None,
            "public_redistribution":"not_approved",
            "source_access_basis":"user_initiated_one_public_article_factual_nonpublic_research",
            "explicit_request_id":request_id,
            "publisher_automatic_harvesting_permission_claimed":False}


def validate_captured(capture:dict,*,now:datetime):
    start=_time(capture["start_at"])
    capture_time=_time(capture["source"]["fetched_at"])
    if not (capture_time < start and now < start):
        raise ValueError("after_start_capture_or_commit")
    if capture.get("prediction_rank_grade_bets_unchanged") is not True:
        raise ValueError("would_change_existing_prediction")
    if capture.get("production_effect") is not False or capture.get("no_odds_or_results_used") is not True:
        raise ValueError("would_use_result_or_change_formal")
    if capture.get("workout_factor_grades") is not None or capture.get("workout_score_calibrated") is not False:
        raise ValueError("unverified_workout_grades_not_allowed")
    if not capture.get("before_post") or capture.get("verified_horses",0)<1:
        raise ValueError("missing_verified_prestart_horses")
    source=capture["source"]
    if len(source["html_sha256"])!=64:
        raise ValueError("missing_html_source_digest")
    if source.get("article_published_at") and _time(source["article_published_at"]) >= start:
        raise ValueError("article_postrace_republication")
    names=set()
    numbers=set()
    sessions=0
    for horse in capture.get("observations",[]):
        n=horse.get("horse_number")
        name=horse.get("horse_name")
        if not isinstance(n,int) or n<1 or not name or n in numbers or name in names:
            raise ValueError("duplicate_or_invalid_horse_in_observations")
        numbers.add(n)
        names.add(name)
        for row in horse.get("workouts",[]):
            splits=row.get("split_seconds",{})
            if set(splits)!={"6F","5F","4F","3F","1F"} or not any(v is not None for v in splits.values()):
                raise ValueError("source_workout_not_numeric_valid")
            if not row.get("session") or row.get("observed_split_count",0)<1:
                raise ValueError("workout_session_missing")
            sessions+=1
    if len(names)!=capture["verified_horses"] or capture["roster_horses"]<len(names):
        raise ValueError("workout_coverage_mismatch")
    if not capture.get("frozen_roster_proof",{}).get("commit_sha"):
        raise ValueError("immutable_roster_Git_commit_missing")
    return {"horses":len(names),"sessions":sessions,"start_at":start.isoformat()}


def build_commitment(capture:dict, *, now:datetime, policy:dict,
                     manual_request_id:str|None=None)->dict:
    grant=(user_requested_single_article_gate(
        capture["source"]["url"],policy,request_id=manual_request_id)
        if manual_request_id is not None else permission_gate(capture["source"]["url"],policy))
    coverage=validate_captured(capture,now=now)
    # Content-addressed proof of the WHOLE observed per-horse JSON, without
    # redistributing third-party timing tables on public GitHub Pages.
    facts_bytes=(json.dumps(capture,ensure_ascii=False,sort_keys=True,
                            separators=(",",":"))+"\n").encode("utf-8")
    digest=hashlib.sha256(facts_bytes).hexdigest()
    return {
      "schema_version":1,
      "proof_type":"prestart_Git_introduction_source_hash_commitment_no_predictions",
      "race_id":capture["race_id"],"week_id":capture["week_id"],
      "start_at":coverage["start_at"],"captured_at":capture["source"]["fetched_at"],
      "declared_git_commit_request_at":now.isoformat(),
      "source_article_url":capture["source"]["url"],
      "source_page_html_sha256":capture["source"]["html_sha256"],
      "factual_observations_canonical_sha256":digest,
      "canonical_format":"utf8_json_sorted_keys_compact_separators_trailing_newline",
      "roster_frozen_git_proof":capture["frozen_roster_proof"],
      "research_horses_with_source":coverage["horses"],
      "research_workout_sessions_with_source":coverage["sessions"],
      "rights_permission_document_url":grant["permission_evidence_url"],
      "source_access_mode":grant.get("source_access_basis","publisher_explicitly_approved"),
      "manual_request_id":grant.get("explicit_request_id"),
      "publisher_automatic_permission_claimed":grant.get("publisher_automatic_harvesting_permission_claimed",True),
      "article_or_editorial_content_published":False,
      "source_attribution_url":capture["source"]["url"],
      "third_party_detail_published":False,
      "prediction_created":False,"prediction_modified":False,
      "formal_step1_2_and_bets_untouched":True,
      "outcome_or_odds_used":False,
      "proof_final_status":"PENDING_REAL_FIRST_GIT_COMMIT_AND_TIMESTAMP_CHECK",
      "production_effect":False
    }


def write_new_commitment(root:Path,capture:dict, now:datetime, policy:dict,
                         manual_request_id:str|None=None)->Path:
    result=build_commitment(capture,now=now,policy=policy,
                            manual_request_id=manual_request_id)
    week=capture["week_id"]
    race=capture["race_id"]
    if not (race.startswith(capture["start_at"][:10]) and
            len(race)<100 and all(c.isalnum() or c=="-" for c in race) and
            len(week)==10 and week[4]=="-" and week[7]=="-"):
        raise ValueError("invalid_race_or_week_path")
    destination=root/"experience_regime_v1"/"workout_proof_commitments"/week/(race+".json")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("x",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
        f.write("\n")
    return destination


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--capture-json",required=True)
    ap.add_argument("--permission-registry",default=str(ROOT/"experience_regime_v1/workout_source_permission_v1.json"))
    ap.add_argument("--output-root",default=str(ROOT))
    ap.add_argument("--user-requested-single-article",action="store_true")
    ap.add_argument("--manual-request-id")
    args=ap.parse_args()
    doc=_read(Path(args.capture_json))
    policy=_read(Path(args.permission_registry))
    # Distinguish one real user-triggered action from scheduled automation.
    manual=None
    if args.user_requested_single_article:
        if (os.environ.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or
                not os.environ.get("GITHUB_ACTOR") or
                not args.manual_request_id):
            raise SystemExit("MANUAL_MODE_REQUIRES_WORKFLOW_DISPATCH_USER_AND_RUN_ID")
        manual=args.manual_request_id
        user_requested_single_article_gate(doc["source"]["url"],policy,
                                           request_id=manual)
    else:
        permission_gate(doc["source"]["url"],policy)
    now=datetime.now(JST)
    path=write_new_commitment(Path(args.output_root),doc,now,policy,
                              manual_request_id=manual)
    print("PRESTART_SOURCE_HASH_COMMITMENT_CREATED_PENDING_GIT_PROOF",path)


if __name__=="__main__":
    main()
