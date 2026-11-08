#!/usr/bin/env python3
"""Read-only audit: every finalized JRA result must have a review, including no-bet races.

Never settles or alters a prediction; never synthesizes a review from postrace information.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone, date
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JST = timezone(timedelta(hours=9))


def audit(root: Path, today: date) -> tuple[list[str], list[str]]:
    db = json.loads((root / "docs/data/races.json").read_text(encoding="utf-8"))
    checked, errors = [], []
    for r in db.get("races", []):
        if r.get("scope") != "jra-main" or r.get("date", "") >= today.isoformat():
            continue
        rid = r.get("id", "")
        source = root / "e2e_validation/results" / f"{rid}.json"
        if not source.is_file():
            continue
        result = json.loads(source.read_text(encoding="utf-8"))
        if result.get("race_id") != rid or len(result.get("finish_order") or []) < 3 or not result.get("official_result_at"):
            errors.append(f"{rid}: invalid official result file")
            continue
        checked.append(rid)
        if r.get("status") != "reviewed":
            errors.append(f"{rid}: official result exists but review status is {r.get('status')!r}")
            continue
        if not isinstance(r.get("review"), str) or not r["review"].strip():
            errors.append(f"{rid}: review text missing")
        if not r.get("result") or r["result"].get("finish_order") != result["finish_order"]:
            errors.append(f"{rid}: published finish order missing or different")
        if not isinstance(r.get("performance"), dict):
            errors.append(f"{rid}: performance missing")
            continue
        if r.get("purchase_decision") == "pass":
            perf = r["performance"]
            if (r.get("total_stake_yen") != 0 or r.get("final_bets") != [] or
                r.get("settlements") != [] or perf.get("stake_yen") != 0 or
                perf.get("payout_yen") != 0 or perf.get("profit_yen") != 0 or
                perf.get("roi_pct") is not None or perf.get("ticket_hit") is not None):
                errors.append(f"{rid}: no-bet settlement/ROI must be zero with undefined ROI and hit")
        elif not isinstance(r.get("settlements"), list):
            errors.append(f"{rid}: settlement list missing")
    return checked, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--today", default=datetime.now(JST).date().isoformat())
    args = parser.parse_args()
    checked, errors = audit(args.root, date.fromisoformat(args.today))
    print(json.dumps({"checked": len(checked), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
