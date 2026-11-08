#!/usr/bin/env python3
"""Regression tests for JRA no-bet review coverage."""
import importlib.util
import json
from datetime import date
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("jra-review-coverage-v1.py")
spec = importlib.util.spec_from_file_location("jra_review_coverage_v1", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ReviewCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "docs/data").mkdir(parents=True)
        (self.root / "e2e_validation/results").mkdir(parents=True)
        self.race = {
            "id": "2026-11-07-pass", "date": "2026-11-07",
            "scope": "jra-main", "status": "predicted",
            "purchase_decision": "pass", "total_stake_yen": 0, "final_bets": []
        }
        self.result = {"race_id": self.race["id"], "finish_order": [12, 6, 11],
                       "official_result_at": "2026-11-07T19:00:00+09:00"}
        self.write()

    def write(self):
        (self.root / "docs/data/races.json").write_text(json.dumps({"races": [self.race]}), encoding="utf-8")
        (self.root / "e2e_validation/results" / (self.race["id"] + ".json")).write_text(
            json.dumps(self.result), encoding="utf-8")

    def test_unreviewed_pass_is_detected(self):
        checked, errors = mod.audit(self.root, date(2026, 11, 8))
        self.assertEqual(checked, [self.race["id"]])
        self.assertTrue(any("review status" in x for x in errors))

    def test_reviewed_zero_bet_has_no_roi(self):
        self.race.update({
            "status": "reviewed", "review": "公式結果から印を検証。購入は見送り。",
            "result": {"finish_order": [12, 6, 11]}, "settlements": [],
            "performance": {"stake_yen": 0, "payout_yen": 0, "profit_yen": 0,
                            "roi_pct": None, "ticket_hit": None}
        })
        self.write()
        checked, errors = mod.audit(self.root, date(2026, 11, 8))
        self.assertEqual(len(checked), 1)
        self.assertEqual(errors, [])
        self.race["performance"]["roi_pct"] = 0
        self.write()
        self.assertTrue(any("no-bet settlement" in x for x in mod.audit(self.root, date(2026, 11, 8))[1]))

    def test_no_premature_same_day_review_requirement(self):
        self.assertEqual(mod.audit(self.root, date(2026, 11, 7)), ([], []))


if __name__ == "__main__":
    unittest.main()
