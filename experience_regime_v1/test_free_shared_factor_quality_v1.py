import copy
import json
import unittest
from pathlib import Path
from experience_regime_v1.free_shared_factor_quality_v1 import (
    factor, undercard_factor_quality, formal_factor_quality, compare_quality)
from experience_regime_v1.free_factor_comparison_v1 import audit_and_compare, render

ROOT = Path(__file__).resolve().parents[1]
WEEK = ROOT / "experience_regime_v1"
WID = "2026-10-31"
DAY = "2026-11-01"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestFreeSharedFactorQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = WEEK / "research_step1_candidates" / WID
        evidence = WEEK / "factor_evidence" / WID
        cls.b = load(base / "2026-11-01-kyoto-01.json")
        cls.e = load(evidence / "2026-11-01-kyoto-01.json")
        cls.f = load(WEEK / "step1_frozen" / WID / "2026-11-01-kyoto-11.json")

    def test_unverified_numerical_grades_disallowed(self):
        with self.assertRaisesRegex(ValueError, "numerical_grade_without_validated_model_forbidden"):
            factor(8, "identity_only", grade="A")
        with self.assertRaisesRegex(ValueError, "numerical_grade_without_validated_model_forbidden"):
            factor(7, "observed", grade="B")

    def test_field_comparisons_only_frozen_attributes(self):
        rows = undercard_factor_quality(self.b, self.e)
        self.assertEqual(rows["race_id"],self.b["race_id"])
        self.assertEqual(len(rows["runners"]),len(self.b["runners"]))
        self.assertTrue(rows["no_poststart_retroactive_forecast"])
        by_number = {h["horse_number"]:h for h in rows["runners"]}
        before = {h["horse_number"]:h for h in self.b["runners"]}
        for n,h in by_number.items():
            self.assertEqual(h["baseline_mark_frozen"],before[n]["mark"])
            self.assertEqual(h["baseline_rank_frozen"],before[n]["step1_rank"])
            self.assertEqual(h["baseline_win_probability_frozen"],before[n]["predicted_win_probability"])
            self.assertEqual(h["factors"][6]["status"],"unavailable")
            self.assertEqual(h["factors"][5]["status"],"identity_only")
            self.assertEqual(h["factors"][7]["status"],"identity_only")
            self.assertIsNone(h["new_probability"])
            self.assertIsNone(h["new_rank"])
            self.assertEqual(len(h["factors"]),9)

    def test_new_horse_without_history_is_not_forced_bad_grade(self):
        data=undercard_factor_quality(self.b,self.e)
        debut = next(h for h in data["runners"] if h["regime"]=="E0")
        self.assertIsNone(debut["factors"][8]["grade"])
        self.assertIsNone(debut["new_probability"])

    def test_formal_6_7_8_are_all_placeholder_grades(self):
        summary=formal_factor_quality(self.f)
        self.assertEqual(len(summary["runners"]),13)
        for h in summary["runners"]:
            self.assertEqual([p["grade"] for p in h["fallback_factors"]],["B","B-","B"])
            self.assertEqual([p["status"] for p in h["fallback_factors"]],["unavailable"]*3)

    def test_mismatched_horse_fails(self):
        bad=copy.deepcopy(self.e)
        bad["runners"][0]["horse_name"]="不正な別馬"
        with self.assertRaisesRegex(ValueError,"immutable_horse_identity_mismatch"):
            undercard_factor_quality(self.b,bad)

    def test_odds_or_results_must_never_be_used_as_source(self):
        bad=copy.deepcopy(self.b)
        bad["no_odds_or_results_accessed"]=False
        with self.assertRaisesRegex(ValueError,"price_blind_frozen_input_unverified"):
            undercard_factor_quality(bad,self.e)

    def test_actual_frozen_12_race_stage_comparison_without_outcomes(self):
        report=audit_and_compare(WID,DAY)
        self.assertEqual(report["formal_races"],2)
        self.assertEqual(report["formal_horses"],30)
        self.assertEqual(report["undercard_races"],10)
        self.assertEqual(report["undercard_horses"],125)
        self.assertEqual(report["frozen_predictions_untouched"],125)
        self.assertEqual(report["coverage_by_factor"]["7"]["observed_or_identity"],0)
        self.assertEqual(report["coverage_by_factor"]["6"]["observed_or_identity"],125)
        self.assertEqual(report["coverage_by_factor"]["8"]["observed_or_identity"],125)
        self.assertEqual(report["coverage_by_factor"]["2"]["observed_or_identity"],86)
        self.assertEqual(report["coverage_by_factor"]["3"]["observed_or_identity"],58)
        self.assertEqual(report["coverage_by_factor"]["5"]["observed_or_identity"],35)
        self.assertIsNone(report["winner_accuracy_challenger"])
        self.assertIsNone(report["roi_challenger"])
        self.assertFalse(report["production_effect"])
        self.assertFalse(report["outcome_data_read"])
        page=render(report)
        self.assertIn("無料データの9項目監査",page)
        self.assertNotIn("100%改善",page)


if __name__=="__main__":
    unittest.main()
