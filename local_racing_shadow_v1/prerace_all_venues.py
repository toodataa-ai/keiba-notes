#!/usr/bin/env python3
"""Full-day NAR PRE-RACE population builder (local Shadow only).

Only official NAR RaceList and DebaTable (and past results embedded therein)
are consulted. Each race started before capture is a gap, NEVER a prediction.
The workflow must commit created predictions before those races start.
No JRA file is read or written.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
import generate_daily as base

ROOT = Path("local_racing_shadow_v1")
JST = base.JST
SAFETY_MINUTES = 12

def load_json(p):
    return json.loads(p.read_text(encoding="utf-8"))

def fetch_program(key, venue, code, target):
    soup, url, seen = base.get_html("RaceList", {
        "k_babaCode": code, "k_raceDate": target.replace("-", "/")
    })
    races = []
    for a in soup.find_all("a", href=True):
        if "DebaTable" not in a.get("href", ""):
            continue
        row = a.find_parent("tr")
        if row is None:
            continue
        cells = [c.get_text(" ",strip=True) for c in row.find_all(["td","th"],recursive=False)]
        if len(cells) < 5:
            continue
        number = re.search(r"\b(\d{1,2})\s*R\b",cells[0],re.I)
        start = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b"," ".join(cells[1:4]))
        if not number or not start:
            continue
        no = int(number.group(1))
        hh,mm=map(int,start.groups())
        when=dt.datetime.combine(dt.date.fromisoformat(target),dt.time(hh,mm),JST)
        course_text=" ".join(cells)
        distance=next((int(m.group(1)) for v in cells if (m:=re.search(r"(\d{3,4})\s*m\b",v,re.I))),None)
        count=next((int(v) for v in reversed(cells) if re.fullmatch(r"\d{1,2}",v)),None)
        surface=("ばんえい" if code==3 else
                 "芝" if re.search(r"芝(?:右|左)?\s*\d{3,4}m",course_text) else "ダート")
        races.append({
            "race_no":no,"race_name":a.get_text(" ",strip=True),
            "scheduled_start_at":when,"distance":distance,
            "declared_count":count,"surface":surface,
            "program_url":url,"program_seen_at":seen,
        })
    nos=[x["race_no"] for x in races]
    if races and (len(nos)!=len(set(nos)) or sorted(nos)!=list(range(1,len(nos)+1))):
        raise ValueError(f"Incomplete/duplicate official card: {venue}, race numbers {sorted(nos)}")
    if races and venue not in soup.get_text(" ",strip=True)[:1800]:
        raise ValueError(f"Official venue mismatch: expected {venue}, source {url}")
    return sorted(races,key=lambda x:x["race_no"]),url

def run(date):
    if date!=dt.datetime.now(JST).date().isoformat():
        raise ValueError(f"Refusing late/retrospective/future predictions: request={date}, today(JST)={dt.datetime.now(JST).date()}")
    cfg=load_json(ROOT/"config.json")
    request=load_json(ROOT/"prerace_request.json")
    if cfg.get("production_effect") is not False or request.get("production_effect") is not False:
        raise ValueError("JRA isolation guard failed")
    if request.get("date")!=date or request.get("scope")!="PRE-RACE":
        raise ValueError("Explicit date/scope mismatch")
    base.DATE=date
    base.OUT=ROOT/"predictions"/date
    entries=[]; gaps=[]; existing_ids=[]; venue_counts={}; program_urls={}
    expected=request.get("expected_races_by_venue") or {}
    enabled={k:v for k,v in cfg["venues"].items() if v.get("enabled")}
    if len(enabled)!=15:
        raise ValueError(f"Expected all 15 NAR venues enabled; actual {len(enabled)}")
    if expected and (set(expected)-set(enabled)):
        raise ValueError(f"Official active venue contains unconfigured code: {sorted(set(expected)-set(enabled))}")
    for key,venue in enabled.items():
        if expected and key not in expected:
            continue  # Officially inactive today; active venues are explicitly enumerated and audited
        code=venue.get("nar_baba_code")
        if not isinstance(code,int):
            raise ValueError(f"Missing verified official baba code for {key}")
        label=venue["label"]
        try:
            programs,source=fetch_program(key,label,code,date)
        except Exception as exc:
            gaps.append({"venue":key,"race_id":None,"status":"BLOCKED_PROGRAM",
                         "reason":f"{type(exc).__name__}: {exc}"})
            continue
        venue_counts[key]=len(programs)
        program_urls[key]=source
        print(f"OFFICIAL {label}: {len(programs)} races",flush=True)
        if key in expected and int(expected[key])!=len(programs):
            gaps.append({"venue":key,"race_id":None,"status":"BLOCKED_POPULATION_MISMATCH",
                         "expected":int(expected[key]),"actual":len(programs)})
        for p in programs:
            race_id=f"{date.replace('-','')}-{key}-{p['race_no']:02d}"
            dest=base.OUT/(race_id+".json")
            if dest.exists():
                frozen=load_json(dest)
                if frozen.get("race_id")!=race_id or frozen.get("date")!=date or frozen.get("venue")!=label:
                    raise ValueError(f"Immutable identity mismatch: {dest}")
                if dt.datetime.fromisoformat(frozen["information_cutoff_at"])>=p["scheduled_start_at"]:
                    raise ValueError(f"Existing prediction lacks a pre-start cutoff: {dest}")
                existing_ids.append(race_id)
                continue
            now=dt.datetime.now(JST)
            if now+dt.timedelta(minutes=SAFETY_MINUTES)>=p["scheduled_start_at"]:
                gaps.append({"venue":key,"race_id":race_id,"status":"EXPIRED_OR_TOO_CLOSE",
                             "scheduled_start_at":p["scheduled_start_at"].isoformat(),
                             "reason":"Insufficient time for verifiable GitHub commit before race; do not create hindsight prediction"})
                continue
            try:
                obj=base.build(label,code,p)
                obj["race_id"]=race_id
                obj["surface"]=p["surface"]
                if code==3:
                    obj["pace"]="適用外（ばんえい方式）"
                    obj["method_limitations"].append("ばんえいはサラブレッド競走と異なる。直近の着順を用いる探索的基準であり、障害・重量の補正は未実装")
                    for h in obj["runners"]:
                        h["running_style_hypothesis"]="対象外（ばんえい）"
                entries.append((dest,obj))
            except Exception as exc:
                gaps.append({"venue":key,"race_id":race_id,"status":"BLOCKED_CAPTURE",
                             "reason":f"{type(exc).__name__}: {exc}"})
    if not venue_counts or sum(venue_counts.values())==0:
        raise ValueError("No official programs parsed: BLOCKED_CALENDAR, not a successful skip")
    if sum(venue_counts.values())==0 or any(x["status"]=="BLOCKED_PROGRAM" for x in gaps):
        # Preserve completed captures from independently verifiable venues.
        print("WARNING: some venue programs were unavailable",flush=True)
    created=[]
    for dest,obj in entries:
        if dt.datetime.now(JST)+dt.timedelta(minutes=SAFETY_MINUTES)>=dt.datetime.fromisoformat(obj["scheduled_start_at"]):
            gaps.append({"venue":obj["venue"],"race_id":obj["race_id"],
                         "status":"EXPIRED_DURING_CAPTURE",
                         "reason":"Not enough time remains before verified GitHub commit"})
            continue
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            raise ValueError("Immutable race file exists: "+str(dest))
        dest.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        created.append(obj["race_id"])
    # Non-empty official program with uncollected races is partial, never a skip.
    # Existing immutable snapshots remain part of the daily captured population.
    saved_ids=sorted(set(created+existing_ids))
    if len(saved_ids)!=len(created)+len(existing_ids):
        raise ValueError("Duplicate saved race ids")
    diag={
        "schema_version":1,"date":date,"scope":"PRE-RACE_ALL_OFFICIAL_VENUES",
        "status":"COMPLETE" if not gaps else "PARTIAL_WITH_COVERAGE_GAPS",
        "generated_at":dt.datetime.now(JST).isoformat(timespec="seconds"),
        "official_total_races":sum(venue_counts.values()),
        "official_races_by_venue":venue_counts,
        "official_source_urls":program_urls,
        "created_race_ids":saved_ids,"created_count":len(saved_ids),
        "newly_created_race_ids":created,"newly_created_count":len(created),
        "already_frozen_race_ids":existing_ids,"already_frozen_count":len(existing_ids),
        "coverage_gaps":gaps,"gap_count":len(gaps),
        "minimum_precommit_lead_minutes":SAFETY_MINUTES,
        "prediction_commit_sha":"Must be resolved independently from Git history AFTER push; this diagnostic file is not temporal proof.",
        "production_effect":False,
        "jra_related_files_changed":False,
        "note":"Races already started are recorded as gaps, never guessed. GitHub commit must precede every captured race, independently verified by publish_audit.py.",
    }
    audit=ROOT/"diagnostics"/f"{date}-all-venues-prerace-run.json"
    audit.parent.mkdir(parents=True,exist_ok=True)
    audit.write_text(json.dumps(diag,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"PRE-RACE {date}: scheduled={diag['official_total_races']} archived={len(saved_ids)} new={len(created)} gaps={len(gaps)}",flush=True)
    if len(saved_ids)==0 and not gaps:
        raise ValueError("Nonempty official racing population but no coverage data captured")

def check_commit_window(date):
    folder=ROOT/"predictions"/date
    import subprocess
    untracked=subprocess.check_output(["git","ls-files","--others","--exclude-standard",str(folder)],text=True).splitlines()
    if not untracked:
        print("No newly created snapshots; immutable originals untouched",flush=True)
        return
    now=dt.datetime.now(JST)
    unsafe=[]
    for item in untracked:
        p=load_json(Path(item))
        if now+dt.timedelta(minutes=3)>=dt.datetime.fromisoformat(p["scheduled_start_at"]):
            unsafe.append(item)
    if unsafe:
        raise ValueError(f"PRE-COMMIT CUTOFF BLOCKER: {unsafe} (never commit late snapshots)")
    print(f"Pre-commit cutoffs validated for {len(untracked)} newly created files",flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",required=True)
    parser.add_argument("--verify-commit-window",action="store_true")
    args=parser.parse_args()
    try:
        (check_commit_window if args.verify_commit_window else run)(args.date)
    except Exception as exc:
        print(f"BLOCKER: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        sys.exit(1)
