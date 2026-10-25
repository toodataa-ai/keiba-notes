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
    if proof["week_id"] != week or proof["date"] != date:
        raise ValueError("prerace_proof_week_or_date_mismatch")
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
    committed_at = subprocess.check_output(
        ["git", "show", "-s", "--format=%cI", sha], cwd=ROOT, text=True
    ).strip()
    if datetime.fromisoformat(committed_at) != datetime.fromisoformat(
        proof["proof_commit_at"].replace("Z", "+00:00")
    ):
        raise ValueError("proof_commit_timestamp_conflict")
    if snapshot["race_context"]["race_category"] != item["race_category"]:
        raise ValueError("fixed_race_category_mismatch")
    if snapshot["race_context"]["date"] != date:
        raise ValueError("fixed_race_date_mismatch")
    for number, horse in snapshot["experience"]["horses"].items():
        starts = horse["starts_before_race"]
        if not isinstance(starts, int) or isinstance(starts, bool) or starts < 0:
            raise ValueError("invalid_frozen_starts")
        expected = "E0" if starts == 0 else "E1" if starts <= 3 else "E2"
        if horse["regime"] != expected or int(number) != horse["horse_number"]:
            raise ValueError("frozen_regime_or_horse_number_conflict")
        if starts != sum(horse["career_summary_wsto"]):
            raise ValueError("frozen_career_total_conflict")
    rel = str(snapshot_path.relative_to(ROOT))
    frozen = subprocess.check_output(["git", "show", sha + ":" + rel], cwd=ROOT)
    present = snapshot_path.read_bytes()
    if frozen != present:
        raise ValueError("prerace_snapshot_changed_since_proof")
    # The immutable audit and weekly selection were also present in the
    # prerace proof commit. Check their exact bytes before accepting outcomes.
    audit_path = snapshot_path.parent.parent / "audits" / snapshot_path.name
    plan_path = snapshot_path.parent.parent / "sample_plan.json"
    for evidence_path, error_code in (
        (audit_path, "prerace_audit_changed_since_proof"),
        (plan_path, "prerace_sample_plan_changed_since_proof"),
    ):
        evidence_rel = str(evidence_path.relative_to(ROOT))
        evidence_frozen = subprocess.check_output(
            ["git", "show", sha + ":" + evidence_rel], cwd=ROOT
        )
        if evidence_frozen != evidence_path.read_bytes():
            raise ValueError(error_code)
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
        if len(words) > 3 and words[2].isdigit() and name in words[3] and int(words[2]) != num:
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


def persist_official_result(week, review):
    """Derive a separate, immutable-source-linked result record; never change prerace inputs."""
    record = {
        "schema_version": 1,
        "race_id": review["race_id"],
        "date": review["date"],
        "race_category": review["race_category"],
        "source": "JRA official JRADB result and payout confirmation",
        "official_result_url": review["official_result_url"],
        "official_result_sha256": review["official_result_sha256"],
        "result_capture_at": review["result_capture_at"],
        "prerace_proof_commit": review["prerace_proof_commit"],
        "prerace_snapshot_sha256": review["prerace_snapshot_sha256"],
        "no_synthetic_prediction": True,
        "production_effect": False,
        "horses": [
            {key: horse[key] for key in (
                "horse_number", "horse_name", "started",
                "finish_position", "finish_status", "actual_win", "actual_top3"
            )}
            for horse in review["horses"]
        ],
    }
    return save_if_different(BASE / "results" / week / (review["race_id"] + ".json"), record)


def aggregate(reviews):
    groups = defaultdict(list)
    for review in reviews:
        category = review["race_category"]
        for h in review["horses"]:
            if not h["started"]:
                continue
            row = dict(h, _race_id=review["race_id"])
            groups[("all", h["regime"])].append(row)
            groups[(category, h["regime"])].append(row)

    def metric(rows):
        n = len(rows)
        wins = sum(x["actual_win"] for x in rows)
        top3 = sum(x["actual_top3"] for x in rows)
        result = {
            "horse_observations": n, "races": len({x["_race_id"] for x in rows}),
            "wins": wins, "top3": top3,
            "actual_win_rate": round(wins/n, 6) if n else None,
            "actual_top3_rate": round(top3/n, 6) if n else None,
        }
        ranks = [x["step1_rank"] for x in rows if "step1_rank" in x]
        result["step1_rank_observations"] = len(ranks)
        result["step1_mean_rank"] = round(sum(ranks)/len(ranks), 6) if ranks else None
        for target, prefix in (("actual_win", "win"), ("actual_top3", "top3")):
            key = "predicted_" + ("win" if prefix == "win" else "top3") + "_probability"
            samples = [x for x in rows if key in x]
            result[prefix + "_prediction_observations"] = len(samples)
            # Incomplete groups do not receive a deceptively full-group score.
            if n and len(samples) == n:
                mean_p = sum(x[key] for x in samples) / n
                result["predicted_" + prefix + "_rate"] = round(mean_p, 6)
                result[prefix + "_brier"] = round(
                    sum((x[key] - x[target])**2 for x in samples)/n, 6)
                result[prefix + "_calibration_error"] = round(
                    mean_p - result["actual_" + prefix + "_rate"], 6)
            else:
                result["predicted_" + prefix + "_rate"] = None
                result[prefix + "_brier"] = None
                result[prefix + "_calibration_error"] = None
        result["prediction_accuracy_state"] = (
            "available_from_frozen_snapshot" if n and
            result["win_prediction_observations"] == n and
            result["top3_prediction_observations"] == n
            else "unavailable_or_partial_in_frozen_research_snapshots"
        )
        return result

    return {
        "regimes": {k: metric(groups[("all", k)]) for k in REGIMES},
        "categories": {c: {k: metric(groups[(c, k)]) for k in REGIMES} for c in CATEGORIES}
    }


def regime_rate_differences(metrics):
    """Observed percentage-point differences only; no significance claims."""
    pairs = (("E0", "E2"), ("E1", "E2"), ("E0", "E1"))
    differences = {}
    for left, right in pairs:
        a, b = metrics[left], metrics[right]
        differences[left + "_minus_" + right] = {
            "actual_win_rate_pp": (
                round(100 * (a["actual_win_rate"] - b["actual_win_rate"]), 4)
                if a["actual_win_rate"] is not None and b["actual_win_rate"] is not None else None
            ),
            "actual_top3_rate_pp": (
                round(100 * (a["actual_top3_rate"] - b["actual_top3_rate"]), 4)
                if a["actual_top3_rate"] is not None and b["actual_top3_rate"] is not None else None
            ),
            "interpretation": "descriptive_only_not_statistical_significance"
        }
    return differences



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
                    persist_official_result(week, reviewed)
                    reviews.append(reviewed)
                    print("E012_POSTRACE_REUSED", rid, flush=True)
                    continue
                card_url = snapshot["race_context"]["official_source_url"]
                _card_r, card = get_official(session, card_url)
                result_url = result_link(card, card_url)
                result_r, soup = get_official(session, result_url)
                check_identity(soup, snapshot)
                if "払戻金" not in soup.get_text(" ", strip=True):
                    raise ValueError("official_payout_not_confirmed")
                horses = parse_horse_results(soup, snapshot)
                # Optional controls must actually exist in the immutable snapshot.
                pre_runners = {int(x["horse_number"]): x for x in snapshot.get("step1", {}).get("runners", [])}
                for horse in horses:
                    source = pre_runners.get(horse["horse_number"], {})
                    for src, field_name in (("step1_rank", "step1_rank"), ("rank", "step1_rank"),
                                      ("predicted_win_probability", "predicted_win_probability"),
                                      ("predicted_top3_probability", "predicted_top3_probability")):
                        if src in source and field_name not in horse:
                            value = source[src]
                            if isinstance(value, (float, int)) and not isinstance(value, bool):
                                if field_name == "step1_rank" and value >= 1:
                                    horse[field_name] = value
                                elif field_name != "step1_rank" and 0 <= value <= 1:
                                    horse[field_name] = value
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
                persist_official_result(week, reviewed)
                reviews.append(reviewed)
                print("E012_POSTRACE_REVIEWED", rid, "horses", len(horses), "url", result_r.url, flush=True)
            except Exception as exc:
                blockers.append({"race_id": rid, "date": date, "reason": str(exc)[:800]})
                print("E012_POSTRACE_BLOCKER", rid, str(exc)[:800], flush=True)
            time.sleep(0.35)
    # Rebuild daily/weekly analyses only from already recorded, proof-linked reviews.
    eligible = {x["race_id"]: x for x in plan["selected_races"]}
    week_reviews = []
    for file in sorted((BASE / "reviews" / week).glob("*.json")):
        row = load(file)
        item = eligible.get(row.get("race_id"))
        if item is None or row.get("date") != item["date"]:
            continue
        date_proof = folder / ("proof_commit_" + item["date"] + ".json")
        if not date_proof.is_file():
            continue
        proof_row = load(date_proof)
        if row.get("prerace_proof_commit") != proof_row.get("proof_commit"):
            raise ValueError("stored_weekly_review_proof_mismatch_" + item["race_id"])
        week_reviews.append(row)
    week_ids = {x["race_id"] for x in week_reviews}
    week_metrics = aggregate(week_reviews)
    daily_summaries = {}
    for date in sorted({x["date"] for x in plan["selected_races"]}):
        due = [x for x in plan["selected_races"] if x["date"] == date]
        day_rows = [r for r in week_reviews if r["date"] == date]
        day = {
            "schema_version": 1, "week_id": week, "date": date,
            "selected_races": len(due), "reviewed_races": len(day_rows),
            "pending_races": len(due) - len(day_rows),
            "result_source": "JRA official JRADB", "production_effect": False,
            "prediction_inputs": "frozen_prestart_snapshots_only",
            "regimes": aggregate(day_rows)["regimes"],
            "categories": aggregate(day_rows)["categories"],
            "regime_rate_differences": regime_rate_differences(aggregate(day_rows)["regimes"]),
            "category_regime_rate_differences": {
                cat: regime_rate_differences(regimes)
                for cat, regimes in aggregate(day_rows)["categories"].items()
            }
        }
        daily_summaries[date] = day
        # Never publish misleading zero-result placeholder analyses for future dates.
        if day_rows:
            save_if_different(BASE / "analysis" / week / "daily" / (date + ".json"), day)

    weekly = {
        "schema_version": 1, "week_id": week, "selected_races": len(eligible),
        "reviewed_races": len(week_reviews), "pending_races": len(eligible) - len(week_reviews),
        "pending_not_yet_reviewed": sorted(set(eligible) - week_ids),
        "completed_dates": sorted({r["date"] for r in week_reviews}),
        "result_source": "JRA official JRADB",
        "production_effect": False, "automatic_promotion": False,
        "prediction_inputs": "frozen_prestart_snapshots_only",
        "regimes": week_metrics["regimes"], "categories": week_metrics["categories"],
        "regime_rate_differences": regime_rate_differences(week_metrics["regimes"]),
        "category_regime_rate_differences": {
            cat: regime_rate_differences(regimes)
            for cat, regimes in week_metrics["categories"].items()
        }
    }
    save_if_different(BASE / "analysis" / week / "weekly.json", weekly)
    status_path = ROOT / "docs/data/experience_regime_review_status.json"
    history = {}
    if status_path.exists():
        previous = load(status_path)
        history = previous.get("history_by_week", {})
        if previous.get("week_id") and previous["week_id"] != week:
            history[previous["week_id"]] = {
                "dates": previous.get("dates", []),
                "selected_races": previous.get("selected_races", 0),
                "reviewed_races": previous.get("reviewed_races", 0),
                "overall": previous.get("overall", {}),
                "categories": previous.get("categories", {})
            }
    summary = aggregate(reviews)
    selected = [x for x in plan["selected_races"] if x["date"] in dates]
    status = {
        "schema_version": 2, "model_version": "e012-shadow-v0.1",
        "week_id": week, "dates": dates,
        "selected_races": len(selected), "reviewed_races": len(reviews),
        "pending_races": len(selected) - len(reviews),
        "blockers": blockers, "history_by_week": history,
        "daily": {d: daily_summaries[d] for d in dates},
        "weekly": weekly,
        "result_source": "JRA official JRADB result pages only",
        "prerace_proofs_verified": len(blockers) == 0,
        "no_undocumented_prediction_accuracy": True,
        "production_effect": False, "automatic_promotion": False,
        "reviewed_race_ids": [r["race_id"] for r in reviews],
        "overall": summary["regimes"], "categories": summary["categories"]
    }
    save_if_different(status_path, status)
    print("E012_POSTRACE_TOTAL",len(reviews),"/",len(selected),"blockers",len(blockers),flush=True)
    print("E012_POSTRACE_REGIMES", json.dumps(status["overall"], ensure_ascii=False), flush=True)
    return len(blockers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-id", required=True)
    ap.add_argument("--dates", nargs="+", required=True)
    args = ap.parse_args()
    return 0 if run(args.week_id, args.dates) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
