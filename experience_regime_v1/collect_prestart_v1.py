#!/usr/bin/env python3
"""E0/E1/E2 independent JRA prestart OBSERVATION collector.
No odds, race results, STEP1 rating, formal E2E or regional race writes.
Official racecard career record W-S-T-O is NOT the last-four past performances.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from experience_regime_v1.model import classify_regime
from experience_regime_v1.prestart_collection_audit_v1 import audit

ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")
MODEL = "e012-shadow-v0.1"
# Empirically verified on JRA 2026-10-17 racecard URLs: suffix digit checksum.
# Seeds are real published JRA PC racecards; on mismatch no fallback to guessed data.
SEEDS = {
    "2026-10-17": {"東京": (1, 0xD0), "京都": (4, 0xCD), "新潟": (12, 0x4E)},
    # Independently checked against official 2026-10-18 JRA racecards:
    # Tokyo 4R /1F, Kyoto 11R /30, Niigata 8R /6A.
    "2026-10-18": {"東京": (4, 0x1F), "京都": (11, 0x30), "新潟": (8, 0x6A)},
    # Verified directly against six 2026-10-24 and 2026-10-25 JRA official racecards.
    "2026-10-24": {"東京": (1, 0xD9), "京都": (1, 0xB7), "新潟": (1, 0x50)},
    "2026-10-25": {"東京": (1, 0x09), "京都": (1, 0xE7), "新潟": (1, 0x80)},
    # Verified against JRA PC 2026-10-31 1R official cards (Tokyo /74, Kyoto /DF).
    "2026-10-31": {"東京": (1, 0x74), "京都": (1, 0xDF)},
    # Verified against JRA PC 2026-11-01 1R official cards (Tokyo /54, Kyoto /32).
    "2026-11-01": {"東京": (1, 0x54), "京都": (1, 0x32)},
}
MEETING_DAY = {
    "2026-10-17": {"東京": "06", "京都": "06", "新潟": "01"},
    "2026-10-18": {"東京": "07", "京都": "07", "新潟": "02"},
    "2026-10-24": {"東京": "08", "京都": "08", "新潟": "03"},
    "2026-10-25": {"東京": "09", "京都": "09", "新潟": "04"},
    "2026-10-31": {"東京": "10", "京都": "10"},
    "2026-11-01": {"東京": "11", "京都": "11"},
}
VENUES = {"東京":("05","04","06"),"京都":("08","04","06"),"新潟":("04","04","01")}

def jst_now():
    return datetime.now(JST)

def official_card_url(item):
    day=item["date"];venue=item["venue"];num=item["race_no"]
    if day not in SEEDS or venue not in SEEDS[day]:
        raise ValueError("official card URL has no verified seed")
    known,base=SEEDS[day][venue]
    # JRA URL two decimal race digits; ones coefficient -75, tens +82 (mod 256).
    v=(base-75*((num%10)-(known%10))+82*((num//10)-(known//10)))%256
    cc,meet,_legacy_meeting_day=VENUES[venue]
    meeting_day=MEETING_DAY[day][venue]
    code=f"pw01dde01{cc}{day[:4]}{meet}{meeting_day}{num:02d}{day.replace('-','')}/{v:02X}"
    return "https://www.jra.go.jp/JRADB/accessD.html?CNAME="+quote(code,safe="")

def save_new(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        return False
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return True

def fetch_race_card(session,item):
    url=official_card_url(item)
    r=session.get(url,timeout=24,headers={"User-Agent":"Mozilla/5.0 (compatible; experience-regime-shadow-research/0.1)"})
    r.raise_for_status()
    raw=r.content
    soup=BeautifulSoup(raw,"html.parser")
    visible=soup.get_text(" ",strip=True)
    identity=f"{item['date'][-2:]}日"
    match_venue=(item["venue"] in visible)
    match_race=re.search(rf"(?:^|\s){item['race_no']}\s*レース",visible) is not None
    if not (match_venue and match_race and (identity in visible)):
        raise ValueError(f"official card identity mismatch: venue={match_venue}, race={match_race}, date={identity in visible}")
    seen=set();horses={}
    captured_at=jst_now().isoformat()
    for tr in soup.select("tr"):
        no_cell=tr.select_one("td.num")
        horse_cell=tr.select_one("td.horse")
        if no_cell is None or horse_cell is None:continue
        m=re.search(r"\d+",no_cell.get_text(" ",strip=True))
        if not m:continue
        num=int(m.group(0))
        if num in seen:raise ValueError(f"duplicate runner number {num}")
        seen.add(num)
        horse_label=horse_cell.get_text(" ",strip=True)
        name_node=horse_cell.select_one("a")
        name=name_node.get_text(" ",strip=True) if name_node else None
        if not name: name=horse_label.split()[0] if horse_label else None
        # Exact four-part W-S-T-other JRA career *summary*, not last four starts.
        groups=re.findall(r"\(\s*(\d+)\s*\.\s*(\d+)\s*\.\s*(\d+)\s*\.\s*(\d+)\s*\)",horse_label)
        if len(groups)==1:
            record=[int(v) for v in groups[0]]
            starts=sum(record)
            horse={"horse_number":num,"horse_name":name,"starts_before_race":starts,
                   "regime":classify_regime(starts),"career_summary_wsto":record,
                   "source_url":url,"observed_at":captured_at,
                   "source_field":"JRA official racecard 戦績 (W.S.T.other)"}
        else:
            horse={"horse_number":num,"horse_name":name,"starts_before_race":None,
                   "regime":None,"source_url":url,"observed_at":captured_at,
                   "missing_reason":"missing_or_ambiguous_official_lifetime_summary"}
        horses[str(num)]=horse
    if len(horses)<2:
        raise ValueError("official JRA runner list not parsed; no surrogate list accepted")
    return url,hashlib.sha256(raw).hexdigest(),horses,captured_at

def collect(week_id,date):
    week_dir=ROOT/"experience_regime_v1"/"collection"/week_id
    pool=json.loads((week_dir/"race_pool.json").read_text())
    plan=json.loads((week_dir/"sample_plan.json").read_text())
    if pool["week_id"]!=week_id or plan["week_id"]!=week_id or pool["race_count"]!=len(pool["races"]):
        raise ValueError("population/plan mismatch")
    selected={r["race_id"]:r for r in plan["selected_races"]}
    all_today=[r for r in pool["races"] if r["date"]==date]
    gaps=[];stats=Counter();by_cat={}
    # The fixed plan can never change at this stage, even if source retrieval fails.
    for item in sorted(all_today,key=lambda x:(x["start_at"],x["venue"],x["race_no"])):
        if item["race_id"] not in selected:
            gaps.append({"race_id":item["race_id"],"race_no":item["race_no"],"venue":item["venue"],
                         "reason":"not_selected_by_fixed_weekly_plan"})
    session=requests.Session()
    for item in [r for r in all_today if r["race_id"] in selected]:
        rid=item["race_id"]
        target=week_dir/"snapshots"/(rid+".json")
        audit_path=week_dir/"audits"/(rid+".json")
        start=datetime.fromisoformat(item["start_at"])
        if target.exists():
            stats["immutable_snapshot_reused"]+=1
            continue
        if jst_now()>=start:
            gaps.append({"race_id":rid,"start_at":item["start_at"],"reason":"already_started_no_new_prediction"})
            stats["started_selected"]+=1
            continue
        try:
            url,digest,horses,captured_at=fetch_race_card(session,item)
            ctx={"date":date,"venue":item["venue"],"race_no":item["race_no"],
                 "race_name":item["race_name"],"race_category":item["race_category"],
                 "sample_origin":selected[rid]["sample_origin"],"start_at":item["start_at"],
                 "official_source_url":url}
            snapshot={"schema_version":1,"race_id":rid,"model_version":MODEL,
                      "capture_type":"prerace_experience_observation_only",
                      "production_effect":False,"step1_prediction_status":"unavailable_not_synthesized",
                      "step1":{"runners":[{"horse_number":x["horse_number"]} for x in horses.values()]},
                      "race_context":ctx,"experience":{"model_version":MODEL,
                      "horses":horses},"source_html_sha256":digest,"captured_at":captured_at}
            report=audit(snapshot,json.dumps(snapshot,ensure_ascii=False).encode(),jst_now())
            report["source_url"]=url
            report["source_html_sha256"]=digest
            save_new(target,snapshot)
            save_new(audit_path,report)
            stats["new_snapshots"]+=1
            for h in horses.values():
                key=h.get("regime")
                if key in ("E0","E1","E2"):
                    stats["verified_"+key+"_horses"]+=1
                    by_cat.setdefault(item["race_category"],Counter())[key]+=1
                else:stats["missing_lifetime_starts"]+=1
            if not report["usable_for_e012_shadow"]:
                gaps.append({"race_id":rid,"start_at":item["start_at"],"reason":"incomplete_lifetime_starts_or_evidence",
                             "missing_fields":report["missing_prerace_evidence"]})
            print("E012_REAL_JRA_PRESTART",rid,"runners",len(horses),
                  "usable",report["usable_for_e012_shadow"],"source",url,flush=True)
        except Exception as exc:
            stats["selected_race_collection_errors"]+=1
            gaps.append({"race_id":rid,"start_at":item["start_at"],"reason":"source_capture_failed",
                         "detail":str(exc)[:300]})
            print("E012_COVERAGE_GAP",rid,str(exc)[:300],flush=True)
    summary={"schema_version":1,"week_id":week_id,"date":date,"generated_at":jst_now().isoformat(),
             "population_today_count":len(all_today),"fixed_plan_total_races":len(selected),
             "fixed_plan_today_races":len([x for x in all_today if x["race_id"] in selected]),
             "stats":dict(stats),"category_regime_verified_horses":{k:dict(v) for k,v in by_cat.items()},
             "coverage_gaps":gaps,"production_effect":False}
    save_new(week_dir/("coverage_gap_"+date+".json"),summary)
    print("E012_COLLECTION_SUMMARY",json.dumps(summary,ensure_ascii=False),flush=True)

def precommit_gate(week_id,date):
    week_dir=ROOT/"experience_regime_v1"/"collection"/week_id
    targets=list((week_dir/"snapshots").glob(date+"-*.json")) if (week_dir/"snapshots").exists() else []
    rejected=[]
    for p in targets:
        record=json.loads(p.read_text())
        start=datetime.fromisoformat(record["race_context"]["start_at"])
        if jst_now()>=start:
            # Reuse existing Git-tracked historical snapshots without mutation.
            # First-introduction provenance is independently checked via git log.
            import subprocess
            tracked=subprocess.run(["git","ls-files","--error-unmatch",str(p.relative_to(ROOT))],
                 cwd=ROOT,capture_output=True).returncode==0
            if tracked:
                continue
            rejected.append(record["race_id"])
            # ONLY a newly generated, not-yet-committed snapshot can be pruned.
            p.unlink()
            a=week_dir/"audits"/p.name
            if a.exists():a.unlink()
    if rejected:
        path=week_dir/("precommit_blockers_"+date+".json")
        save_new(path,{"at":jst_now().isoformat(),"race_ids":rejected,
                       "reason":"cannot_commit_first_snapshot_after_race_start"})
    print("E012_PRECOMMIT_GATE",len(targets),"pruned",len(rejected),flush=True)

def proof_audit(week_id,date,proof_sha,commit_at):
    week_dir=ROOT/"experience_regime_v1"/"collection"/week_id
    committed=datetime.fromisoformat(commit_at.replace("Z","+00:00"))
    snapshots=list((week_dir/"snapshots").glob(date+"-*.json")) if (week_dir/"snapshots").exists() else []
    details=[];totals=Counter()
    for path in sorted(snapshots):
        p=json.loads(path.read_text())
        start=datetime.fromisoformat(p["race_context"]["start_at"])
        captured=datetime.fromisoformat(p["captured_at"])
        ok=captured<start and committed<start
        regimes=Counter(v.get("regime") for v in p["experience"]["horses"].values() if v.get("regime") in ("E0","E1","E2"))
        if ok:
            for key,n in regimes.items():
                totals[key+"_horses"]+=n
                totals[key+"_races"]+=1
        else:totals["invalid_timing_races"]+=1
        details.append({"race_id":p["race_id"],"proof_commit":proof_sha,"proof_commit_at":commit_at,
                        "captured_at":p["captured_at"],"start_at":p["race_context"]["start_at"],
                        "proof_prestart_valid":ok,"regime_counts":dict(regimes)})
    report={"schema_version":1,"week_id":week_id,"date":date,"generated_at":jst_now().isoformat(),
            "proof_commit":proof_sha,"proof_commit_at":commit_at,"totals":dict(totals),
            "races":details,"production_effect":False}
    path=week_dir/("proof_commit_"+date+".json")
    save_new(path,report)
    print("E012_GIT_PROOF",json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("command",choices=("collect","precommit_gate","proof_audit"))
    ap.add_argument("--week-id",required=True)
    ap.add_argument("--date",required=True)
    ap.add_argument("--proof-sha")
    ap.add_argument("--commit-at")
    ns=ap.parse_args()
    if ns.command=="collect": collect(ns.week_id,ns.date)
    elif ns.command=="precommit_gate":precommit_gate(ns.week_id,ns.date)
    else:
        if not ns.proof_sha or not ns.commit_at:ap.error("proof sha and time required")
        proof_audit(ns.week_id,ns.date,ns.proof_sha,ns.commit_at)
