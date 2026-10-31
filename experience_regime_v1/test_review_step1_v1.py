import unittest
from experience_regime_v1.review_backfill_v1 import aggregate

class TestE012VerifiedStep1Metrics(unittest.TestCase):
    def test_partial_proof_backed_prediction_scores_only_available_horses(self):
        reviews=[{"race_id":"test-race","race_category":"maiden","horses":[
            {"horse_number":1,"regime":"E1","started":True,
             "actual_win":1,"actual_top3":1,"step1_rank":1,
             "predicted_win_probability":0.7,"predicted_top3_probability":0.8},
            {"horse_number":2,"regime":"E1","started":True,
             "actual_win":0,"actual_top3":0},
        ]}]
        group=aggregate(reviews)["regimes"]["E1"]
        self.assertEqual(group["horse_observations"],2)
        self.assertEqual(group["win_prediction_observations"],1)
        self.assertEqual(group["top3_prediction_observations"],1)
        self.assertAlmostEqual(group["win_brier"],0.09)
        self.assertAlmostEqual(group["top3_brier"],0.04)
        self.assertAlmostEqual(group["win_calibration_error"],-0.3)
        self.assertEqual(group["step1_rank_observations"],1)
        self.assertEqual(group["prediction_accuracy_state"],
                         "unavailable_or_partial_in_frozen_research_snapshots")

    def test_no_prediction_never_invents_scores(self):
        reviews=[{"race_id":"test","race_category":"debut","horses":[
            {"horse_number":1,"regime":"E0","started":True,
             "actual_win":1,"actual_top3":1},
        ]}]
        group=aggregate(reviews)["regimes"]["E0"]
        self.assertIsNone(group["win_brier"])
        self.assertIsNone(group["top3_brier"])
        self.assertIsNone(group["step1_mean_rank"])

    def test_non_starter_excluded(self):
        reviews=[{"race_id":"test","race_category":"maiden","horses":[
            {"horse_number":1,"regime":"E1","started":False,
             "actual_win":None,"actual_top3":None,
             "predicted_win_probability":0.4},
        ]}]
        self.assertEqual(aggregate(reviews)["regimes"]["E1"]["horse_observations"],0)

if __name__=="__main__":
    unittest.main()
