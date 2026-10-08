#!/usr/bin/env python3
"""NAR POST-RACE runner. Only official results; never edits pre-race prediction.

Run: python local_racing_shadow_v1/postrace.py --date 2026-10-08
Failures remain in diagnostics; reruns reuse validated saved results/reviews.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

ROOT = Path("local_racing_shadow_v1")
JST = dt.timezone(dt.timedelta(hours=9))
ENDPOINT = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/"
CODES = {"大井": 20, "園田": 27, "川崎": 21, "船橋": 19, "浦和": 18, "名古屋": 24}
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "Mozilla/5.0 (compatible; LocalShadowPostRace/0.2; +official-sources)",
                     "Accept-Language": "ja-JP,ja;q=0.9"})

class Blocked(Exception):
    def __init__(self, state, reason):
        super().__init__(reason)
        self.state = state

def now():
    return dt.datetime.now(JST).isoformat(timespec="seconds")

def clean(value):
    return re.sub(r"\\s+", "", unicodedata.normalize("NFKC", str(value or "")))

def timestamp(value):
    v = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if v.tzinfo is None:
        raise Blocked("BLOCKED_PROOF", f"Timezone absent: {value}")
    return v

def jread(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\\n"

def write_distinct(path, obj, mutable=False):
    content = dump(obj)
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return False
        if not mutable:
            raise Blocked("BLOCKED_CONFLICT", f"Existing immutable artifact differs: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True

def git_proof(path, record):
    start = timestamp(record["scheduled_start_at"])
    cutoff = timestamp(record["information_cutoff_at"])
    generated = timestamp(record["generated_at"])
    if not generated <= cutoff < start:
        raise Blocked("BLOCKED_PROOF", "generated/cutoff/start invalid")
    rows = subprocess.check_output(["git", "log", "--no-renames", "--format=%H|%cI",
                                    "--", str(path)], text=True).splitlines()
    if len(rows) != 1:
        raise Blocked("BLOCKED_PROOF", f"Expected exactly one initial commit, found {len(rows)}")
    sha, committed = rows[0].split("|", 1)
    if timestamp(committed) >= start:
        raise Blocked("BLOCKED_PROOF", "Initial Git commit after scheduled start")
    mirror = Path("docs/data/local-racing-shadow") / "predictions" / record["date"] / path.name
    if not mirror.exists() or mirror.read_bytes() != path.read_bytes():
        raise Blocked("BLOCKED_PROOF", "Missing/different public prediction mirror")
    manifest = jread(Path("docs/data/local_racing_shadow_public.json"))
    matches = [r for r in manifest.get("races", []) if r.get("race_id") == record["race_id"]]
    if len(matches) != 1 or matches[0].get("proof_commit") != sha:
        raise Blocked("BLOCKED_PROOF", "Manifest proof_commit mismatch")
    if matches[0].get("prediction_path") != ("data/local-racing-shadow/predictions/" + record["date"] + "/" + path.name):
        raise Blocked("BLOCKED_PROOF", "Manifest prediction path mismatch")
    return sha

def http_html(route, params):
    url = ENDPOINT + route + "?" + urlencode(params)
    err = None
    for i in range(3):
        try:
            r = HTTP.get(url, timeout=35)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or r.encoding
            if "地方競馬情報サイト" not in r.text:
                raise Blocked("BLOCKED_FETCH", "NAR identity marker absent")
            return BeautifulSoup(r.text, "html.parser"), url
        except (requests.RequestException, Blocked) as exc:
            err = exc
            if i < 2:
                time.sleep(i + 1)
    raise Blocked("BLOCKED_FETCH", f"{url}: {err}")

def validate_prediction(path, p, date, enabled):
    rid = p.get("race_id")
    if (p.get("date") != date or path.stem != rid or path.parent.name != date or
            rid != f"{date.replace('-', '')}-{next((k for k, v in enabled.items() if v == p.get('venue')), '')}-{int(p.get('race_no', 0)):02d}"):
        raise Blocked("BLOCKED_JOIN", "Race ID/date/venue/race_no mismatch")
    if p.get("production_effect") is not False:
        raise Blocked("BLOCKED_PROOF", "Production isolation violated")
    if any(k in p for k in ("finish_order", "official_result", "payouts")):
        raise Blocked("BLOCKED_PROOF", "Post-race leakage found in prediction")
    runners = p.get("runners", [])
    nums = [int(x["horse_no"]) for x in runners]
    if len(nums) < 5 or len(nums) != len(set(nums)):
        raise Blocked("BLOCKED_JOIN", "Prediction horse numbers invalid")
    order = p.get("ability_order", [])
    ranks = [x["ability_rank"] for x in order]
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise Blocked("BLOCKED_JOIN", "Prediction ability ranks invalid")
    if order[0]["horse_no"] != p["top_pick"]["horse_no"]:
        raise Blocked("BLOCKED_JOIN", "Top-pick not ability rank 1")
    return nums

def parse_official(soup, p):
    # Fail closed: only the actual NAR "競走成績" table, never past-race / compete tables.
    head = next((h for h in soup.find_all(["h2","h3","h4","h5"])
                 if "競走成績" in h.get_text(" ", strip=True) and "第" in h.get_text(" ", strip=True)), None)
    if head is None:
        raise Blocked("PENDING_OFFICIAL", "Official result heading not present")
    htext = head.get_text(" ", strip=True)
    date = dt.date.fromisoformat(p["date"])
    if clean(f"{date.year}年{date.month}月{date.day}日") not in clean(htext):
        raise Blocked("BLOCKED_PARSE", "Official page date mismatch")
    if clean(p["venue"]) not in clean(htext):
        raise Blocked("BLOCKED_PARSE", "Official venue mismatch")
    if not re.search(r"第\\s*" + str(int(p["race_no"])) + r"\\s*競走", clean(htext)):
        raise Blocked("BLOCKED_PARSE", "Official race number mismatch")
    heading = head.find_next(["h2","h3","h4"])
    official_name = heading.get_text(" ", strip=True) if heading else None
    if official_name and clean(p["race_name"]) != clean(official_name):
        raise Blocked("BLOCKED_JOIN", f"Race name differs: {official_name} != {p['race_name']}")
    body = soup.get_text(" ", strip=True)
    dist_match = re.search(r"ダート\\s*(\\d{3,4})\\s*[ｍm]", body)
    if not dist_match:
        raise Blocked("BLOCKED_PARSE", "Official surface/distance missing")
    distance = int(dist_match.group(1))
    if distance != int(p["distance"]) or clean(p.get("surface")) != "ダート":
        raise Blocked("BLOCKED_JOIN", "Official distance/surface does not match prediction")
    going_match = re.search(r"馬場[：:]\\s*(良|稍重|重|不良)", body)
    if not going_match:
        raise Blocked("BLOCKED_PARSE", "Official going not found")
    if any(x in body for x in ("競走取り止め", "競走取止め", "競走不成立")):
        raise Blocked("CANCELLED_OFFICIAL", "Official page describes cancelled/void race")
    result_table = None
    for table in soup.find_all("table"):
        for tr in table.find_all("tr")[:5]:
            s = clean(tr.get_text(" ", strip=True))
            if all(v in s for v in ("着順", "馬番", "馬名")):
                result_table = table
                break
        if result_table:
            break
    if result_table is None:
        raise Blocked("BLOCKED_PARSE", "No verified finish-order table with 着順/馬番/馬名")
    rows = []
    for tr in result_table.find_all("tr"):
        cells = tr.find_all(["th","td"], recursive=False)
        if len(cells) < 10:
            continue
        horse_number = clean(cells[2].get_text(" ", strip=True))
        if not re.fullmatch(r"\\d{1,2}", horse_number):
            continue
        raw_rank = clean(cells[0].get_text(" ", strip=True))
        name = cells[3].get_text(" ", strip=True)
        anchor = cells[3].find("a", href=re.compile("Horse", re.I))
        if anchor:
            name = anchor.get_text(" ", strip=True)
        if not name:
            raise Blocked("BLOCKED_PARSE", f"No horse name for #{horse_number}")
        rank = int(raw_rank) if re.fullmatch(r"\\d{1,2}", raw_rank) else None
        special = next((code for code in ("出走取消", "競走除外", "競走中止", "失格", "降着", "取消", "除外", "中止")
                        if code in raw_rank), None)
        if rank is None and special is None:
            raise Blocked("BLOCKED_PARSE", f"Unrecognized finish status: {raw_rank}")
        rows.append({"horse_no": int(horse_number), "horse_name": name, "finish_position": rank,
                     "official_disposition": special, "raw_finish": raw_rank,
                     "finish_time": cells[10].get_text(" ", strip=True) if len(cells) > 10 else None})
    if len(rows) < 5:
        raise Blocked("BLOCKED_PARSE", f"Insufficient actual finish-order entries: {len(rows)}")
    nos = [x["horse_no"] for x in rows]
    if len(set(nos)) != len(nos):
        raise Blocked("BLOCKED_JOIN", "Duplicate official horse numbers")
    ranks = [x["finish_position"] for x in rows if x["finish_position"] is not None]
    if 1 not in ranks or any(k > len(rows) for k in ranks):
        raise Blocked("BLOCKED_JOIN", "Official finish ranks are invalid")
    # NAR may report legitimate dead heats: equal rank allowed, but evidence is retained.
    return {"official_race_name": official_name, "distance": distance,
            "going": going_match.group(1), "finish_order": rows,
            "official_splits": None,
            "dead_heat_positions": [r for r, c in Counter(ranks).items() if c > 1]}

def joined(p, official):
    pred = {int(x["horse_no"]): x for x in p["runners"]}
    actual = {int(x["horse_no"]): x for x in official["finish_order"]}
    unknown = sorted(actual.keys() - pred.keys())
    missing = sorted(pred.keys() - actual.keys())
    if unknown or missing:
        raise Blocked("BLOCKED_JOIN", f"Runner mismatch: official_only={unknown}, prediction_only={missing}")
    mismatched = [(no, pred[no]["horse_name"], x["horse_name"])
                  for no, x in actual.items() if clean(x["horse_name"]) != clean(pred[no]["horse_name"])]
    if mismatched:
        raise Blocked("BLOCKED_JOIN", f"Horse name discrepancy: {mismatched}")
    return actual

def make_review(p, result):
    actual = joined(p, result)
    top = p["top_pick"]
    first = actual[int(top["horse_no"])]
    top_finish = first["finish_position"]
    rank_cmp = []
    for x in p["ability_order"]:
        no = int(x["horse_no"])
        observed = actual[no]
        rank_cmp.append({"horse_no": no, "horse_name": x["horse_name"],
                         "predicted_rank": x["ability_rank"],
                         "actual_finish": observed["finish_position"],
                         "official_disposition": observed["official_disposition"]})
    evaluable = top_finish is not None
    return {"race_id": p["race_id"], "date": p["date"], "venue": p["venue"],
            "prediction_path": result["prediction_path"],
            "result_path": f"local_racing_shadow_v1/results/{p['date']}/{p['race_id']}.json",
            "prediction_sha256": result["prediction_sha256"],
            "proof_commit": result["proof_commit"], "top_pick": top,
            "actual_top_pick_finish": top_finish, "rank_comparison": rank_cmp,
            "hit_metrics": {"evaluable": evaluable, "top_pick_win": int(top_finish == 1) if evaluable else None,
                            "top_pick_top3": int(top_finish <= 3) if evaluable else None,
                            "top_pick_rank_error": abs(top_finish-1) if evaluable else None},
            "diagnostics": [{"classification": "evidence", "finding": "Official finishing position compared against frozen pre-race ranking"},
                            {"classification": "unknown", "finding": "Pre-race pace cannot be validated from finish order alone"}],
            "known_limitations": ["No post-race hindsight adjustment to the pre-race ranking",
                                  "Single-day sample cannot establish transferable effects",
                                  "Official incident narratives and bias not independently verified",
                                  "Official splits are not interpreted unless separately verified"],
            "predicted_pace": p.get("pace"), "official_pace_evidence": None,
            "source_urls": [result["official_source_url"], result["source_evidence"]["race_list_url"]],
            "review_status": "VERIFIED"}

def validate_existing(p, result, review, pred_path, sha, proof_commit):
    expected = f"local_racing_shadow_v1/predictions/{p['date']}/{p['race_id']}.json"
    if result.get("prediction_path") != expected or result.get("prediction_sha256") != sha or result.get("proof_commit") != proof_commit:
        raise Blocked("BLOCKED_CONFLICT", "Existing result provenance disagrees with immutable prediction")
    if result.get("race_id") != p["race_id"] or result.get("status") != "OFFICIAL_CONFIRMED":
        raise Blocked("BLOCKED_CONFLICT", "Existing result identity/status invalid")
    joined(p, result)
    fresh = make_review(p, result)
    if review != fresh:
        raise Blocked("BLOCKED_CONFLICT", "Existing review content differs from reproducible review")
    return True

def check_race_list(p, cache):
    venue = p["venue"]
    if venue in cache:
        return cache[venue]
    code = CODES.get(venue)
    if code is None:
        raise Blocked("BLOCKED_FETCH", f"Unknown NAR venue code for {venue}")
    soup, url = http_html("RaceList", {"k_babaCode":code, "k_raceDate":p["date"].replace("-", "/")})
    text = clean(soup.get_text(" ", strip=True))
    d = dt.date.fromisoformat(p["date"])
    if clean(f"{d.year}年{d.month}月{d.day}日") not in text:
        raise Blocked("BLOCKED_FETCH", "RaceList official date mismatch")
    cache[venue] = url
    return url

def run(date, only_id):
    cfg = jread(ROOT / "config.json")
    if cfg.get("production_effect") is not False:
        raise RuntimeError("JRA isolation invariant invalid")
    assert cfg["prompts"]["post_race"] == "local_racing_shadow_v1/shadow_review_prompt_v0_2.txt"
    enabled = {k: v["label"] for k, v in cfg["venues"].items() if v.get("enabled")}
    pred_paths = sorted((ROOT / "predictions" / date).glob("*.json"))
    if not pred_paths:
        raise RuntimeError(f"BLOCKED_NO_PREDICTIONS {date}")
    if len({p.stem for p in pred_paths}) != len(pred_paths):
        raise RuntimeError("Duplicate prediction path")
    prior_shas = {str(path): sha256(path) for path in pred_paths}
    statuses, validated = {}, {}
    cache = {}
    for path in pred_paths:
        p = jread(path)
        rid = path.stem
        if only_id and rid != only_id:
            statuses[rid] = {"status": "NOT_SELECTED", "reason": "Explicit single-race retry", "result_path": None, "review_path": None}
            continue
        result_path = ROOT / "results" / date / path.name
        review_path = ROOT / "reviews" / date / path.name
        entry = {"status": "PENDING", "reason": None, "result_path": None, "review_path": None}
        try:
            validate_prediction(path, p, date, enabled)
            proof_commit = git_proof(path, p)
            digest = prior_shas[str(path)]
            if review_path.exists() and not result_path.exists():
                raise Blocked("BLOCKED_CONFLICT", "Review exists without result")
            if result_path.exists():
                result = jread(result_path)
                if review_path.exists():
                    validate_existing(p, result, jread(review_path), path, digest, proof_commit)
                    entry.update(status="SKIPPED_VERIFIED", reason=None, result_path=str(result_path),
                                 review_path=str(review_path))
                else:
                    if result.get("prediction_sha256") != digest or result.get("proof_commit") != proof_commit:
                        raise Blocked("BLOCKED_CONFLICT", "Existing result provenance mismatch")
                    joined(p, result)
                    review = make_review(p, result)
                    write_distinct(review_path, review)
                    entry.update(status="COMPLETED", reason="Resumed review from verified stored result",
                                 result_path=str(result_path), review_path=str(review_path))
            else:
                list_url = check_race_list(p, cache)
                code = CODES[p["venue"]]
                soup, url = http_html("RaceMarkTable", {"k_babaCode":code,
                                   "k_raceDate":date.replace("-", "/"), "k_raceNo":p["race_no"]})
                parsed = parse_official(soup, p)
                joined(p, parsed)
                result = {"race_id": rid, "date": date, "venue": p["venue"], "race_no": p["race_no"],
                          "official_race_name": parsed["official_race_name"], "official_distance": parsed["distance"],
                          "official_source_url": url, "official_observed_at": now(),
                          "official_going": parsed["going"], "status": "OFFICIAL_CONFIRMED",
                          "finish_order": parsed["finish_order"], "official_splits": parsed["official_splits"],
                          "dead_heat_positions": parsed["dead_heat_positions"],
                          "prediction_path": str(path), "prediction_sha256": digest,
                          "proof_commit": proof_commit,
                          "source_evidence": {"race_list_url": list_url, "race_mark_table_url": url,
                                              "official_confirmed_at": now()},
                          "validation": {"race_identity": True, "all_horse_numbers_joined": True,
                                         "horse_names_match": True, "prediction_immutable": True}}
                review = make_review(p, result)
                write_distinct(result_path, result)
                write_distinct(review_path, review)
                entry.update(status="COMPLETED", reason=None, result_path=str(result_path),
                             review_path=str(review_path), source_url=url)
            validated[rid] = {"p": p, "result": result, "review": jread(review_path),
                              "distance": p.get("distance")}
        except Blocked as ex:
            entry.update(status=ex.state, reason=str(ex))
        except Exception as ex:
            entry.update(status="BLOCKED_IMPLEMENTATION", reason=f"{type(ex).__name__}: {ex}")
        statuses[rid] = entry
        print(f"{rid}: {entry['status']} {entry.get('reason') or ''}", flush=True)
    if only_id:
        # A single-race retry still regenerates summary using all previously verified review files.
        for path in pred_paths:
            rid = path.stem
            if rid in validated or statuses[rid]["status"] != "NOT_SELECTED":
                continue
            p = jread(path)
            try:
                validate_prediction(path, p, date, enabled)
                proof_commit = git_proof(path, p)
                rpath = ROOT / "results" / date / path.name
                vpath = ROOT / "reviews" / date / path.name
                if not (rpath.exists() and vpath.exists()):
                    raise Blocked("PENDING_OFFICIAL", "Unprocessed on single-race retry")
                result, review = jread(rpath), jread(vpath)
                validate_existing(p, result, review, path, prior_shas[str(path)], proof_commit)
                validated[rid] = {"p": p, "result": result, "review": review,
                                  "distance": p.get("distance")}
                statuses[rid] = {"status": "SKIPPED_VERIFIED", "reason": "Previously verified",
                                 "result_path": str(rpath), "review_path": str(vpath)}
            except Blocked as ex:
                statuses[rid] = {"status": ex.state, "reason": str(ex),
                                 "result_path": None, "review_path": None}
    if any(sha256(path) != old for path, old in ((Path(k),v) for k,v in prior_shas.items())):
        raise RuntimeError("FAIL: prediction SHA-256 changed during post-race operation")
    completed = [x for x in statuses.values() if x["status"] == "COMPLETED"]
    skipped = [x for x in statuses.values() if x["status"] == "SKIPPED_VERIFIED"]
    blocked = [x for x in statuses.values() if x["status"].startswith("BLOCKED")]
    pending = [x for x in statuses.values() if x["status"].startswith("PENDING")]
    valid_proof_count = len(validated) + sum(1 for x in blocked if x["status"] != "BLOCKED_PROOF" and x["status"] != "BLOCKED_JOIN")
    # Eligible category reconciliation follows mutually exclusive completion/blocked/pending.
    eligible_ids = [rid for rid, x in statuses.items() if x["status"] != "BLOCKED_PROOF"]
    for rid in eligible_ids:
        if statuses[rid]["status"] == "NOT_SELECTED":
            raise RuntimeError("NOT_SELECTED remained unresolved after retry")
    c_venues, c_dists = defaultdict(list), defaultdict(list)
    for v in validated.values():
        c_venues[v["p"]["venue"]].append(v["review"])
        c_dists[str(v["distance"])].append(v["review"])
    def agg(reviews):
        metrics = [r["hit_metrics"] for r in reviews if r["hit_metrics"]["evaluable"]]
        n = len(metrics)
        return {"reviewed": len(reviews), "evaluable": n, "top_pick_wins": sum(m["top_pick_win"] for m in metrics),
                "top_pick_top3": sum(m["top_pick_top3"] for m in metrics),
                "win_rate": round(sum(m["top_pick_win"] for m in metrics)/n,6) if n else None,
                "top3_rate": round(sum(m["top_pick_top3"] for m in metrics)/n,6) if n else None,
                "mean_absolute_top_pick_rank_error": round(sum(m["top_pick_rank_error"] for m in metrics)/n,6) if n else None,
                "small_sample_warning": n < 30}
    global_agg = agg([v["review"] for v in validated.values()])
    summary = {"schema_version": 1, "date": date, "scope": "predictions_with_valid_proof_only",
               "expected_predictions": len(pred_paths), "eligible_predictions": len(eligible_ids),
               "completed_reviews": len(completed), "pending": len(pending), "blocked": len(blocked),
               "skipped_existing": len(skipped), "by_venue": {k: agg(v) for k,v in sorted(c_venues.items())},
               "by_distance": {k: agg(v) for k,v in sorted(c_dists.items())},
               "top_pick_win_rate": global_agg["win_rate"],
               "top_pick_top3_rate": global_agg["top3_rate"],
               "ranking_error_summary": {"top_pick_mean_absolute_rank_error": global_agg["mean_absolute_top_pick_rank_error"],
                                         "evaluable_n": global_agg["evaluable"]},
               "reviewed_races": len(validated), "summary": global_agg,
               "evidence_based_findings": ["Frozen ability rank compared with NAR official result without hindsight adjustment"],
               "uncertainties": ["Small one-day sample; no JRA transfer", "Pace and race incident effects not externally verified"],
               "coverage_gaps": [], "reconciliation": {
                   "eligible_equals_categories": len(eligible_ids) == len(completed)+len(pending)+
                       len([x for x in blocked if x not in [] and x["status"] != "BLOCKED_PROOF"])+len(skipped),
                   "review_ids": sorted(validated), "unresolved_ids": sorted(set(statuses) - set(validated)),
                   "ineligible_proof_ids": sorted(rid for rid,x in statuses.items() if x["status"] == "BLOCKED_PROOF")}}
    analysis_path = ROOT / "analysis" / f"{date}-summary.json"
    write_distinct(analysis_path, summary, mutable=True)
    diagnostics = {"schema_version": 1, "date": date, "prompt": cfg["prompts"]["post_race"],
                   "expected_predictions": len(pred_paths), "completed_or_verified": len(validated),
                   "total_unresolved": len(pred_paths)-len(validated), "races": statuses,
                   "retry_only_race_ids": sorted(set(statuses)-set(validated)),
                   "status": "SUCCESS" if len(validated) == len(pred_paths) and summary["reconciliation"]["eligible_equals_categories"] else "PARTIAL"}
    diag_path = ROOT / "diagnostics" / f"{date}-postrace-run.json"
    write_distinct(diag_path, diagnostics, mutable=True)
    print(json.dumps({"date":date,"completed_or_verified":len(validated),"unresolved":len(pred_paths)-len(validated),
                      "diagnostics":str(diag_path),"status":diagnostics["status"]},ensure_ascii=False))
    return 0 if diagnostics["status"] == "SUCCESS" else 2

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=(dt.datetime.now(JST).date()-dt.timedelta(days=1)).isoformat())
    parser.add_argument("--race-id", default=None)
    args = parser.parse_args()
    try:
        sys.exit(run(args.date,args.race_id))
    except Exception as ex:
        print(f"BLOCKED_IMPLEMENTATION: {type(ex).__name__}: {ex}", file=sys.stderr)
        sys.exit(3)
