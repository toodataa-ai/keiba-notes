#!/usr/bin/env python3
"""Read-only integrity auditor for local NAR POST-RACE outputs and publication."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path("local_racing_shadow_v1")
DOCS = Path("docs/data")
PUBLIC = DOCS / "local-racing-shadow"

def load(p):
    return json.loads(p.read_text(encoding="utf-8"))

def assert_equal(a, b, desc):
    if a != b:
        raise AssertionError(f"{desc}: {a!r} != {b!r}")

def audit(date, published):
    predictions = sorted((ROOT / "predictions" / date).glob("*.json"))
    assert predictions, "No predictions"
    public = load(DOCS / "local_racing_shadow_public.json")
    manifest = {x["race_id"]:x for x in public["races"] if x["date"] == date}
    assert_equal(len(manifest), len(predictions), "Manifest prediction count")
    summary_path = ROOT / "analysis" / f"{date}-summary.json"
    diag_path = ROOT / "diagnostics" / f"{date}-postrace-run.json"
    assert summary_path.exists() and diag_path.exists(), "Missing summary/diagnostics"
    summary = load(summary_path)
    diagnostics = load(diag_path)
    verified = {}
    for pred_path in predictions:
        rid = pred_path.stem
        p = load(pred_path)
        assert_equal(p["race_id"], rid, "Prediction identity")
        assert rid in manifest, f"Missing manifest entry {rid}"
        sha = hashlib.sha256(pred_path.read_bytes()).hexdigest()
        mirror_pred = PUBLIC / "predictions" / date / pred_path.name
        assert_equal(mirror_pred.read_bytes(), pred_path.read_bytes(), f"{rid} mirrored prediction changed")
        logs = subprocess.check_output(["git", "log", "--no-renames", "--format=%H",
                                        "--", str(pred_path)], text=True).splitlines()
        assert len(logs)==1, f"{rid}: prediction history changed"
        assert_equal(logs[0], manifest[rid].get("proof_commit"), "Proof manifest")
        res_path = ROOT / "results" / date / pred_path.name
        rev_path = ROOT / "reviews" / date / pred_path.name
        if not rev_path.exists():
            assert manifest[rid]["status"] != "reviewed", f"{rid}: false published review status"
            assert manifest[rid].get("review_path") is None, f"{rid}: ghost review URL"
            assert manifest[rid].get("result_path") is None or res_path.exists(), f"{rid}: ghost result URL"
            continue
        assert res_path.exists(), f"{rid}: review without result"
        result, review = load(res_path), load(rev_path)
        assert_equal(result["race_id"], rid, "Result race id")
        assert_equal(result["status"], "OFFICIAL_CONFIRMED", "Official status")
        assert_equal(result["prediction_sha256"], sha, "Result prediction digest")
        assert_equal(review["prediction_sha256"], sha, "Review prediction digest")
        assert_equal(result["proof_commit"], logs[0], "Result proof commit")
        assert_equal(review["proof_commit"], logs[0], "Review proof commit")
        assert_equal(review["result_path"], str(res_path), "Review result path")
        assert_equal(result["prediction_path"], str(pred_path), "Result prediction path")
        assert result["official_source_url"].startswith("https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?"), f"{rid}: unsupported official URL"
        pred_horses = {h["horse_no"]:h["horse_name"] for h in p["runners"]}
        official_horses = {h["horse_no"]:h["horse_name"] for h in result["finish_order"]}
        assert_equal(set(pred_horses), set(official_horses), "Horse number JOIN")
        assert_equal(len(result["finish_order"]),len(official_horses),"Official duplicate horse numbers")
        for no,name in pred_horses.items():
            assert_equal(name,official_horses[no],"Horse name JOIN")
        by_no = {h["horse_no"]: h for h in result["finish_order"]}
        top_no = p["top_pick"]["horse_no"]
        assert_equal(review["top_pick"], p["top_pick"], "Frozen top pick")
        assert_equal(review["actual_top_pick_finish"], by_no[top_no]["finish_position"], "Top-pick finish")
        assert_equal(len(review["rank_comparison"]),len(p["ability_order"]),"Ranking compare count")
        for a, b in zip(p["ability_order"], review["rank_comparison"]):
            assert_equal(a["horse_no"], b["horse_no"], "Ability horse number")
            assert_equal(a["ability_rank"], b["predicted_rank"], "Ability rank")
            assert_equal(by_no[a["horse_no"]]["finish_position"], b["actual_finish"], "Official rank")
        assert_equal(manifest[rid]["status"],"reviewed","Published status")
        assert_equal(manifest[rid]["result_path"],"data/local-racing-shadow/results/"+date+"/"+pred_path.name,"Result public path")
        assert_equal(manifest[rid]["review_path"],"data/local-racing-shadow/reviews/"+date+"/"+pred_path.name,"Review public path")
        if published:
            for x in (res_path, rev_path):
                mirror = PUBLIC / x.relative_to(ROOT)
                assert_equal(mirror.read_bytes(),x.read_bytes(),f"Published mirror mismatch: {rid}")
        verified[rid] = review
    assert_equal(summary["expected_predictions"],len(predictions),"Expected prediction count")
    assert_equal(summary["reviewed_races"],len(verified),"Summary reviewed count")
    assert_equal(set(summary["reconciliation"]["review_ids"]),set(verified),"Summary identity set")
    assert_equal(len(verified),sum(x["status"]=="reviewed" for x in manifest.values()),"Manifest reviewed count")
    remaining = len(predictions)-len(verified)
    assert_equal(diagnostics["total_unresolved"],remaining,"Diagnostics unresolved")
    if remaining == 0:
        assert_equal(diagnostics["status"],"SUCCESS","Diagnostics completion")
    if published:
        analysis_mirror = PUBLIC / "analysis" / summary_path.name
        assert_equal(analysis_mirror.read_bytes(),summary_path.read_bytes(),"Published analysis mirror")
        status=load(DOCS / "local_racing_shadow_status.json")
        assert status["totals"]["results_joined"] >= len(verified), "Status joined count below audited reviews"
    changed = subprocess.check_output(["git","status","--porcelain","--","local_racing_shadow_v1/predictions"],text=True)
    assert not changed.strip(), "Prediction files modified/created/deleted"
    print(json.dumps({"date":date,"predictions":len(predictions),"reviewed":len(verified),
                      "unresolved":remaining,"published":published,"status":"PASS" if remaining == 0 else "PARTIAL"},
                     ensure_ascii=False))
    return 0 if remaining==0 else 2

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",default="2026-10-08")
    ap.add_argument("--published",action="store_true")
    args=ap.parse_args()
    try: sys.exit(audit(args.date,args.published))
    except Exception as ex:
        print(f"POSTRACE_AUDIT_FAIL: {type(ex).__name__}: {ex}",file=sys.stderr)
        sys.exit(3)
