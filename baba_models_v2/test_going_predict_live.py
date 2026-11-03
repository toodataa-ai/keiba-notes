import unittest, warnings
from datetime import date
warnings.filterwarnings('ignore')
import going_predict_live as g

class T(unittest.TestCase):
    def test_replay_probabilities(self):
        out = g.run_replay('fukushima', date(2025, 7, 5))
        self.assertTrue(len(out) >= 20)
        for s, no, pred, act, pchg in out:
            self.assertIn(pred, g.GOING_JA); self.assertTrue(0 <= pchg <= 1)
        turf = [r for r in out if r[0] == 'turf']
        self.assertEqual(turf[-1][2], '良')      # turf recovers by the late races on that day (and in the model)
    def test_probs_sum_to_one(self):
        labels, obs = g.load_context(); df = g.training_frame(before=date(2025, 7, 5)); models = g.fit_models(df)
        import stage_b_dataset as sd
        W = sd.load_weather('weather'); sched = g.typical_schedule(labels, 'fukushima', date(2025, 7, 5))
        rows = g.build_rows('fukushima', date(2025, 7, 5), 'turf', {'morning': 1, 'morning_other': 1, 'moist0': 14.0}, labels, obs, W, sched)
        P = g.predict_probs(models, rows, 'turf')
        self.assertAlmostEqual(float(P.sum(1).min()), 1.0, places=6)
if __name__ == '__main__': unittest.main()
