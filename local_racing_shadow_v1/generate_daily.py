#!/usr/bin/env python3
"""Capture immutable NAR-official pre-race Shadow observations; no result/odds inputs.

This is a transparent rule-based compact STEP1 baseline (not a trained model).
Only live official race cards and historical runs embedded in those cards are used.
One atomic Git commit, produced by the invoking workflow before any race starts,
provides temporal proof for all snapshots.
"""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

JST = dt.timezone(dt.timedelta(hours=9))
BASE = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/"
ROOT = Path("local_racing_shadow_v1")
VENUES = {"oi": ("大井", 20), "sonoda": ("園田", 27)}
DATE = dt.datetime.now(JST).date().isoformat()
OUT = ROOT / "predictions" / DATE
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; LocalShadowResearch/0.1; source=NAR)", "Accept-Language":"ja-JP,ja;q=0.9"})

def get_html(endpoint, params):
    url = BASE + endpoint + "?" + urlencode(params)
    for attempt in range(3):
        try:
            response = SESSION.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            if "地方競馬情報サイト" not in response.text:
                raise ValueError("Unexpected content; not verified NAR race data")
            return BeautifulSoup(response.text, "html.parser"), url, dt.datetime.now(JST)
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 * (attempt+1))

def extract_program(code):
    soup, url, seen = get_html("RaceList", {"k_babaCode":code, "k_raceDate":DATE.replace("-", "/")})
    races = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "DebaTable" not in href:
            continue
        tr = a.find_parent("tr")
        if not tr:
            continue
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"], recursive=False)]
        if len(cells) < 5:
            continue
        found_no = re.search(r"\b(\d{1,2})\s*R\b", cells[0], flags=re.I)
        found_time = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", " ".join(cells[1:4]))
        if not found_no or not found_time:
            continue
        no = int(found_no.group(1))
        hh, mm = map(int, found_time.groups())
        distance = next((int(m.group(1)) for cell in cells if (m := re.search(r"(\d{3,4})\s*m\b", cell, re.I))), None)
        declared = next((int(c) for c in reversed(cells) if re.fullmatch(r"\d{1,2}", c)), None)
        start = dt.datetime.combine(dt.date.fromisoformat(DATE), dt.time(hh, mm), JST)
        races.append({"race_no":no,"race_name":a.get_text(" ",strip=True),"scheduled_start_at":start,"distance":distance,
                      "declared_count":declared,"program_url":url,"program_seen_at":seen})
    by_no = {r["race_no"]:r for r in races}
    if by_no and (len(by_no) != len(races) or sorted(by_no) != list(range(1,len(by_no)+1))):
        raise ValueError(f"Inconsistent official race program: {code}, race numbers {sorted(by_no)}")
    return [by_no[i] for i in sorted(by_no)]

def horse_anchor(tag):
    return tag and tag.name == "a" and "HorseMarkInfo" in (tag.get("href") or "")

def fetch_runners(code, race_no):
    soup,url,seen = get_html("DebaTable", {"k_babaCode":code, "k_raceDate":DATE.replace("-", "/"), "k_raceNo":race_no})
    result=[]
    anchors=soup.find_all(horse_anchor)
    for a in anchors:
        row=a.find_parent("tr")
        cell=a.find_parent(["td","th"])
        if row is None or cell is None:
            continue
        predecessors=[]
        for c in row.find_all(["td","th"],recursive=False):
            if c is cell or c.find(lambda t:t is a):
                break
            s=c.get_text(" ",strip=True)
            if re.fullmatch(r"\d{1,2}",s):
                predecessors.append(int(s))
        if not predecessors:
            raise ValueError(f"Official horse number missing: {url} {a.get_text(' ',strip=True)}")
        horse_no=predecessors[-1]
        gate=predecessors[-2] if len(predecessors)>1 else None
        blocks=[]
        nxt=row
        for i in range(6):
            if nxt is None or (i and nxt.find(horse_anchor)):
                break
            blocks.append(nxt.get_text(" ",strip=True))
            nxt=nxt.find_next_sibling("tr")
        alltext=" ".join(blocks)
        name=a.get_text(" ",strip=True)
        riders=row.find_all("a", href=re.compile("RiderMark",re.I))
        jockey=riders[0].get_text(" ",strip=True) if riders else None
        weights=re.search(r"(?:▲|△|☆)?\s*(\d{2}\.\d)\s+\d+-\d+-\d+-\d+",alltext)
        weight=float(weights.group(1)) if weights else None
        forms=[]
        for m in re.finditer(r"(?<![0-9])(\d{1,2})\s+([0-9]{2})\.([0-9]{2})\.([0-9]{2})(?!\d)",alltext):
            try:
                date=dt.date(2000+int(m.group(2)),int(m.group(3)),int(m.group(4)))
            except ValueError:
                continue
            if date >= dt.date.fromisoformat(DATE):
                raise ValueError(f"Potential result leakage from future/current race data: {name} {date}")
            if all(f["date"] != date.isoformat() for f in forms):
                forms.append({"date":date.isoformat(),"finish_position":int(m.group(1))})
            if len(forms)>=5:
                break
        # Official history: corner order is captured only as evidence, never inferred if missing.
        corner_sequences=re.findall(r"\b\d+:\d{2}\.\d\s+(\d{1,2}(?:-\d{1,2}){1,3})\s+\d{2}\.\d",alltext)
        prior_first_positions=[int(s.split("-")[0]) for s in corner_sequences[:3]]
        running_style=("先行" if prior_first_positions and sum(n<=3 for n in prior_first_positions)>=2
                       else "差し・追込" if prior_first_positions and sum(n>=7 for n in prior_first_positions)>=2
                       else "中団" if prior_first_positions else "不明")
        # Only published historical finishes and distance/venue records contribute.
        distance_record=re.search(r"距\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)",alltext)
        score=0.0
        weights_by_recency=[5.,3.,2.,1.5,1.]
        for f,w in zip(forms,weights_by_recency):
            score+=w*max(-4.,(7.-f["finish_position"])/6.)
        if distance_record:
            wins,seconds,thirds,losses=map(int,distance_record.groups())
            score+= 1.6*wins/max(1,wins+seconds+thirds+losses) + .6*(seconds+thirds)/max(1,wins+seconds+thirds+losses)
        non_runner=any(x in alltext for x in ("出走取消","競走除外","出走取止"))
        result.append({"horse_no":horse_no,"horse_name":name,"gate":gate,"jockey":jockey,"weight_carried":weight,
                       "recent_races":forms,"recent_corner_positions":corner_sequences[:3],
                       "running_style_hypothesis":running_style,"distance_record":list(map(int,distance_record.groups())) if distance_record else None,
                       "evidence_density":len(forms),"reliability":"高" if len(forms)>=4 else ("中" if len(forms)>=2 else "低"),
                       "evidence_score":round(score,4),"non_runner":non_runner})
    numbers=[r["horse_no"] for r in result]
    if len(numbers)!=len(set(numbers)):
        raise ValueError(f"Duplicate horse numbers: {url}")
    if len(result)<5 or len(result)>18:
        raise ValueError(f"Invalid horse count {len(result)}: {url}")
    if not any(r["recent_races"] for r in result):
        raise ValueError(f"No verified historical pre-race evidence: {url}")
    return result,url,seen

def build(venue,code,program):
    runners,url,seen=fetch_runners(code,program["race_no"])
    if program["declared_count"] is not None and abs(len(runners)-program["declared_count"])>1:
        raise ValueError(f"Official runner count mismatch: {url}: expected={program['declared_count']}, extracted={len(runners)}")
    active=[r for r in runners if not r["non_runner"]]
    if not active:
        raise ValueError(f"No active runners: {url}")
    ranked=sorted(active,key=lambda r:(-r["evidence_score"],-r["evidence_density"],r["horse_no"]))
    # Weight is retained as evidence; no popularity/odds or post-race performance is used.
    for rank,r in enumerate(ranked,1):
        r["ability_rank"]=rank
    for r in runners:
        if r["non_runner"]:
            r["ability_rank"]=None
    front=sum(r["running_style_hypothesis"]=="先行" for r in active)
    pace="H（速い）" if front>=5 else "M（平均）" if front>=3 else "S（遅い）" if front<=1 else "M（仮説）"
    top=ranked[0]
    now=dt.datetime.now(JST)
    if now >= program["scheduled_start_at"] - dt.timedelta(minutes=2):
        raise ValueError(f"Pre-race cutoff cannot be proven: {venue} {program['race_no']}R")
    ident=f"{DATE.replace('-','')}-{('oi' if code==20 else 'sonoda')}-{program['race_no']:02d}"
    return {"race_id":ident,"date":DATE,"venue":venue,"race_no":program["race_no"],
            "race_name":program["race_name"],"surface":"ダート","distance":program["distance"],
            "class":program["race_name"],"age_condition":"公式競走名参照",
            "scheduled_start_at":program["scheduled_start_at"].isoformat(timespec="seconds"),
            "generated_at":now.isoformat(timespec="seconds"),
            "information_cutoff_at":now.isoformat(timespec="seconds"),
            "model_version":"local-daily-shadow-v0.1","production_effect":False,
            "method":"公式出馬表の直近5走着順と当距離実績に基づく、オッズ非参照の再現可能なcompact STEP1基準",
            "method_limitations":["過去レースの格差・馬場差・タイム指数は未補正", "騎手・斤量は記録対象だが能力スコアには未投入", "レース当日馬場・バイアスが公表前の場合は未確認"],
            "going":"未確認（予想固定時点の公式出馬表で未取得）",
            "track_bias_evidence":None,"pace":pace,"top_pick":{"horse_no":top["horse_no"],"horse_name":top["horse_name"]},
            "ability_order":[{"horse_no":r["horse_no"],"horse_name":r["horse_name"],"ability_rank":r["ability_rank"],"evidence_score":r["evidence_score"]} for r in ranked],
            "runners":runners,
            "sources":[{"name":"NAR公式・当日出馬表（過去5走を含む）","url":url,"observed_at":seen.isoformat(timespec="seconds")},
                       {"name":"NAR公式・当日メニュー","url":program["program_url"],"observed_at":program["program_seen_at"].isoformat(timespec="seconds")}],
            "official_declared_count":program["declared_count"],"observed_runner_count":len(runners)}

def main():
    if dt.datetime.now(JST).date().isoformat()!=DATE:
        raise ValueError("Date advanced mid-execution")
    cfg=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
    if cfg.get("production_effect") is not False:
        raise ValueError("JRA isolation invariant failed")
    records=[]
    for key,(venue,code) in VENUES.items():
        if not cfg["venues"][key]["enabled"]:
            continue
        race_program=extract_program(code)
        if race_program:
            print(f"Official {venue}: {len(race_program)} races",flush=True)
        for p in race_program:
            dest=OUT / f"{DATE.replace('-','')}-{key}-{p['race_no']:02d}.json"
            if dest.exists():
                print(f"Immutable existing prediction; preserving {dest}",flush=True)
                continue
            records.append((dest,build(venue,code,p)))
    if not records:
        print("No new pre-race official entries; no changes",flush=True)
        return
    if len(records)!=24 and DATE=="2026-10-08":
        raise ValueError(f"Fail closed: expected 24 races on 2026-10-08, found {len(records)}")
    if dt.datetime.now(JST) >= min(dt.datetime.fromisoformat(p["scheduled_start_at"]) for _,p in records)-dt.timedelta(minutes=2):
        raise ValueError("First relevant race cutoff exceeded before atomic file write")
    OUT.mkdir(parents=True,exist_ok=True)
    # Only write after *all* official cards and baseline rankings have validated.
    for dest,obj in records:
        if dest.exists():
            raise ValueError(f"Refusing to overwrite immutable snapshot {dest}")
        dest.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"CREATED {len(records)} official-only pre-race Shadow snapshots",flush=True)

if __name__=="__main__":
    try: main()
    except Exception as ex:
        print(f"BLOCKER: {type(ex).__name__}: {ex}",file=sys.stderr,flush=True)
        sys.exit(1)
