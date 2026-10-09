#!/usr/bin/env python3
"""Strict manual POST-RACE request dispatcher. No POST-RACE/JRA write operation here."""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path("local_racing_shadow_v1")
REQUEST = ROOT / "postrace_request.json"
JST = dt.timezone(dt.timedelta(hours=9))
VENUES = "oi|kawasaki|funabashi|urawa|sonoda|nagoya"

def validate(date, race_id=None, today=None):
    if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("Date must be YYYY-MM-DD in JST")
    day = dt.date.fromisoformat(date)
    if day > (today or dt.datetime.now(JST).date()):
        raise ValueError("Future race date is not eligible for POST-RACE")
    if race_id:
        if not isinstance(race_id, str) or not re.fullmatch(
            r"\d{8}-(?:" + VENUES + r")-\d{2}", race_id
        ) or not race_id.startswith(date.replace("-", "") + "-"):
            raise ValueError("Race ID does not belong to selected local-racing date")
    return date, race_id or ""

def payload(record, today=None):
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("Unsupported request version")
    if record.get("scope") != "POST-RACE" or record.get("production_effect") is not False:
        raise ValueError("POST-RACE isolation guard failed")
    if type(record.get("request_seq")) is not int or record["request_seq"] < 1:
        raise ValueError("request_seq must be a positive integer")
    return validate(record.get("date"), record.get("race_id"), today)

def main():
    event = os.environ.get("POSTRACE_EVENT")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if cfg.get("production_effect") is not False or cfg.get("prompts", {}).get("post_race") != "local_racing_shadow_v1/shadow_review_prompt_v0_2.txt":
        raise ValueError("Production or governing-prompt guard failed")
    if event == "push":
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if sha != os.environ.get("GITHUB_SHA"):
            raise ValueError("Workflow checkout does not match triggering push")
        changed = subprocess.check_output(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], text=True
        ).splitlines()
        if changed != [REQUEST.as_posix()]:
            raise ValueError(f"Only a standalone request commit is allowed: {changed}")
        record = json.loads(REQUEST.read_text(encoding="utf-8"))
        date, race_id = payload(record)
        try:
            older = subprocess.check_output(
                ["git", "show", "HEAD^:" + REQUEST.as_posix()],
                stderr=subprocess.DEVNULL, text=True
            )
        except subprocess.CalledProcessError:
            older = None
        if older:
            previous = json.loads(older)
            if record["request_seq"] <= previous["request_seq"]:
                raise ValueError("request_seq must increase on every retry")
    elif event == "workflow_dispatch":
        date = os.environ.get("POSTRACE_INPUT_DATE") or (
            dt.datetime.now(JST).date() - dt.timedelta(days=1)
        ).isoformat()
        date, race_id = validate(date, os.environ.get("POSTRACE_INPUT_RACE_ID"))
    else:
        raise ValueError("Unsupported workflow event")

    directory = ROOT / "predictions" / date
    races = sorted(directory.glob("*.json"))
    if not races:
        raise ValueError("BLOCKED_NO_PREDICTIONS: " + date)
    if race_id and not (directory / (race_id + ".json")).is_file():
        raise ValueError("Requested race prediction not found: " + race_id)
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        raise ValueError("Missing GitHub output file")
    with open(out, "a", encoding="utf-8") as handle:
        handle.write("date=" + date + "\n")
        handle.write("race_id=" + race_id + "\n")
    print(json.dumps({"date": date, "race_id": race_id or None,
                      "saved_predictions": len(races), "production_effect": False},
                     ensure_ascii=False))

def self_test():
    cases = [
        ("2026-10-09", "20261009-oi-03", True),
        ("2026-10-08", "20261008-sonoda-12", True),
        ("2026-10-09", "20261008-oi-03", False),
        ("2026-10-09", "../../JRA", False),
        ("2026-10-09", "20261009-tokyo-03", False),
        ("2026-10-40", None, False),
    ]
    today = dt.date(2026, 10, 12)
    for day, race, ok in cases:
        try:
            validate(day, race, today)
            accepted = True
        except ValueError:
            accepted = False
        if accepted != ok:
            raise AssertionError(f"Regression case failed: {day}, {race}")
    valid = {"schema_version": 1, "scope": "POST-RACE", "date": "2026-10-09",
             "race_id": None, "request_seq": 1, "production_effect": False}
    assert payload(valid, today) == ("2026-10-09", "")
    for field, bad in [("production_effect", True), ("request_seq", 0),
                       ("request_seq", True), ("scope", "PRE-RACE")]:
        changed = dict(valid, **{field: bad})
        try:
            payload(changed, today)
        except ValueError:
            continue
        raise AssertionError("Unsafe request accepted")
    print("PASS: 10 POST-RACE request selector/isolation regression checks")

if __name__ == "__main__":
    try:
        if "--self-test" in sys.argv:
            self_test()
        else:
            main()
    except Exception as exc:
        print(f"BLOCKED_REQUEST: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(3)
