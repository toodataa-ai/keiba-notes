#!/usr/bin/env python3
"""Fail-closed local racing Shadow publisher. Does not generate predictions."""
import datetime as dt
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path("local_racing_shadow_v1")
DOCS = pathlib.Path("docs/data")
PUBLIC = DOCS / "local-racing-shadow"
MANIFEST = DOCS / "local_racing_shadow_public.json"
STATUS = DOCS / "local_racing_shadow_status.json"
JST = dt.timezone(dt.timedelta(hours=9))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_if_changed(path, data):
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def parse_time(value):
    d = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Timestamp must include timezone: " + value)
    return d


def proof(path, start):
    cmd = ["git", "log", "--follow", "--format=%H|%cI", "--", str(path)]
    rows = subprocess.check_output(cmd, text=True).splitlines()
    if not rows:
        raise ValueError(f"No committed prediction proof: {path}")
    # Oldest commit containing the prediction; ensure commit predates the race.
    sha, when = rows[-1].split("|", 1)
    if parse_time(when) >= start:
        raise ValueError(f"Prediction commit after start: {path}")
    if len(rows) > 1:
        raise ValueError(f"Immutable prediction modified after creation: {path}")
    return sha


def main():
    cfg = read(ROOT / "config.json")
    enabled = {k: v["label"] for k, v in cfg["venues"].items() if v.get("enabled")}
    labels = set(enabled.values())
    previous = read(MANIFEST)
    entries = []
    changed = False
    for path in sorted((ROOT / "predictions").glob("*/*.json")):
        p = read(path)
        required = ["race_id", "date", "venue", "race_no", "race_name", "distance", "scheduled_start_at", "generated_at", "information_cutoff_at", "model_version", "runners", "sources"]
        missing = [k for k in required if k not in p]
        if missing:
            raise ValueError(f"{path}: missing {missing}")
        if p["venue"] not in labels:
            raise ValueError(f"{path}: disabled or unknown venue")
        start = parse_time(p["scheduled_start_at"])
        cutoff = parse_time(p["information_cutoff_at"])
        created = parse_time(p["generated_at"])
        if not created <= cutoff < start:
            raise ValueError(f"{path}: invalid pre-race cutoff")
        if path.parent.name != p["date"] or path.stem != str(p["race_id"]):
            raise ValueError(f"{path}: inconsistent identity")
        if any(k in p for k in ("finish_order", "official_result", "payouts")):
            raise ValueError(f"{path}: result leakage")
        sha = proof(path, start)
        relative = path.relative_to(ROOT)
        mirror = PUBLIC / relative
        if mirror.exists() and mirror.read_bytes() != path.read_bytes():
            raise ValueError(f"Immutable public prediction differs: {mirror}")
        changed |= write_if_changed(mirror, p)
        result = ROOT / "results" / p["date"] / path.name
        review = ROOT / "reviews" / p["date"] / path.name
        if review.exists() and not result.exists():
            raise ValueError(f"{review}: missing result")
        for kind, source in (("results", result), ("reviews", review)):
            if source.exists():
                changed |= write_if_changed(PUBLIC / kind / p["date"] / path.name, read(source))
        entries.append({
            "race_id": p["race_id"], "date": p["date"], "venue": p["venue"],
            "race_no": p["race_no"], "race_name": p["race_name"],
            "distance": p["distance"], "class": p.get("class"),
            "scheduled_start_at": p["scheduled_start_at"],
            "status": "reviewed" if review.exists() else "predicted",
            "model_version": p["model_version"],
            "information_cutoff_at": p["information_cutoff_at"],
            "proof_commit": sha,
            "prediction_path": "data/local-racing-shadow/" + relative.as_posix(),
            "result_path": "data/local-racing-shadow/results/" + p["date"] + "/" + path.name if result.exists() else None,
            "review_path": "data/local-racing-shadow/reviews/" + p["date"] + "/" + path.name if review.exists() else None,
            "preview": {"top_pick": p.get("top_pick"), "pace": p.get("pace"), "going": p.get("going")},
        })
    ids = [str(x["race_id"]) for x in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate race_id")
    analyses = []
    for path in sorted((ROOT / "analysis").glob("*-summary.json")):
        data = read(path)
        dest = PUBLIC / "analysis" / path.name
        changed |= write_if_changed(dest, data)
        analyses.append({"date": path.name[:10], "scope": data.get("scope", "all"),
                         "reviewed_races": data.get("reviewed_races", 0),
                         "summary": data.get("summary"), "findings": data.get("findings", []),
                         "path": "data/local-racing-shadow/analysis/" + path.name})
    # Preserve timestamp if nothing changed, so scheduled runs do not cause noise.
    desired = dict(previous)
    desired.update({"races": entries, "daily_analysis": analyses})
    before = dict(previous)
    before.pop("updated_at", None)
    compare = dict(desired)
    compare.pop("updated_at", None)
    if before != compare or changed:
        desired["updated_at"] = dt.datetime.now(JST).isoformat(timespec="seconds")
        write_if_changed(MANIFEST, desired)
    if STATUS.exists():
        status = read(STATUS)
        status.setdefault("totals", {})
        status["totals"]["races_observed"] = len(entries)
        status["totals"]["pre_race_snapshots"] = len(entries)
        status["totals"]["results_joined"] = sum(x["status"] == "reviewed" for x in entries)
        for venue in status.get("venues", []):
            if isinstance(venue, dict):
                label = venue.get("label", venue.get("venue"))
                venue["races_observed"] = sum(x["venue"] == label for x in entries)
        write_if_changed(STATUS, status)
    print(f"Shadow publish audit passed: {len(entries)} predictions, {len(analyses)} analyses")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"BLOCKER: {e}", file=sys.stderr)
        sys.exit(1)
