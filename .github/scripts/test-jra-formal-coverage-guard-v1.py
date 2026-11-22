#!/usr/bin/env python3
"""Regression tests for read-only day-level JRA formal publication guard."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("jra-formal-coverage-guard-v1.py")
spec = importlib.util.spec_from_file_location("jra_formal_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

DAY = "2026-11-23"
RID = DAY + "-tokyo-sports-hai-2yo-stakes"
PROOF = "a" * 40


class FormalCoverageGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cal = {"meetings": [{
            "dates": [DAY],
            "expected_main_race_ids": [RID]
        }]}
        self.race = {
            "id": RID, "date": DAY, "scope": "jra-main",
            "status": "predicted", "purchase_decision": "buy",
            "total_stake_yen": 100,
            "final_bets": [{"type": "単勝", "stake_yen": 100, "selection": [2]}],
            "final_bets_fixed_at": DAY + "T14:00:00+09:00",
            "proof_commit": PROOF,
            "e2e_prediction": "e2e_validation/predictions/" + RID + "/sealed.json",
            "report": "reports/" + RID + ".html",
            "pdf": "pdfs/" + RID + ".pdf",
        }
        self.pred = {
            "source_race_id": RID,
            "proof_commit": PROOF,
            "final_bets_fixed_at": DAY + "T14:00:00+09:00",
            "race_context": {"date": DAY, "start_at": DAY + "T15:40:00+09:00"}
        }
        self.write()

    def write(self):
        self.write_json("docs/data/jra_postrace_meetings_v1.json", self.cal)
        self.write_json("docs/data/races.json", {"races": [self.race]})
        self.write_json(self.race["e2e_prediction"], self.pred)
        self.write_bytes("docs/" + self.race["report"], b"<!doctype html><html></html>")
        self.write_bytes("docs/" + self.race["pdf"], b"%PDF-1.7 testing")

    def write_json(self, name, data):
        self.write_bytes(name, (json.dumps(data) + "\n").encode("utf-8"))

    def write_bytes(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    @patch.object(gate.subprocess, "run")
    def test_verified_before_post_has_complete_coverage(self, run):
        result = gate.validate_day(self.root, DAY)
        self.assertTrue(result["strictly_complete"], result["errors"])
        self.assertEqual(result["verified"], 1)

    @patch.object(gate.subprocess, "run")
    def test_missing_canonical_is_not_counted_as_pass(self, run):
        self.write_json("docs/data/races.json", {"races": []})
        result = gate.validate_day(self.root, DAY)
        self.assertFalse(result["strictly_complete"])
        self.assertEqual(result["races"][0]["status"], "MISSING")

    @patch.object(gate.subprocess, "run")
    def test_post_start_bets_are_rejected(self, run):
        self.race["final_bets_fixed_at"] = DAY + "T16:00:00+09:00"
        self.write()
        result = gate.validate_day(self.root, DAY)
        self.assertFalse(result["strictly_complete"])
        self.assertIn("not frozen before race start", " ".join(result["errors"]))

    @patch.object(gate.subprocess, "run")
    def test_legitimate_zero_bet_pass_is_valid(self, run):
        self.race["purchase_decision"] = "pass"
        self.race["final_bets"] = []
        self.race["total_stake_yen"] = 0
        self.write()
        result = gate.validate_day(self.root, DAY)
        self.assertTrue(result["strictly_complete"], result["errors"])

    @patch.object(gate.subprocess, "run")
    def test_missing_bets_not_silently_converted_to_pass(self, run):
        self.race["final_bets"] = []
        self.write()
        self.assertFalse(gate.validate_day(self.root, DAY)["strictly_complete"])

    def test_no_calendar_entry_must_not_pass(self):
        self.assertFalse(gate.validate_day(self.root, "2026-11-24")["strictly_complete"])


if __name__ == "__main__":
    unittest.main()
