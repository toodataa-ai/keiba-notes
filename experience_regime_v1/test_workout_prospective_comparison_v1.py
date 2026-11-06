"""Synthetic *unit-test fixtures only*, never persisted as historical racing model outputs."""
from __future__ import annotations
import copy
import unittest
from datetime import datetime
from experience_regime_v1.test_workout_prestart_proof_v1 import CAPTURE,NOW,approved
from experience_regime_v1.workout_prestart_proof_v1 import build_commitment
from experience_regime_v1.workout_prospective_comparison_v1 import compare

RID=CAPTURE["race_id"]
START=CAPTURE["start_at"]
LEGACY={
    "race_id":RID,"start_at":START,"frozen_at":"2026-11-15T13:00:00+09:00",
    "odds_used_in_STEP1":False,"no_results_or_outcomes_used":True,
    "runners":[
        {"horse_number":1,"regime":"E0","win_probability":0.25,"top3_probability":0.66},
        {"horse_number":2,"regime":"E1","win_probability":0.3,"top3_probability":0.64},
        {"horse_number":3,"regime":"E2","win_probability":0.45,"top3_probability":0.7}
    ]
}
CHALLENGER=copy.deepcopy(LEGACY)
CHALLENGER["runners"][0]["win_probability"]=0.5
CHALLENGER["runners"][1]["win_probability"]=0.2
CHALLENGER["runners"][2]["win_probability"]=0.3
RESULT={"race_id":RID,"official_result_final":True,
        "published_at":"2026-11-15T16:20:00+09:00",
        "finish_order":[1,2,3]}


class TestProspectiveComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=build_commitment(CAPTURE,now=NOW,policy=approved())

    def call(self,legacy=None,challenger=None,result=None,captured=None,proof=None):
        return compare(proof=proof or self.proof,captured=captured or CAPTURE,
                       legacy=legacy,challenger=challenger,result=result)

    def test_no_fictional_prediction_or_backfill_from_source_only(self):
        report=self.call()
        self.assertEqual(report["status"],"awaiting_both_independently_frozen_prestart_predictions")
        self.assertIsNone(report["prediction_accuracy"])
        self.assertIsNone(report["roi_new"])

    def test_both_valid_but_results_not_yet_verified(self):
        report=self.call(LEGACY,CHALLENGER)
        self.assertEqual(report["status"],"awaiting_official_verified_results")
        self.assertIsNone(report["prediction_accuracy"])

    def test_frozen_probability_scoring_is_descriptive_only(self):
        report=self.call(LEGACY,CHALLENGER,RESULT)
        self.assertEqual(report["status"],"prospective_brier_computed_descriptive_not_approval")
        self.assertLess(report["challenger_minus_legacy_brier_win"],0)
        self.assertIsNone(report["roi_new"])
        self.assertFalse(report["formal_promotion_allowed"])
        self.assertEqual(report["legacy"]["by_regime"]["E0"]["horses"],1)
        self.assertEqual(report["challenger"]["by_regime"]["E1"]["horses"],1)

    def test_unfrozen_or_after_start_bets_and_results_not_accepted(self):
        for field,val in [
            ("frozen_at","2026-11-15T15:41:00+09:00"),
            ("odds_used_in_STEP1",True),
            ("no_results_or_outcomes_used",False)
        ]:
            copyold=copy.deepcopy(LEGACY);copyold[field]=val
            with self.assertRaises(ValueError,msg=field):
                self.call(copyold,CHALLENGER,RESULT)

    def test_mismatched_field_or_invalid_win_mass_rejected(self):
        x=copy.deepcopy(CHALLENGER)
        x["runners"][0]["horse_number"]=99
        with self.assertRaisesRegex(ValueError,"same_field_and_regime_required"):
            self.call(LEGACY,x,RESULT)
        x=copy.deepcopy(CHALLENGER)
        x["runners"][0]["win_probability"]=0.99
        with self.assertRaises(ValueError):
            self.call(LEGACY,x,RESULT)

    def test_official_outcomes_need_final_source(self):
        bad=copy.deepcopy(RESULT);bad["official_result_final"]=False
        with self.assertRaisesRegex(ValueError,"official_result_finalization_required"):
            self.call(LEGACY,CHALLENGER,bad)

    def test_modified_workout_artifact_digest_detected(self):
        x=copy.deepcopy(CAPTURE)
        x["observations"][0]["workouts"][0]["split_seconds"]["1F"]=10.4
        with self.assertRaisesRegex(ValueError,"workout_artifact_sha_mismatch"):
            self.call(captured=x)

    def test_prestart_observation_with_afterstart_article_timestamp_rejected(self):
        x=copy.deepcopy(CAPTURE)
        x["source"]["fetched_at"]="2026-11-15T16:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"poststart_evidence"):
            self.call(captured=x)


if __name__=="__main__":
    unittest.main()
