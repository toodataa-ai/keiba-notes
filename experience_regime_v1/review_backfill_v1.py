#!/usr/bin/env python3
"""Postrace review of immutable E0/E1/E2 JRA observations.

Only JRA official results may create result rows. This script never edits
prerace snapshots, formal JRA predictions, E2E cases, or local/NAR files.
Missing prediction probabilities must remain missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experience_regime_v1"
JRA_HOST = "www.jra.go.jp"
CATEGORIES = ("debut", "maiden", "class_1", "class_2", "class_3", "open_listed", "graded")
REGIMES = ("E0", "E1", "E2")
UNSTARTED = ("取消", "除外", "出走取消", "競走除外")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_if_different(path, data):
    serialized = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == serialized:
        return False
    path.write_text(serialized, encoding="utf-8")
    return True


def normalized(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value or ""))


def get_official(session, url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.hostname != JRA_HOST or not parsed.path.startswith("/JRADB/access"):
        raise ValueError("not a JRA official JRADB URL")
    r = session.get(url, timeout=35, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    if len(r.content) < 4000:
        raise ValueError("official page unexpectedly short")
    return r, BeautifulSoup(r.content, "html.parser")


def result_link(card, card_url):
    # Links on the official postrace card are authoritative; do not guess a
    # JRA checksum suffix from the pre-race CNAME.
    probes = []
    for a in card.select("a"):
        label = normalized(a.get_text(" ", strip=True))
        for attribute in ("href", "onclick"):
            value = a.get(attribute, "")
            if value and ("accessS.html" in value or "レース結果" in label):
                probes.append(value)
    for value in probes:
        candidate = unquote(value).replace("&amp;", "&")
        found = re.search(r"(?:https?://www\.jra\.go\.jp)?/?(?:JRADB/)?accessS\.html\?CNAME=(pw01sde[A-Za-z0-9/%]+)", candidate)
        if found:
            return "https://www.jra.go.jp/JRADB/accessS.html?CNAME=" + found.group(1)
        if "accessS.html" in value and value.startswith("/"):
            return urljoin(card_url, value)
    # Some JRA navigators generate the href using a JS wrapper. Try the
    # actual official page HTML, but never infer a checksum or race identity.
    html = unquote(str(card)).replace("&amp;", "&")
    found = re.search(r"accessS\.html\?CNAME=(pw01sde[A-Za-z0-9/%]+)", html)
    if found:
        return "https://www.jra.go.jp/JRADB/accessS.html?CNAME=" + found.group(1)
    raise ValueError("official_card_has_no_parseable_result_link")


def verify_immutable(week, date, item, proof, snapshot_path, snapshot, audit):
    rid = item["race_id"]
    if snapshot["race_id"] != rid or audit["race_id"] != rid:
        raise ValueError("snapshot / audit race_id mismatch")
    if not audit.get("usable_for_e012_shadow"):
        raise ValueError("prerace_source_evidence_incomplete")
    entry = next((x for x in proof["races"] if x["race_id"] == rid), None)
    if entry is None or not entry["proof_prestart_valid"]:
        raise ValueError("missing_valid_prerace_proof")
    if proof["proof_commit"] != entry["proof_commit"]:
        raise ValueError("proof_sha_mismatch")
    sha = proof["proof_commit"]
    rel = str(snapshot_path.relative_to(ROOT))
    frozen = subprocess.check_output(["git", "show", sha + ":" + rel], cwd=ROOT)
    present = snapshot_path.read_bytes()
    if frozen != present:
        raise ValueError("prerace_snapshot_changed_since_proof")
    t = datetime.fromisoformat(snapshot["race_context"]["start_at"])
    proof_at = datetime.fromisoformat(proof["proof_commit_at"].replace("Z", "+00:00"))
    if not (proof_at < t and datetime.fromisoformat(snapshot["captured_at"]) < t):
        raise ValueError("prerace_timing_failed")
    expected = item["sample_origin"]
    if snapshot["race_context"]["sample_origin"] != expected:
        raise ValueError("fixed_sample_plan_mismatch")


def check_identity(soup, snapshot):
    text = soup.get_text(" ", strip=True)
    context = snapshot["race_context"]
    day = int(context["date"][-2:])
    race_no = context["race_no"]
    if not (context["venue"] in text and re.search(rf"{day}日", text) and
            re.search(rf"\b{race_no}\s*レース", text)):
        raise ValueError("official_result_race_identity_mismatch")


def parse_horse_results(soup, snapshot):
    frozen_horses = snapshot["experience"]["horses"]
    by_name = {normalized(h["horse_name"]): int(n) for n, h in frozen_horses.items()}
    if len(by_name) != len(frozen_horses):
        raise ValueError("prerace_horse_names_not_unique")
    rows = {}
    inspected = []
    for tr in soup.select("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        words = [normalized(cell.get_text(" ", strip=True)) for cell in cells]
        candidates = []
        for node in tr.select("td.horse, td.horse_name, td.horse-name"):
            candidates.append(normalized(node.get_text(" ", strip=True)))
        if not candidates:
            candidates = words
        found = [(name, num) for name, num in by_name.items()
                 if any(name == cell or name in cell for cell in candidates)]
        if len(found) != 1:
            if len(inspected) < 3 and len(cells) >= 5:
                inspected.append([(cell.get("class"), text[:24]) for cell, text in zip(cells, words[:8])])
            continue
        name, num = found[0]
        number_node = tr.select_one("td.num")
        if number_node is not None:
            raw_number = normalized(number_node.get_text(" ", strip=True))
            if raw_number.isdigit() and int(raw_number) != num:
                raise ValueError(f"official_result_horse_number_conflict_{num}")
        if num in rows:
            raise ValueError("duplicate_result_horse_" + str(num))
        place_text = words[0]
        placing = int(place_text) if re.fullmatch(r"\d{1,2}", place_text) else None
        if placing is None and not any(x in place_text for x in UNSTARTED + ("中止", "失格")):
            raise ValueError(f"unrecognized_finish_status_{num}_{place_text}")
        started = not any(x in place_text for x in UNSTARTED)
        rows[num] = {"horse_number": num, "horse_name": frozen_horses[str(num)]["horse_name"],
                     "regime": frozen_horses[str(num)]["regime"],
                     "starts_before_race": frozen_horses[str(num)]["starts_before_race"],
                     "finish_position": placing,
                     "finish_status": "finished" if placing is not None else place_text,
                     "started": started,
                     "actual_win": int(placing == 1) if started else None,
                     "actual_top3": int(placing is not None and placing <= 3) if started else None}
    if len(rows) != len(frozen_horses):
        missing = sorted(set(map(int, frozen_horses)) - set(rows))
        raise ValueError(f"official_result_not_fully_matched_{len(rows)}_of_{len(frozen_horses)}_missing_{missing}; sample_tr={inspected}")
    finishers = [r for r in rows.values() if r["finish_position"] is not None]
    if not finishers or not any(r["finish_position"] == 1 for r in finishers):
        raise ValueError("official_result_no_winner")
    return [rows[int(n)] for n in sorted(rows)]


def aggregate(reviews):
    group = defaultdict(list)
    for review in reviews:
        cat = review["race_category"]
        for horse in review["horses"]:
            if not horse["started"]:
                continue
            group[("all", horse["regime"])].append(horse)
            group[(cat, horse["regime"])].append(horse)
    def metric(items):
        return {"horse_observations": len(items),
                "races": len(set(x["_race_id"] for x in items)),
                "wins": sum(x["actual_win"] for x in items),
                "top3": sum(x["actual_top3"] for x in items),
                "actual_win_rate": round(sum(x["actual_win"] for x in items)/len(items), 6) if items else None,
                "actual_top3_rate": round(sum(x["actual_top3"] for x in items)/len(items), 6) if items else None,
                "predicted_win_rate": None, "predicted_top3_rate": None,
                "win_brier": None, "top3_brier": None,
                "prediction_accuracy_state": "unavailable_in_frozen_research_snapshots"}
    output = {"regimes": {}, "categories": {}}
    for regime in REGIMES:
        output["regimes"][regime] = metric(group[("all", regime)])
    for cat in CATEGORIES:
        output["categories"][cat] = {regime: metric(group[(cat, regime)]) for regime in REGIMES}
    return output


def run(week, dates):
    folder = BASE / "collection" / week
    plan = load(folder / "sample_plan.json")
    session = requests.Session()
    reviews = []
    blockers = []
    for date in dates:
        proof = load(folder / ("proof_commit_" + date + ".json"))
        for item in [x for x in plan["selected_races"] if x["date"] == date]:
            rid = item["race_id"]
            input_path = folder / "snapshots" / (rid + ".json")
            audit_path = folder / "audits" / (rid + ".json")
            dest = BASE / "reviews" / week / (rid + ".json")
            try:
                snapshot = load(input_path)
                audit = load(audit_path)
                verify_immutable(week, date, item, proof, input_path, snapshot, audit)
                if dest.exists():
                    reviewed = load(dest)
                    if reviewed["race_id"] != rid or reviewed["prerace_proof_commit"] != proof["proof_commit"]:
                        raise ValueError("existing_result_proof_conflict")
                    reviews.append(reviewed)
                    print("E012_POSTRACE_REUSED", rid, flush=True)
                    continue
                card_url = snapshot["race_context"]["official_source_url"]
                _card_r, card = get_official(session, card_url)
                result_url = result_link(card, card_url)
                result_r, soup = get_official(session, result_url)
                check_identity(soup, snapshot)
                horses = parse_horse_results(soup, snapshot)
                reviewed = {
                    "schema_version": 1, "race_id": rid, "date": date,
                    "venue": item["venue"], "race_no": item["race_no"],
                    "race_category": item["race_category"],
                    "sample_origin": item["sample_origin"],
                    "research_model_version": snapshot["model_version"],
                    "prerace_proof_commit": proof["proof_commit"],
                    "prerace_snapshot_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                    "official_result_url": result_r.url,
                    "official_result_sha256": hashlib.sha256(result_r.content).hexdigest(),
                    "result_capture_at": datetime.now(timezone.utc).isoformat(),
                    "status": "reviewed_official_result",
                    "prediction_accuracy_state": snapshot["step1_prediction_status"],
                    "no_synthetic_prediction": True,
                    "production_effect": False,
                    "horses": horses,
                }
                save_if_different(dest, reviewed)
                reviews.append(reviewed)
                print("E012_POSTRACE_REVIEWED", rid, "horses", len(horses), "url", result_r.url, flush=True)
            except Exception as exc:
                blockers.append({"race_id": rid, "date": date, "reason": str(exc)[:800]})
                print("E012_POSTRACE_BLOCKER", rid, str(exc)[:800], flush=True)
            time.sleep(0.35)
    # Add an internal race identifier to rows only in-memory for aggregate calculations.
    for review in reviews:
        for horse in review["horses"]:
            horse["_race_id"] = review["race_id"]
    summary = aggregate(reviews)
    for review in reviews:
        for horse in review["horses"]:
            horse.pop("_race_id", None)
    selected = [x for x in plan["selected_races"] if x["date"] in dates]
    status = {
        "schema_version": 1, "model_version": "e012-shadow-v0.1",
        "week_id": week, "dates": dates,
        "selected_races": len(selected), "reviewed_races": len(reviews),
        "pending_races": len(blockers), "blockers": blockers,
        "result_source": "JRA official JRADB result pages only",
        "prerace_proofs_verified": True,
        "no_undocumented_prediction_accuracy": True,
        "production_effect": False,
        "reviewed_race_ids": [r["race_id"] for r in reviews],
        "overall": summary["regimes"],
        "categories": summary["categories"],
    }
    save_if_different(ROOT / "docs/data/experience_regime_review_status.json", status)
    print("E012_POSTRACE_TOTAL",len(reviews),"/",len(selected),"blockers",len(blockers),flush=True)
    print("E012_POSTRACE_REGIMES", json.dumps(status["overall"], ensure_ascii=False), flush=True)
    return len(blockers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-id", default="2026-10-17")
    ap.add_argument("--dates", nargs="+", default=["2026-10-17", "2026-10-18"])
    args = ap.parse_args()
    return 0 if run(args.week_id, args.dates) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
