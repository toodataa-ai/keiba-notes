#!/usr/bin/env python3
"""Read-only JRA formal race-day coverage gate; never predicts or backfills."""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
JST = timezone(timedelta(hours=9))
HEX40 = re.compile(r"^[0-9a-f]{40}$")
PUBLIC_BASE = "https://toodataa-ai.github.io/keiba-notes/"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dt(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return result


def validate_day(root: Path, day: str, check_public=False):
    errors = []
    cal = load(root / "docs/data/jra_postrace_meetings_v1.json")
    registry = load(root / "docs/data/races.json")
    expected = []
    for meeting in cal["meetings"]:
        if day in meeting["dates"]:
            expected += [rid for rid in meeting["expected_main_race_ids"]
                         if rid.startswith(day + "-")]
    expected = list(dict.fromkeys(expected))
    if not expected:
        return {"date": day, "expected": [], "races": [],
                "errors": ["no calendar race coverage; check official JRA program before claiming completion"]}

    by_id = {r["id"]: r for r in registry["races"] if r.get("scope") == "jra-main"}
    results = []
    for rid in expected:
        err = []
        race = by_id.get(rid)
        if race is None:
            results.append({"race_id": rid, "status": "MISSING", "errors": ["no canonical prereace registry entry"]})
            continue
        if race.get("date") != day or race.get("status") not in ("predicted", "reviewed"):
            err.append("wrong date or not a sealed predicted/reviewed record")
        bets = race.get("final_bets")
        if not isinstance(bets, list):
            err.append("final_bets missing")
        decision = race.get("purchase_decision")
        if decision == "pass":
            if bets != [] or race.get("total_stake_yen") != 0:
                err.append("pass must have zero bets and zero stake")
        elif decision == "buy":
            if not bets or not (0 < race.get("total_stake_yen", 0) <= 6000):
                err.append("buy must have priced bets with a <=6000 yen total")
        else:
            err.append("purchase_decision must be buy or pass; NEVER treat missing as pass")
        proof = race.get("proof_commit")
        if not isinstance(proof, str) or not HEX40.fullmatch(proof):
            err.append("missing prestart proof_commit")
        else:
            try:
                subprocess.run(["git", "cat-file", "-e", proof + "^{commit}"],
                               cwd=root, check=True, capture_output=True, timeout=10)
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                err.append("proof_commit is not readable in Git checkout")

        paths = [race.get("e2e_prediction"), "docs/" + str(race.get("report") or ""),
                 "docs/" + str(race.get("pdf") or "")]
        prefixes = ["e2e_validation/predictions/" + rid + "/", "docs/reports/", "docs/pdfs/"]
        for p, prefix in zip(paths, prefixes):
            if not isinstance(p, str) or not p.startswith(prefix) or ".." in Path(p).parts or not (root / p).is_file():
                err.append("missing/invalid immutable artifact: " + str(p))
        pred = None
        if paths[0] and (root / paths[0]).is_file():
            try:
                pred = load(root / paths[0])
                post = dt(pred["race_context"]["start_at"])
                if pred.get("race_context", {}).get("date") != day:
                    err.append("prediction race date mismatch")
                if pred.get("proof_commit") != proof:
                    err.append("prediction proof_commit mismatch")
                if dt(race.get("final_bets_fixed_at")) >= post:
                    err.append("final_bets were not frozen before race start")
                if dt(pred.get("final_bets_fixed_at")) >= post:
                    err.append("sealed prediction is not prestart")
                if pred.get("source_race_id", pred.get("race_id")) != rid:
                    err.append("sealed prediction race ID mismatch")
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
                err.append("invalid sealed prediction timestamp/schema: " + str(e))
        if (root / paths[2]).is_file() and not (root / paths[2]).read_bytes().startswith(b"%PDF-"):
            err.append("published PDF does not have PDF signature")
        if (root / paths[1]).is_file():
            html = (root / paths[1]).read_text(encoding="utf-8")
            if "<html" not in html.lower():
                err.append("report HTML invalid")

        if check_public:
            for p in ["docs/data/races.json", paths[1], paths[2]]:
                if not p or not (root / p).is_file():
                    continue
                try:
                    request = Request(PUBLIC_BASE + p.removeprefix("docs/"),
                                      headers={"Cache-Control": "no-cache"})
                    with urlopen(request, timeout=15) as response:
                        remote = response.read()
                    if remote != (root / p).read_bytes():
                        err.append("public HTTP bytes differ from GitHub checkout: " + p)
                except Exception as exc:
                    err.append("public HTTP not verified: " + p + ": " + type(exc).__name__)
        results.append({"race_id": rid, "status": "OK" if not err else "BLOCKED", "errors": err})

    failed = [r for r in results if r["status"] != "OK"]
    return {"date": day, "expected": expected, "races": results,
            "verified": len(results) - len(failed),
            "errors": errors + [r["race_id"] + ": " + "; ".join(r["errors"]) for r in failed],
            "strictly_complete": not failed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(JST).date().isoformat())
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--check-public", action="store_true")
    opts = parser.parse_args()
    try:
        date.fromisoformat(opts.date)
        outcome = validate_day(opts.root, opts.date, opts.check_public)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"strictly_complete": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome.get("strictly_complete") else 1


if __name__ == "__main__":
    sys.exit(main())
