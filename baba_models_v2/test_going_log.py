import unittest
import going_log as gl


def row(d, track, pw, wet, actual, morning, pm, base, p_nf=None, changed=False):
    return {'date': d, 'track': track, 'surface': 'turf', 'morning_going': morning, 'p_wet_main': pw, 'wet': wet,
            'actual_main': actual, 'changed_before_main': changed, 'probs_main': pm,
            'probs_morning_persists': base, 'probs_no_forecast_main': p_nf}


class T(unittest.TestCase):
    def test_score_counts_and_loglosses(self):
        good = {'良': 0.1, '稍重': 0.8, '重': 0.05, '不良': 0.05}; base = {'良': 0.9, '稍重': 0.08, '重': 0.01, '不良': 0.01}
        rows = [row('2026-11-14', 'fukushima', 0.8, True, 1, '良', good, base, changed=True),
                row('2026-11-14', 'hanshin', 0.1, False, 0, '良', base, base)]
        S = gl.score(rows)
        self.assertEqual(S['with_outcome'], 2); self.assertEqual(S['changed_before_main'], 1); self.assertEqual(S['wet_days'], 1)
        self.assertLess(S['changed_cases']['logloss_final'], S['changed_cases']['logloss_baseline'])
        self.assertEqual(S['forecast_check']['n'], 2)
        self.assertGreaterEqual(S['forecast_check']['brier_forecast'], 0)

    def test_roundtrip(self):
        import os, tempfile
        p = os.path.join(tempfile.mkdtemp(), 'x', 'log.jsonl')
        r = {'date': '2026-11-14', 'track': 'tokyo', 'surface': 'dirt'}
        gl.write_log([r], p); self.assertEqual(gl.read_log(p), [r])


if __name__ == '__main__':
    unittest.main()
