#!/usr/bin/env python3
"""JRA official-only prestart STEP1 factor evidence for E012 research.

NOT the full nine-factor formal model. Captures observed pace-position, ground,
course, pedigree and jockey identities, preserving incomplete marks as null.
Never rewrites an original snapshot, formal forecast or existing research proxy.
Never uses odds or finish results of the current race.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")
FACTOR_NAMES = ["斤量", "展開", "馬場", "ローテ", "コース", "血統", "調教", "騎手", "基礎能力"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def when(value):
    obj = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if obj.tzinfo is None:
        raise ValueError("naive_timestamp")
    return obj


def first_git_proof(path, start):
    relative = str(path.relative_to(ROOT))
    lines = subprocess.check_output(
        ["git", "log", "--diff-filter=A", "--reverse", "--format=%H %cI", "--", relative],
        text=True, cwd=ROOT).strip().splitlines()
    if len(lines) != 1:
        raise ValueError("first_git_proof_not_unique")
    commit, timestamp = lines[0].split()
    if when(timestamp) >= start:
        raise ValueError("source_first_commit_not_prestart")
    initial = subprocess.check_output(
        ["git", "show", commit + ":" + relative], cwd=ROOT)
    if initial != path.read_bytes():
        raise ValueError("immutable_source_modified_after_first_commit")
    return {"commit": commit, "at": timestamp}


def strip(text):
    return " ".join(text.split())


def parse_past(cell, race_day):
    t = strip(cell.get_text(" ", strip=True))
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", t)
    if not m or "除外" in t or "取消" in t:
        return None
    past_day = date(*map(int, m.groups()))
    if past_day >= race_day:
        raise ValueError("future_or_today_past_race")
    surface = re.search(r"(\d{3,4})\s*(芝|ダ)", t)
    position = re.search(r"(\d{1,2})\s*頭", t)
    finish = re.search(r"(\d+)\s*着", t)
    condition = re.search(r"(?:\d+:\d{2}\.\d+)\s*(良|稍重|重|不良)", t)
    passing = None
    if "kg" in t and "3F" in t:
        between = t.split("kg", 1)[1].split("3F", 1)[0]
        if re.fullmatch(r"\s*(?:\d{1,2}\s+){0,3}\d{1,2}\s*", between):
            parts = [int(s) for s in between.split()]
            field = int(position.group(1)) if position else 0
            if field and 1 <= len(parts) <= 4 and all(1 <= v <= field for v in parts):
                passing = parts
    return {
        "date": past_day.isoformat(),
        "going": condition.group(1) if condition else None,
        "surface": ("芝" if surface and surface.group(2) == "芝" else
                    "ダート" if surface else None),
        "distance_m": int(surface.group(1)) if surface else None,
        "course": t[m.end():].strip().split(" ")[0],
        "field": int(position.group(1)) if position else None,
        "finish": int(finish.group(1)) if finish else None,
        "passing_positions": passing,
        "source_excerpt": t[:250]
    }


def extract_card(url, race_day, frozen_names):
    if not re.fullmatch(r"https://www\.jra\.go\.jp/JRADB/accessD\.html\?CNAME=[\w%/]+", url):
        raise ValueError("non_official_JRA_card")
    response = requests.get(url, timeout=25, headers={
        "User-Agent": "Mozilla/5.0 (compatible; E012 JRA official research provenance audit)"})
    response.raise_for_status()
    raw = response.content
    if len(raw) < 1600:
        raise ValueError("incomplete_official_html")
    doc = BeautifulSoup(raw, "html.parser")
    page = strip(doc.get_text(" ", strip=True))
    course = re.search(r"コース\s*[:：]\s*([\d,]+)\s*メートル\s*[（(]\s*(芝|ダート)", page)
    if course is None:
        raise ValueError("official_course_distance_surface_unverifiable")
    meters = int(course.group(1).replace(",", ""))
    surface = course.group(2)
    head = page[:page.find("コース") + 90]
    going = re.search(r"(芝|ダート)\s*(良|稍重|重|不良)", head)
    current_going = going.group(2) if going and going.group(1) == surface else None
    parsed = {}
    withdrawn = {}
    names_inv = {v: k for k, v in frozen_names.items()}
    if len(names_inv) != len(frozen_names):
        raise ValueError("duplicated_frozen_names")
    for tr in doc.select("table tr"):
        no = tr.select_one("td.num")
        horse = tr.select_one("td.horse")
        jockey = tr.select_one("td.jockey")
        if not (no and horse and jockey):
            continue
        number = strip(no.get_text(" ", strip=True))
        horse_text = strip(horse.get_text(" ", strip=True))
        name = horse_text.split(" ")[0]
        match = re.search(r"\d+", number)
        if match is None:
            if name in names_inv and ("取消" in number or "除外" in number):
                withdrawn[names_inv[name]] = {"horse_number": names_inv[name], "reason": number}
            continue
        n = int(match.group(0))
        if n in parsed:
            raise ValueError("duplicate_JRA_horse_number")
        jockey_text = strip(jockey.get_text(" ", strip=True))
        weight = re.search(r"(\d{2}(?:\.\d+)?)\s*kg", jockey_text)
        jockey_name = jockey_text[weight.end():].strip() if weight else None
        sire = re.search(r"父\s*[：:]\s*(.+?)(?=\s+母\s*[：:]|$)", horse_text)
        dam = re.search(r"母\s*[：:]\s*(.+?)(?:\s*[\(（]母の父\s*[：:]|$)", horse_text)
        broodmare_sire = re.search(r"母の父\s*[：:]\s*(.+?)\s*[\)）]", horse_text)
        past = [x for c in tr.select("td.past") if (x := parse_past(c, race_day)) is not None]
        parsed[n] = {
            "name": name,
            "jockey": jockey_name or None,
            "declared_weight_kg": float(weight.group(1)) if weight else None,
            "sire": sire.group(1).strip() if sire else None,
            "dam": dam.group(1).strip() if dam else None,
            "damsire": broodmare_sire.group(1).strip() if broodmare_sire else None,
            "recent_races": past
        }
    if set(parsed) & set(withdrawn) or set(parsed) | set(withdrawn) != set(frozen_names):
        raise ValueError("official_field_mismatch_unaccounted")
    for n, value in parsed.items():
        if value["name"] != frozen_names[n]:
            raise ValueError("official_horse_name_mismatch:" + str(n))
    return parsed, withdrawn, {
        "url": url, "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw), "course_m": meters,
        "surface": surface, "going": current_going,
        "going_explicitly_verified": current_going is not None
    }


def make_evidence(item, original, existing, snapshot, original_proof, existing_proof):
    deadline = when(item["start_at"])
    if datetime.now(JST) >= deadline:
        raise ValueError("poststart_evidence_prohibited")
    if item["sample_origin"] != "stratified_sample" or existing["race_id"] != item["race_id"]:
        raise ValueError("study_identity_mismatch")
    all_horses = snapshot["experience"]["horses"]
    name_by_number = {int(n): h["horse_name"] for n, h in all_horses.items()}
    card, withdrawn, source = extract_card(
        snapshot["race_context"]["official_source_url"],
        date.fromisoformat(item["date"]), name_by_number)
    source_names = {x["horse_number"]: x["horse_name"] for x in existing["runners"]}
    if set(source_names) != set(card) or any(source_names[n] != v["name"] for n, v in card.items()):
        raise ValueError("unmodified_previous_research_field_mismatch")
    runners = []
    for n in sorted(card):
        horse = card[n]
        visible = horse["recent_races"]
        past_position = []
        for p in visible:
            if p["passing_positions"] and p["field"]:
                past_position.append({
                    "race_date": p["date"], "first_passing_position": p["passing_positions"][0],
                    "field_size": p["field"],
                    "front_fraction": round(p["passing_positions"][0] / p["field"], 4)})
        similar_ground = [p for p in visible if p["going"] is not None and
                          p["going"] == source["going"] and p["surface"] == source["surface"]]
        same_course = [p for p in visible if p["course"] == item["venue"] and
                       p["distance_m"] == source["course_m"] and p["surface"] == source["surface"]]
        factors = {
            "2_pace": {
                "historical_first_section_positions": past_position,
                "pace_position_evidence_count": len(past_position),
                "grade": None,
                "missing": "future_race_pace_and_tactical_interactions_unverified",
                "observed_prestart": bool(past_position)},
            "3_ground": {
                "official_current_going": source["going"],
                "similar_going_record": [{"date": p["date"], "finish": p["finish"], "field": p["field"]}
                                         for p in similar_ground],
                "grade": None,
                "missing": "surface_condition_tolerance_needs_calibrated_comparison",
                "observed_prestart": bool(similar_ground)},
            "5_course": {
                "official_distance_m": source["course_m"], "official_surface": source["surface"],
                "prior_matching_course_races": [
                    {"date": p["date"], "finish": p["finish"], "field": p["field"]}
                    for p in same_course],
                "grade": None,
                "missing": "race_course_advantage_not_calibrated",
                "observed_prestart": bool(same_course)},
            "6_pedigree": {
                "official_sire": horse["sire"], "official_dam": horse["dam"],
                "official_damsire": horse["damsire"],
                "grade": None,
                "missing": "independent_sire_condition_strike_rates_absent",
                "observed_prestart": horse["sire"] is not None},
            "7_workouts": {
                "grade": None, "workout_times": None,
                "missing": "per_horse_prerace_training_times_not_in_this_free_official_card",
                "observed_prestart": False},
            "8_jockey": {
                "official_jockey": horse["jockey"],
                "official_weight_kg": horse["declared_weight_kg"],
                "grade": None,
                "missing": "jockey_course_and_surface_strike_rates_not_verified",
                "observed_prestart": horse["jockey"] is not None}
        }
        runners.append({
            "horse_number": n, "horse_name": horse["name"],
            "regime": all_horses[str(n)]["regime"],
            "raced_before": all_horses[str(n)]["starts_before_race"],
            "factor_evidence": factors})
    return {
        "schema_version": 1, "race_id": item["race_id"], "date": item["date"],
        "start_at": item["start_at"], "week_id": item["week_id"],
        "capture_type": "separate_prestart_JRA_source_verified_factor_evidence_not_nine_grade_prediction",
        "source_original_research_file": str(original.relative_to(ROOT)),
        "source_original_research_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "source_original_research_first_proof": original_proof,
        "source_existing_research_file": str(existing_proof["path"]),
        "source_existing_research_sha256": existing_proof["sha256"],
        "source_existing_research_first_proof": existing_proof["first_proof"],
        "official_card": source,
        "captured_at": datetime.now(JST).isoformat(timespec="milliseconds"),
        "withdrawn": list(withdrawn.values()),
        "scope": "research_evidence_only_no_prediction_or_recalculation",
        "all_nine_factors_scored": False,
        "no_current_race_results_used": True,
        "no_odds_read_for_scores": True,
        "production_effect": False,
        "runners": runners
    }


def run(week, today):
    if datetime.now(JST).date().isoformat() != today:
        raise ValueError("only_current_JST_day")
    base = ROOT / "experience_regime_v1" / "collection" / week
    plan = read(base / "sample_plan.json")
    proof = read(base / ("proof_commit_" + today + ".json"))
    if plan["week_id"] != week or proof["date"] != today:
        raise ValueError("plan_or_proof_mismatch")
    selected = [dict(x, week_id=week) for x in plan["selected_races"]
                if x["date"] == today and x["sample_origin"] == "stratified_sample"]
    outdir = ROOT / "experience_regime_v1" / "factor_evidence" / week
    summary = {"schema_version": 1, "date": today, "week_id": week,
               "target_races": len(selected), "proof_verified_races": [],
               "blocked": [], "horses": 0,
               "factor_support_counts": {str(i): 0 for i in (2, 3, 5, 6, 7, 8)},
               "full_nine_factor_predictions": 0,
               "no_odds_or_results_used": True,
               "production_effect": False}
    for item in selected:
        rid = item["race_id"]
        output = outdir / (rid + ".json")
        try:
            original = base / "snapshots" / (rid + ".json")
            candidate = ROOT / "experience_regime_v1" / "research_step1_candidates" / week / (rid + ".json")
            start = when(item["start_at"])
            original_proof = first_git_proof(original, start)
            candidate_proof = first_git_proof(candidate, start)
            original_obj, candidate_obj = read(original), read(candidate)
            if original_obj["race_id"] != rid or candidate_obj["race_id"] != rid:
                raise ValueError("research_original_identity_mismatch")
            if not next(x for x in proof["races"] if x["race_id"] == rid)["proof_prestart_valid"]:
                raise ValueError("original_first_proof_invalid")
            if output.exists():
                evidence = read(output)
            else:
                evidence = make_evidence(item, original, candidate_obj, original_obj, original_proof, {
                    "path": candidate.relative_to(ROOT),
                    "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    "first_proof": candidate_proof})
                if datetime.now(JST) >= start:
                    raise ValueError("start_passed_before_file_written")
                outdir.mkdir(parents=True, exist_ok=True)
                with output.open("x", encoding="utf-8") as fp:
                    json.dump(evidence, fp, indent=2, ensure_ascii=False)
                    fp.write("\n")
            summary["proof_verified_races"].append(rid)
            summary["horses"] += len(evidence["runners"])
            for h in evidence["runners"]:
                for k, detail in h["factor_evidence"].items():
                    index = k.split("_", 1)[0]
                    if detail.get("observed_prestart"):
                        summary["factor_support_counts"][index] += 1
            print("E012_FACTOR_EVIDENCE_READY", rid, len(evidence["runners"]), flush=True)
        except Exception as exc:
            summary["blocked"].append({"race_id": rid, "reason": str(exc)[:240]})
            print("E012_FACTOR_EVIDENCE_BLOCKED", rid, str(exc)[:240], flush=True)
    target = ROOT / "docs/data/experience_regime_factor_evidence_status.json"
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("E012_FACTOR_EVIDENCE_REPORT", json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-id", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    run(args.week_id, args.date)
