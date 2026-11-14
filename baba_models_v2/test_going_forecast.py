import glob, gzip, json, unittest, warnings
from datetime import date
warnings.filterwarnings('ignore')
import numpy as np
import going_forecast as gf


class T(unittest.TestCase):
    def test_p_wet_monotone_and_bounds(self):
        low = {'06-12': 0.1, '12-18': 0.1}; high = {'06-12': 0.8, '12-18': 0.9}
        a, b = gf.p_wet_after_morning(low, 15.5), gf.p_wet_after_morning(high, 15.5)
        self.assertTrue(0 < a < b < 1)
        self.assertEqual(gf.p_wet_after_morning({'06-12': 0.0, '12-18': 0.0}, 15.5), 0.0)
        # a race before the morning window gets nothing from the afternoon block
        self.assertAlmostEqual(gf.p_wet_after_morning({'06-12': 0.5, '12-18': 0.9}, 8.0), 0.0)
        self.assertIsNone(gf.p_wet_after_morning(None, 15.5))
        # later race => more time => probability does not decrease
        self.assertLessEqual(gf.p_wet_after_morning(high, 10.0), gf.p_wet_after_morning(high, 15.5))

    def test_parse_archived_forecast(self):
        files = sorted(glob.glob('forecast_archive/2026/11/*_0611.json.gz'))
        self.assertTrue(files)
        rec = json.load(gzip.open(files[-1], 'rt', encoding='utf-8'))
        day = date.fromisoformat(files[-1].split('/')[-1][:8][:4] + '-' + files[-1].split('/')[-1][4:6] + '-' + files[-1].split('/')[-1][6:8])
        n = 0
        for code, v in rec['forecasts'].items():
            for tr in v['tracks']:
                pops = gf.parse_pops(v['data'], tr, day)
                if pops:
                    n += 1
                    for k in ('06-12', '12-18'):
                        if k in pops: self.assertTrue(0 <= pops[k] <= 1)
        self.assertGreaterEqual(n, 8)    # all 10 racecourses are covered on a normal day


if __name__ == '__main__':
    unittest.main()
