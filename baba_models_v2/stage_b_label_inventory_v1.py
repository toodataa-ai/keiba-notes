"""Inventory existing JRA official result labels without inventing post times or surfaces.

The resulting CSV is an evidence worklist, NOT a validated Stage B dataset.
Only a reviewed, source-verified, race-specific surface/post-time can make a
row eligible for replay. No in-place edits to existing prediction history.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from stage_b_tokyo_kyoto_v1 import CLASSES, REQUIRED_LABEL_FIELDS, official_jra

VENUES = {"東京": "tokyo", "京都": "kyoto"}


def local_verified(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo("Asia/Tokyo")).replace(tzinfo=None)
        return dt.isoformat(timespec="minutes")
    except ValueError:
        return ""


def make_worklist(races: list[dict]) -> tuple[list[dict], dict]:
    out = []
    reject = Counter()
    for race in races:
        track = VENUES.get(race.get("venue"))
        if track is None:
            continue
        result = race.get("result") or {}
        label = result.get("going")
        url = result.get("official_url") or ""
        if label not in CLASSES:
            reject["no_official_four_class_label"] += 1
            continue
        if not official_jra(url):
            reject["missing_approved_JRA_result_URL"] += 1
            continue
        verified = local_verified(result.get("verified_at"))
        # Do not guess from the race name, venue, or nominal main-race slot.
        out.append({
            "race_id": race.get("id", ""),
            "track": track, "surface": "",
            "race_date": race.get("date", ""), "post_time_jst": "",
            "official_condition": label, "official_result_url": url,
            "verified_at_jst": verified,
        })
    out.sort(key=lambda x: (x["race_date"], x["race_id"]))
    audit = {
        "schema_version": 1, "status": "source_inventory_not_stage_b_validation",
        "source": "docs/data/races.json historical reviewed races only",
        "candidate_rows": len(out),
        "by_track": dict(sorted(Counter(x["track"] for x in out).items())),
        "verified_timestamp_present": sum(bool(x["verified_at_jst"]) for x in out),
        "surface_and_official_post_time_unverified": len(out),
        "excluded_source_rows": dict(sorted(reject.items())),
        "replay_ready_rows": 0,
        "note": "Surface and actual post time must be confirmed independently from official JRA race record, never inferred or auto-filled.",
    }
    return out, audit


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--races", type=Path, default=Path("docs/data/races.json"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    args = p.parse_args()
    obj = json.loads(args.races.read_text(encoding="utf-8"))
    rows, audit = make_worklist(obj["races"])
    for path in (args.output, args.audit):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_LABEL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
