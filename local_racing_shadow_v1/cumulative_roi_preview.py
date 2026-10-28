#!/usr/bin/env python3
"""Audited NAR Shadow theoretical win/place ROI publisher.

Reads immutable predictions, results, reviews and official settlement closure.
Writes ONLY independent staging and production ROI aggregate JSON files.
Never changes a prediction, result, review, JRA file or model output.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys

from postrace import CODES, ROOT, http_html, jread
from postrace_finalize import page_identity, refund_sections, confirmed_win_payout

MANIFEST=Path("docs/data/local_racing_shadow_public.json")
OUTPUT=Path("docs/staging/data/local-shadow-roi-preview.json")
PRODUCTION_OUTPUT=Path("docs/data/local_shadow_roi.json")
BET=100
JST=timezone(timedelta(hours=9))

def check(condition,message):
    if not condition: raise ValueError("BLOCKED_ROI_AUDIT: "+message)

def place_payouts(section):
    """Parse only the official 複勝 payout block. Not top-three assumed pays."""
    if "複勝" not in section: raise ValueError("BLOCKED_PLACE_MISSING")
    value=section.split("複勝",1)[1]
    value=re.split(r"枠連複|枠連単|馬連複|馬連単|ワイド|三連複|三連単|馬複|馬単|枠複|枠単",value,maxsplit=1)[0]
    matches=re.findall(r"(?<!\d)(\d{1,2})\s+([\d,]+)\s*円",value)
    out={}
    for horse,money in matches:
        h,m=int(horse),int(money.replace(",",""))
        check(h not in out and 1<=h<=18 and m>0,"Duplicate/invalid place payout")
        out[h]=m
    check(1<=len(out)<=5,"Unexpected place payout cardinality")
    return out

def daily_bucket():
    return {"reviewed":0,"evaluable":0,"win_checked":0,"win_return_yen":0,
            "place_checked":0,"place_return_yen":0}

def add(bucket,record):
    for k in bucket: bucket[k]+=record[k]

def pct(stake_n,ret):
    return round(ret/(stake_n*BET)*100,2) if stake_n else None

def main():
    manifest=jread(MANIFEST)
    days=sorted(manifest.get("daily_analysis",[]),key=lambda x:x["date"])
    check(days and len({x["date"] for x in days})==len(days),"Missing/duplicate daily analysis")
    manifest_by_id={r["race_id"]:r for r in manifest["races"]}
    check(len(manifest_by_id)==len(manifest["races"]),"Duplicate manifest races")
    targets=[r for r in manifest["races"] if r["status"]=="reviewed"]
    check(sum(x["summary"]["reviewed"] for x in days)==len(targets),"Day/manifest reviewed mismatch")
    official={}
    errors={}
    group_keys=sorted({(r["date"],r["venue"]) for r in targets})
    for date,label in group_keys:
        key=date+" / "+label
        if label not in CODES:
            errors[key]="Unknown enabled NAR venue"; continue
        try:
            soup,url=http_html("RefundMoneyList",{"k_babaCode":CODES[label],
                                                    "k_raceDate":date.replace("-","/")})
            page_identity(soup,date,"帯広" if label=="帯広ば" else label)
            sections=refund_sections(soup.get_text(" ",strip=True))
            check(sections,"No payable official refund sections "+key)
            official[(date,label)]=(url,sections)
        except Exception as e:
            errors[key]=str(e)[:220]
    all_totals=daily_bucket()
    daily={}
    venues={}
    race_rows={}
    unknown=[]
    unknown_win=[]
    for r in sorted(targets,key=lambda x:x["race_id"]):
        rid,date,label=r["race_id"],r["date"],r["venue"]
        root=ROOT/"reviews"/date/(rid+".json")
        respath=ROOT/"results"/date/(rid+".json")
        predpath=ROOT/"predictions"/date/(rid+".json")
        closurepath=ROOT/"diagnostics"/(date+"-postrace-closure.json")
        check(root.is_file() and respath.is_file() and predpath.is_file(),
              "Missing immutable race evidence "+rid)
        review,result,pred=map(jread,(root,respath,predpath))
        closure=jread(closurepath) if closurepath.is_file() else None
        settlement=closure["verified_payouts"].get(rid) if closure else None
        checksum=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        if closure:
            check(closure["status"]=="SUCCESS" and closure["reconciliation"]["complete"],
                  "Existing official closure incomplete "+date)
            check(settlement and settlement["status"]=="VERIFIED_OFFICIAL_PAYOUT",
                  "Missing closure win payout "+rid)
            check(settlement["prediction_sha256"]==checksum(predpath) and
                  settlement["review_sha256"]==checksum(root) and
                  settlement["result_sha256"]==checksum(respath),
                  "Immutable closure evidence hash mismatch "+rid)
            check(settlement["proof_commit"]==r["proof_commit"],"Closure proof mismatch "+rid)
        check(review["proof_commit"]==result["proof_commit"]==r["proof_commit"],
              "Proof mismatch "+rid)
        check(result["prediction_sha256"]==checksum(predpath) and
              review["prediction_sha256"]==checksum(predpath),
              "Prediction digest mismatch "+rid)
        check(review["race_id"]==result["race_id"]==pred["race_id"]==rid,
              "Race identity mismatch "+rid)
        check(result["status"]=="OFFICIAL_CONFIRMED","Result not official "+rid)
        m=review.get("hit_metrics",{})
        bucket=daily.setdefault(date,daily_bucket())
        vbucket=venues.setdefault(label,daily_bucket())
        row={"date":date,"venue":label,"status":"NOT_EVALUABLE"}
        for b in (bucket,vbucket,all_totals):b["reviewed"]+=1
        if m.get("evaluable") is not True:
            race_rows[rid]=row;continue
        top=review.get("top_pick")
        check(isinstance(top,dict) and isinstance(top.get("horse_no"),int),"Missing frozen top pick "+rid)
        horse=int(top["horse_no"])
        actual=[p for p in result["finish_order"] if p["horse_no"]==horse]
        check(len(actual)==1 and actual[0]["finish_position"]==review["actual_top_pick_finish"],
              "Top pick official result mismatch "+rid)
        winners=[int(x["horse_no"]) for x in result["finish_order"] if x["finish_position"]==1]
        group=official.get((date,label))
        block=group[1].get(int(r["race_no"])) if group else None
        row.update({"status":"EVALUABLE","horse_no":horse,
                    "finish_position":actual[0]["finish_position"],
                    "win_return_yen":None,"place_return_yen":None})
        for b in (bucket,vbucket,all_totals):b["evaluable"]+=1

        # Saved historical win settlements are authoritative when present.
        # Earlier days have no closure artifact; official NAR payout can fill
        # that gap, without editing the old reviews or inventing a payout.
        try:
            if settlement:
                win_map={int(x["horse_no"]):int(x["amount_yen_per_100"]) for x in settlement["winner_payouts"]}
                check(set(winners)==set(win_map),"Winner mismatch with frozen closure "+rid)
                if block:
                    latest={x["horse_no"]:x["amount_yen_per_100"] for x in confirmed_win_payout(block,result)}
                    check(latest==win_map,"Saved win payout disagrees with current NAR "+rid)
            else:
                if not block: raise ValueError("No official win payout source for historical race")
                win_map={x["horse_no"]:x["amount_yen_per_100"] for x in confirmed_win_payout(block,result)}
            win_amount=win_map.get(horse,0)
            if win_amount: check(review["actual_top_pick_finish"]==1,"Winner payout contradicts rank "+rid)
            row["win_return_yen"]=win_amount
            for b in (bucket,vbucket,all_totals):
                b["win_checked"]+=1;b["win_return_yen"]+=win_amount
        except Exception as e:
            unknown_win.append({"race_id":rid,"reason":str(e)[:200]})

        try:
            if not group or not block:
                raise ValueError(errors.get(date+" / "+label,"Official place refund section unavailable"))
            source,_=group
            place_map=place_payouts(block)
            top3={int(x["horse_no"]) for x in result["finish_order"]
                  if x["finish_position"] is not None and 1<=x["finish_position"]<=3}
            check(set(place_map).issubset(top3),"Place payout not subset of verified top 3 "+rid)
            # In small fields, only two places may be payable.
            check(set(winners).issubset(set(place_map)),"Winner absent from payable place pool "+rid)
            amount=place_map.get(horse,0)
            row.update({"place_return_yen":amount,"refund_source_url":source})
            for b in (bucket,vbucket,all_totals):
                b["place_checked"]+=1;b["place_return_yen"]+=amount
        except Exception as e:
            unknown.append({"race_id":rid,"reason":str(e)[:200]})
        race_rows[rid]=row
    check(sum(s["reviewed"] for s in daily.values())==len(targets),"Day reviewed mismatch")
    check(all_totals["evaluable"]==sum(x["summary"]["evaluable"] for x in days),
          "Unexpected eligible sample denominator")
    check(all_totals["win_checked"]<=all_totals["evaluable"],"Invalid verified win denominator")
    def format_stats(d):
        return {**d,"win_roi_pct":pct(d["win_checked"],d["win_return_yen"]),
                "place_roi_pct":pct(d["place_checked"],d["place_return_yen"])}
    report={
      "schema_version":1,"scope":"staging_only_theoretical_100yen_each_top_pick",
      "production_effect":False,"settlement_source":"NAR official RefundMoneyList",
      "source_manifest_updated_at":manifest.get("updated_at"),
      "source_manifest_total_races":len(manifest["races"]),
      "source_manifest_reviewed":len(targets),
      "starting_date":days[0]["date"],"ending_date":days[-1]["date"],
      "assumed_stake_yen_per_eligible_race_per_bet_type":BET,
      "summary":format_stats(all_totals),
      "daily":{date:format_stats(stats) for date,stats in sorted(daily.items())},
      "by_venue":{venue:format_stats(stats) for venue,stats in sorted(venues.items())},
      "official_source_errors":errors,"place_unverified_races":unknown,
      "win_unverified_races":unknown_win,"win_complete":all_totals["win_checked"]==all_totals["evaluable"],
      "place_complete":all_totals["place_checked"]==all_totals["evaluable"],
      "exclusions":"Non-evaluable races, non-runners, official cancellations and unreviewed forecasts excluded. No loss assumed for missing official refund data.",
      "status":"VERIFIED" if not unknown and not unknown_win else "PARTIAL_OFFICIAL_PAYOUT",
    }
    production={**report, "scope":"theoretical_100yen_each_top_pick"}
    for path, payload in ((OUTPUT,report),(PRODUCTION_OUTPUT,production)):
        path.parent.mkdir(parents=True,exist_ok=True)
        content=json.dumps(payload,ensure_ascii=False,indent=2)+"\n"
        if not path.exists() or path.read_text(encoding="utf-8")!=content:
            path.write_text(content,encoding="utf-8")
    print(json.dumps({"status":report["status"],"win_roi_pct":report["summary"]["win_roi_pct"],
                      "place_roi_pct":report["summary"]["place_roi_pct"],
                      "win_checked":all_totals["win_checked"],
                      "place_checked":all_totals["place_checked"],
                      "eligible":all_totals["evaluable"],
                      "unknown_place":len(unknown),"unknown_win":len(unknown_win),
                      "staging_output":str(OUTPUT),"production_output":str(PRODUCTION_OUTPUT)},ensure_ascii=False))
    return 0

def selftest():
    s="1R 競走成績 単勝 7 270 円 2 人気 複勝 7 130 円 3 人気 5 100 円 1 人気 2 120 円 2 人気 枠連複 5-7 220 円"
    v=place_payouts(s)
    check(v=={7:130,5:100,2:120},"Sample place mapping failed")
    check(pct(2,270)==135.0,"100 yen recovery ratio failed")
    s2="複勝 3 100 円 1 人気 10 150 円 2 人気 馬連複 3-10 210 円"
    check(place_payouts(s2)=={3:100,10:150},"Two place payout mapping failed")
    print("PASS: independent win/place ROI parsing and refund denominator")

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--self-test",action="store_true");args=a.parse_args()
    try:sys.exit(selftest() if args.self_test else main())
    except Exception as e:
        print("BLOCKED_ROI: "+str(e),file=sys.stderr);sys.exit(3)
