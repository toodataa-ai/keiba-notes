#!/usr/bin/env python3
"""One-shot prospective undercard STEP1 Shadow: primary-source evidence, explicitly incomplete factors.

This is NOT the production JRA STEP1 and never changes formal predictions or immutable
experience snapshots. Unknown inputs are null, never invented as favorable evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")
GRADES = ("C", "B-", "B", "B+", "A", "A+")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def when(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("naive_time")
    return dt


def first_proof(path, deadline):
    rel = str(path.relative_to(ROOT))
    lines = subprocess.check_output(
        ["git", "log", "--diff-filter=A", "--reverse", "--format=%H %cI", "--", rel],
        cwd=ROOT, text=True).strip().splitlines()
    if len(lines) != 1:
        raise ValueError("first_snapshot_git_commit_not_unique")
    commit, timestamp = lines[0].split()
    if when(timestamp) >= deadline:
        raise ValueError("original_experience_snapshot_not_prestart")
    initial = subprocess.check_output(["git", "show", commit + ":" + rel], cwd=ROOT)
    if initial != path.read_bytes():
        raise ValueError("original_experience_snapshot_has_changed")
    return commit, timestamp


def parse_official(url, race_date, number_to_name):
    if not re.fullmatch(r"https://www\.jra\.go\.jp/JRADB/accessD\.html\?CNAME=[\w%/]+", url):
        raise ValueError("non_JRA_official_source")
    response = requests.get(url, timeout=25, headers={
        "User-Agent": "Mozilla/5.0 (compatible; E012 prospective primary-source audit)"})
    response.raise_for_status()
    raw = response.content
    if len(raw) < 1500:
        raise ValueError("official_response_too_short")
    html = BeautifulSoup(raw, "html.parser")
    rows = html.select("table tr")
    parsed = {}
    for tr in rows:
        number = tr.select_one("td.num")
        horse = tr.select_one("td.horse")
        jockey = tr.select_one("td.jockey")
        if not (number and horse and jockey):
            continue
        n = re.search(r"\d+", number.get_text(" ", strip=True))
        if not n:
            continue
        no = int(n.group())
        name = horse.get_text(" ", strip=True).split(" ")[0]
        if no in parsed:
            raise ValueError("duplicated_official_horse_number")
        # Only source-visible evidence; no odds, results, future data, or synthetic history.
        jockey_text = jockey.get_text(" ", strip=True)
        kg = re.search(r"(\d{2}(?:\.\d)?)\s*kg", jockey_text)
        past = []
        for cell in tr.select("td.past"):
            t = " ".join(cell.get_text(" ", strip=True).split())
            day = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", t)
            if not day:
                continue
            past_date = date(*map(int, day.groups()))
            if past_date >= race_date:
                raise ValueError("future_or_current_date_history_forbidden")
            finish = re.search(r"(\d+)\s*着", t)
            dist = re.search(r"(\d{3,4})(芝|ダ)", t)
            course = t[day.end():].strip().split(" ")[0] if t[day.end():].strip() else ""
            past.append({
                "date": past_date.isoformat(),
                "finish": int(finish.group(1)) if finish else None,
                "distance_m": int(dist.group(1)) if dist else None,
                "surface": "芝" if dist and dist.group(2) == "芝" else "ダート" if dist else None,
                "course": course,
                "source_excerpt": t[:220]})
        parsed[no] = {"horse_name": name, "weight_kg": float(kg.group(1)) if kg else None,
                      "past": past}
    expected = set(number_to_name)
    if set(parsed) != expected:
        raise ValueError("official_roster_mismatch:" + str(sorted(expected ^ set(parsed))))
    for n, name in number_to_name.items():
        if parsed[n]["horse_name"] != name:
            raise ValueError("horse_number_name_changed:" + str(n))
    return parsed, hashlib.sha256(raw).hexdigest(), len(raw)


def grade(value):
    if value is None:
        return None
    if value >= 0.75:
        return "A"
    if value >= 0.55:
        return "B+"
    if value >= 0.30:
        return "B"
    return "B-"


def rank_inputs(horse, official, today, race):
    """Only factors 1,4,5,9 may be supported from visible primary-source history."""
    starts = horse["starts_before_race"]
    history = official["past"]
    if starts == 0 and history:
        raise ValueError("debut_horse_has_prior_official_history")
    w, s, t, other = horse["career_summary_wsto"]
    if sum((w, s, t, other)) != starts:
        raise ValueError("career_summary_not_consistent")
    factors = [None] * 9
    source = [None] * 9
    if official["weight_kg"] is not None:
        factors[0] = "B"
        source[0] = "official_weight_only_no_field_relative_comparison"
    if history:
        last = max(date.fromisoformat(p["date"]) for p in history)
        days = (today - last).days
        if days <= 0:
            raise ValueError("invalid_last_start")
        factors[3] = "B+" if 21 <= days <= 90 else "B" if days <= 132 else "B-"
        source[3] = "official_last_four_race_dates"
    same = [p for p in history if p["course"] == race["venue"] and
            p["distance_m"] == race["distance_m"] and p["surface"] == race["surface"]]
    if same:
        factors[4] = "A" if any(p["finish"] is not None and p["finish"] <= 3 for p in same) else "B"
        source[4] = "official_same_venue_surface_distance_recent_finishes"
    ability = None
    if starts:
        form = [(max(0.0, 1.0 - (p["finish"] - 1) / 9.0))
                for p in history if p["finish"] is not None]
        baseline = (2 * w + s + 0.5 * t) / (2 * starts)
        ability = 0.65 * baseline + 0.35 * (sum(form) / len(form) if form else baseline)
        factors[8] = grade(ability)
        source[8] = "official_career_wins_places_and_recent_form_uncalibrated"
    # Unavailable: ②pace, ③ground-specific record, ⑥pedigree,
    # ⑦workout, ⑧jockey-adjusted statistics. Never substitute plausible grades.
    gmap = {"A+": 2.0, "A": 1.5, "B+": 1.0, "B": 0.5, "B-": 0.0, "C": -0.5}
    score = sum((gmap[g] - 0.5) * weight for g, weight in zip(
        factors, (1.0, 0, 0, 0.7, 1.0, 0, 0, 0, 2.6)) if g is not None)
    return factors, source, round(score, 6), ability


def probabilities(scores):
    """Experimental Bradley-Terry/Plackett-Luce style ranking proxy, NEVER calibrated."""
    n = len(scores)
    weights = [math.exp(max(-8, min(8, s))) for s in scores]
    total = sum(weights)
    win = [w / total for w in weights]
    top3 = [0.0] * n
    for a in range(n):
        p1 = weights[a] / total
        for b in range(n):
            if b == a:
                continue
            p2 = p1 * weights[b] / (total - weights[a])
            for c in range(n):
                if c == a or c == b:
                    continue
                p3 = p2 * weights[c] / (total - weights[a] - weights[b])
                for idx in (a, b, c):
                    top3[idx] += p3
    if abs(sum(win) - 1) > 1e-8 or abs(sum(top3) - 3) > 1e-7:
        raise ValueError("probability_normalization_failed")
    return win, top3


def make_one(item, snapshot, proof):
    start = when(item["start_at"])
    if datetime.now(JST) >= start:
        raise ValueError("start_passed_no_retroactive_prediction")
    if item["race_id"] != snapshot["race_id"] or item["date"] != snapshot["race_context"]["date"]:
        raise ValueError("fixed_plan_snapshot_identity_mismatch")
    exp = snapshot["experience"]["horses"]
    names = {int(n): horse["horse_name"] for n, horse in exp.items()}
    official_url = snapshot["race_context"]["official_source_url"]
    race = {"venue": item["venue"], "surface": None, "distance_m": None}
    # The original fixed race card records names/starts but no distance/surface.
    # Do not guess these; leave same-condition suitability unavailable.
    parsed, html_sha, html_bytes = parse_official(
        official_url, date.fromisoformat(item["date"]), names)
    rows = []
    for no in sorted(names):
        h = exp[str(no)]
        if h["source_url"] != official_url or h["regime"] != ("E0" if h["starts_before_race"] == 0 else "E1" if h["starts_before_race"] <= 3 else "E2"):
            raise ValueError("original_lifetime_record_not_verified")
        factors, sources, score, ability = rank_inputs(
            h, parsed[no], date.fromisoformat(item["date"]), race)
        rows.append({"horse_number": no, "horse_name": names[no], "regime": h["regime"],
                     "factor_grades": factors, "factor_evidence": sources,
                     "unavailable_factor_indices": [i + 1 for i, g in enumerate(factors) if g is None],
                     "unverified_or_unavailable_weight": parsed[no]["weight_kg"] is None,
                     "research_proxy_score": score,
                     "career_ability_proxy": ability,
                     "official_prior_races_visible": len(parsed[no]["past"]),
                     "official_prior_evidence": parsed[no]["past"]})
    # Baseline is uniform for E0 (no racing evidence), not falsely interpreted
    # as a calibrated ability estimate or as genuine 9-factor STEP1.
    win, top3 = probabilities([r["research_proxy_score"] for r in rows])
    all_debut = all(h["career_ability_proxy"] is None for h in rows)
    ordered = sorted(rows, key=lambda h: (-h["research_proxy_score"], h["horse_number"]))
    rank_by = {h["horse_number"]: i + 1 for i, h in enumerate(ordered)}
    for i, h in enumerate(rows):
        h["predicted_win_probability"] = win[i]
        h["predicted_top3_probability"] = top3[i]
        h["step1_rank"] = None if all_debut else rank_by[h["horse_number"]]
        rank = h["step1_rank"]
        h["mark"] = None if rank is None else ("◎" if rank == 1 else "○" if rank == 2 else
                "▲" if rank == 3 else "△" if rank <= 6 else "×")
    return {
        "schema_version": 1, "race_id": item["race_id"], "date": item["date"],
        "venue": item["venue"], "race_no": item["race_no"],
        "race_category": item["race_category"], "start_at": item["start_at"],
        "sample_origin": "stratified_sample",
        "capture_type": "experimental_e012_undercard_price_blind_partial_STEP1",
        "not_canonical_formal_STEP1": True,
        "complete_nine_factor_evidence": False,
        "probabilities_calibrated": False,
        "probabilities_interpretation": "experimental uncalibrated normalized proxy; E0 neutral priors, not observed ability",
        "unobserved_factors": [2, 3, 6, 7, 8],
        "rank_method": "experimental_supported_factors_only; tie by horse number; all E0 = no asserted rank",
        "no_odds_or_results_accessed": True, "no_fabricated_source_evidence": True,
        "production_effect": False,
        "source_official_jra_url": official_url,
        "source_official_html_sha256": html_sha, "source_official_html_bytes": html_bytes,
        "original_experience_proof_commit": proof["proof_commit"],
        "original_experience_snapshot_sha256": hashlib.sha256((ROOT / "experience_regime_v1" / "collection" / item["week_id"] / "snapshots" / (item["race_id"] + ".json")).read_bytes()).hexdigest(),
        "calculated_at": datetime.now(JST).isoformat(),
        "runners": rows
    }


def run(week, day):
    if day != datetime.now(JST).date().isoformat():
        raise ValueError("not_current_JST_day")
    root = ROOT / "experience_regime_v1" / "collection" / week
    plan = read(root / "sample_plan.json")
    proof = read(root / ("proof_commit_" + day + ".json"))
    if plan["week_id"] != week or proof["week_id"] != week or proof["date"] != day:
        raise ValueError("wrong_fixed_plan")
    selected = [r for r in plan["selected_races"] if r["date"] == day and r["sample_origin"] == "stratified_sample"]
    outdir = ROOT / "experience_regime_v1" / "research_step1_candidates" / week
    report = {"schema_version": 1, "date": day, "week_id": week,
              "target_undercard_races": len(selected), "experimental_partial_races": [],
              "blocked": [], "formal_step1_frozen_races_separately": 2,
              "complete_nine_factor_research_predictions": 0,
              "production_effect": False, "does_not_change_canonical_step1_status": True}
    for item in selected:
        rid = item["race_id"]
        target = outdir / (rid + ".json")
        if target.exists():
            report["experimental_partial_races"].append(rid)
            continue
        try:
            original = root / "snapshots" / (rid + ".json")
            snapshot = read(original)
            start = when(item["start_at"])
            first_proof(original, start)
            evidence = next(x for x in proof["races"] if x["race_id"] == rid)
            if not evidence["proof_prestart_valid"]:
                raise ValueError("original_observation_proof_invalid")
            result = make_one({**item, "week_id": week}, snapshot, proof)
            if datetime.now(JST) >= start:
                raise ValueError("start_passed_during_preparation")
            outdir.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                f.write("\n")
            report["experimental_partial_races"].append(rid)
            print("E012_BULK_CANDIDATE_CREATED", rid, len(result["runners"]), flush=True)
        except Exception as e:
            report["blocked"].append({"race_id": rid, "reason": str(e)[:240]})
            print("E012_BULK_BLOCKED", rid, str(e)[:240], flush=True)
    target = ROOT / "docs/data/experience_regime_research_step1_bulk_status.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("E012_BULK_SUMMARY", len(report["experimental_partial_races"]), "/", len(selected),
          "blocked", len(report["blocked"]), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--week-id", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    run(args.week_id, args.date)
