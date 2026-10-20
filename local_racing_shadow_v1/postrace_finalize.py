#!/usr/bin/env python3
"""Fail-closed, idempotent NAR cancellation and settlement closure.

Only writes immutable cancellation results, mutable day analysis/diagnostics,
and a separate immutable payout/cancellation evidence record. Never writes
predictions or previously reviewed result/review artifacts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

from postrace import ROOT, CODES, JST, http_html, jread, sha256, git_proof, write_distinct, now

CANCEL = "CANCELLED_OFFICIAL"
FINAL = ROOT / "diagnostics"

def normalize(s):
    return unicodedata.normalize("NFKC", str(s or "")).replace("\u3000", " ")

def page_identity(soup, date, venue):
    text = normalize(soup.get_text(" ", strip=True))
    d = dt.date.fromisoformat(date)
    if not re.search(rf"{d.year}\s*年\s*{d.month}\s*月\s*{d.day}\s*日", text):
        raise ValueError("BLOCKED_OFFICIAL_DATE: Official page date mismatch")
    if venue not in text:
        raise ValueError("BLOCKED_OFFICIAL_VENUE: Official page venue mismatch")
    return text

def cancellation_numbers(text, date, venue):
    """Only an explicit, dated, venue-specific official cancellation notice qualifies."""
    d = dt.date.fromisoformat(date)
    results = {}
    for m in re.finditer("取り止め|取りやめ", text):
        notice = text[max(0, m.start()-180):m.end()+30]
        if venue not in notice or not re.search(rf"{d.month}\s*/\s*{d.day}", notice):
            continue
        left = notice[:notice.find(m.group(0))]
        matches = list(re.finditer(r"第\s*(\d{1,2})\s*競走", left))
        # A cancellation announcement must list the affected race numbers,
        # not merely a previous day's race or generic site-wide advisory.
        for match in matches:
            no = int(match.group(1))
            if 1 <= no <= 12:
                results[no] = notice.strip()
    return results

def refund_sections(text):
    """Separate official RefundMoneyList race blocks, excluding multi-race LOTO."""
    body = text.split("オッズパークLOTO", 1)[0]
    matches = list(re.finditer(r"(?<![0-9A-Za-z])([1-9]|1[0-2])\s*R\s+", body))
    sections = {}
    for i, match in enumerate(matches):
        no = int(match.group(1))
        part = body[match.end():matches[i+1].start() if i+1 < len(matches) else len(body)]
        if no in sections:
            raise ValueError(f"BLOCKED_PAYOUT_PARSE: duplicate official {no}R")
        sections[no] = part
    return sections

def confirmed_win_payout(section, result):
    """Confirm a real, positive single-win payout belonging to the official winner."""
    winners = [int(x["horse_no"]) for x in result["finish_order"]
               if x["finish_position"] == 1]
    matches = re.findall(r"単勝\s*(\d{1,2})\s*([\d,]+)\s*円", section)
    if not winners or len(matches) != len(winners):
        raise ValueError("BLOCKED_PAYOUT: missing payout or unsupported dead heat")
    payout_winners = [int(x[0]) for x in matches]
    if sorted(payout_winners) != sorted(winners):
        raise ValueError(f"BLOCKED_PAYOUT_JOIN: official winners {winners} != payouts {payout_winners}")
    amounts = [int(x[1].replace(",", "")) for x in matches]
    if not all(v > 0 for v in amounts):
        raise ValueError("BLOCKED_PAYOUT: invalid confirmed amount")
    return [{"horse_no": x, "amount_yen_per_100": y} for x, y in zip(payout_winners, amounts)]

def finalized(date):
    predictions = sorted((ROOT / "predictions" / date).glob("*.json"))
    if not predictions:
        raise ValueError("BLOCKED_NO_PREDICTIONS")
    summary_path = ROOT / "analysis" / f"{date}-summary.json"
    diagnostic_path = FINAL / f"{date}-postrace-run.json"
    proof_manifest = jread(Path("docs/data/local_racing_shadow_public.json"))
    old_summary = jread(summary_path)
    old_diag = jread(diagnostic_path)
    existing_evidence = FINAL / f"{date}-postrace-closure.json"
    old_evidence = jread(existing_evidence) if existing_evidence.exists() else None
    all_pred = {p.stem:jread(p) for p in predictions}
    if len(all_pred) != len(predictions):
        raise ValueError("BLOCKED_DUPLICATE_PREDICTION")
    official_venue = sorted({p["venue"] for p in all_pred.values()})
    official = {}
    for venue in official_venue:
        if venue not in CODES:
            raise ValueError(f"BLOCKED_UNKNOWN_VENUE: {venue}")
        params = {"k_babaCode":CODES[venue], "k_raceDate":date.replace("-","/")}
        list_page, list_url = http_html("RaceList", params)
        payout_page, refund_url = http_html("RefundMoneyList", params)
        list_text = page_identity(list_page, date, venue)
        refund_text = page_identity(payout_page, date, venue)
        notices = cancellation_numbers(list_text, date, venue)
        notices2 = cancellation_numbers(refund_text, date, venue)
        # Cancellation must appear in both NAR pages with matching race number.
        agreed = {no:notices[no] for no in notices.keys() & notices2.keys()}
        official[venue] = {"cancelled":agreed, "refund_sections":refund_sections(refund_text),
                           "race_list_url":list_url, "refund_url":refund_url}
    now_time = now()
    cancellations, payout_checks = {}, {}
    expected = set(all_pred)
    for path in predictions:
        p = all_pred[path.stem]
        rid = path.stem
        proof = git_proof(path,p)
        manifest_rows = [x for x in proof_manifest["races"] if x["race_id"] == rid]
        if len(manifest_rows) != 1 or manifest_rows[0]["proof_commit"] != proof:
            raise ValueError(f"BLOCKED_PROOF: {rid}")
        status = old_diag["races"][rid]["status"]
        info = official[p["venue"]]
        race_no = int(p["race_no"])
        result_path = ROOT / "results" / date / path.name
        review_path = ROOT / "reviews" / date / path.name
        if race_no in info["cancelled"]:
            if review_path.exists():
                raise ValueError(f"BLOCKED_CONFLICT: cancelled race has review {rid}")
            notice = info["cancelled"][race_no]
            proposed = {
                "race_id":rid,"date":date,"venue":p["venue"],"race_no":race_no,
                "official_source_url":info["race_list_url"],"official_observed_at":now_time,
                "official_going":None,"status":CANCEL,"finish_order":[],
                "official_splits":None,"prediction_path":str(path),
                "prediction_sha256":sha256(path),"proof_commit":proof,
                "source_evidence":{"race_list_url":info["race_list_url"],
                    "refund_url":info["refund_url"],"official_notice":notice},
                "validation":{"race_identity":True,"prediction_immutable":True,
                              "official_cancellation":True}}
            if result_path.exists():
                saved = jread(result_path)
                for key in ("race_id","date","venue","race_no","status","prediction_path",
                            "prediction_sha256","proof_commit","finish_order"):
                    if saved.get(key) != proposed[key]:
                        raise ValueError(f"BLOCKED_CONFLICT: immutable cancellation result {rid} {key}")
                if not saved.get("source_evidence",{}).get("official_notice"):
                    raise ValueError(f"BLOCKED_CONFLICT: missing official notice {rid}")
            else:
                write_distinct(result_path,proposed)
            cancellations[rid] = {
                "status":CANCEL,"official_source_url":info["race_list_url"],
                "refund_source_url":info["refund_url"],"official_notice":notice,
                "prediction_sha256":sha256(path),"proof_commit":proof,
                "result_path":str(result_path)}
        else:
            if status not in ("COMPLETED","SKIPPED_VERIFIED") and not (
                    result_path.exists() and review_path.exists()):
                raise ValueError(f"BLOCKED_UNRESOLVED: missing valid official review {rid}: {status}")
            if not (result_path.exists() and review_path.exists()):
                raise ValueError(f"BLOCKED_UNRESOLVED: result/review missing {rid}")
            result, review = jread(result_path), jread(review_path)
            if (result.get("status") != "OFFICIAL_CONFIRMED"
                or result.get("prediction_sha256") != sha256(path)
                or result.get("proof_commit") != proof
                or review.get("result_path") != str(result_path)
                or review.get("prediction_sha256") != sha256(path)):
                raise ValueError(f"BLOCKED_REVIEW_PROOF: {rid}")
            section = info["refund_sections"].get(race_no)
            if not section:
                raise ValueError(f"BLOCKED_PAYOUT: missing official refund section {rid}")
            payout = confirmed_win_payout(section, result)
            payout_checks[rid] = {
                "status":"VERIFIED_OFFICIAL_PAYOUT", "refund_source_url":info["refund_url"],
                "winner_payouts":payout,"prediction_sha256":sha256(path),
                "proof_commit":proof,"result_sha256":sha256(result_path),
                "review_sha256":sha256(review_path)}
    if len(cancellations) + len(payout_checks) != len(predictions):
        raise ValueError("BLOCKED_RECONCILIATION: unfinished races")
    expected_reviews = set(payout_checks)
    if (set(old_summary["reconciliation"]["review_ids"]) != expected_reviews
        or old_summary["reviewed_races"] != len(payout_checks)):
        raise ValueError("BLOCKED_RECONCILIATION: previous valid reviews changed")
    record = {
        "schema_version":1,"date":date,"status":"SUCCESS",
        "official_result_count":len(payout_checks),
        "official_cancellation_count":len(cancellations),
        "verified_settlement_count":len(payout_checks),
        "verified_at":old_evidence.get("verified_at",now_time) if old_evidence else now_time,
        "cancelled_races":cancellations,"verified_payouts":payout_checks,
        "reconciliation":{"expected_predictions":len(predictions),
            "verified_review_ids":sorted(expected_reviews),
            "official_cancelled_ids":sorted(cancellations),
            "unresolved_ids":[],
            "complete":set(payout_checks)|set(cancellations)==expected}}
    if old_evidence:
        # Date-scoped outcome data is stable on repeat runs; preserve the original
        # evidence timestamp and avoid gratuitous commits.
        if old_evidence.get("cancelled_races") != cancellations or old_evidence.get("verified_payouts") != payout_checks:
            raise ValueError("BLOCKED_CONFLICT: previous official closure evidence differs")
        record=old_evidence
    write_distinct(existing_evidence,record)
    corrected = dict(old_summary)
    corrected.update({"pending":0,"blocked":0,"cancelled_official":len(cancellations),
                      "settlement_verified":len(payout_checks)})
    corrected["reconciliation"] = dict(old_summary["reconciliation"])
    corrected["reconciliation"].update({
        "unresolved_ids":[],"cancelled_ids":sorted(cancellations),
        "settlement_verified_ids":sorted(payout_checks),
        "eligible_equals_categories":len(predictions) ==
            len(payout_checks)+len(cancellations)})
    write_distinct(summary_path,corrected,mutable=True)
    diag = dict(old_diag)
    diag["races"] = dict(old_diag["races"])
    for rid, cancel in cancellations.items():
        diag["races"][rid] = {
            "status":CANCEL,"reason":"NAR official race cancellation",
            "result_path":cancel["result_path"],"review_path":None,
            "official_source_url":cancel["official_source_url"]}
    diag["completed_or_verified"]=len(payout_checks)
    diag["official_cancelled"]=len(cancellations)
    diag["settlement_verified"]=len(payout_checks)
    diag["total_unresolved"]=0
    diag["retry_only_race_ids"]=[]
    diag["status"]="SUCCESS"
    write_distinct(diagnostic_path,diag,mutable=True)
    print(json.dumps({"date":date,"status":"SUCCESS","reviewed":len(payout_checks),
                      "official_cancelled":len(cancellations),"verified_payouts":len(payout_checks),
                      "unresolved":0},ensure_ascii=False))
    return 0

def self_test():
    text=("地方競馬情報サイト 10/20（火）の盛岡競馬第1競走および第2競走は、"
          "濃霧による視界不良のため取り止めとなりました。"
          "2026年10月20日 盛岡競馬場 払戻金 "
          "3R C2 着順 1 8 10 マツリダ 2 4 4 ニシノ 3 6 7 イネス "
          "単勝 10 290円 複勝 10 180円 "
          "4R C1 着順 1 6 7 モズ 単勝 7 220円 "
          "オッズパークLOTO 5重勝 8R 9R")
    assert set(cancellation_numbers(text,"2026-10-20","盛岡")) == {1,2}
    assert not cancellation_numbers(text,"2026-10-19","盛岡")
    assert not cancellation_numbers(text,"2026-10-20","浦和")
    blocks=refund_sections(text)
    assert set(blocks)=={3,4}
    assert confirmed_win_payout(blocks[3],{"finish_order":[{"horse_no":10,"finish_position":1}]}) == [
        {"horse_no":10,"amount_yen_per_100":290}]
    try:
        confirmed_win_payout(blocks[3],{"finish_order":[{"horse_no":9,"finish_position":1}]})
        raise AssertionError("Mismatch was not rejected")
    except ValueError as e:
        assert str(e).startswith("BLOCKED_PAYOUT_JOIN")
    print("PASS: cancellation, date/venue guard, refund sections, payout join self-tests")

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    try:
        if args.self_test:
            self_test()
        else:
            if not args.date:
                parser.error("--date is required")
            sys.exit(finalized(args.date))
    except Exception as exc:
        print(f"POSTRACE_FINALIZE_FAIL: {type(exc).__name__}: {exc}",file=sys.stderr)
        sys.exit(3)
