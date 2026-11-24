import math, unittest
from sim_v2 import step1_factors as S


class T(unittest.TestCase):
    def test_kick_rank_and_mult(self):
        l3 = {"A": [33.0, 34.0, 35.0, 36.0, 37.0], "B": [33.5, 34.5, 35.5, 36.5, 37.5]}
        hist = [{"date": "2026-10-01", "code": "A", "finish": 2, "last3f": 33.0, "venue": "東京"},
                {"date": "2026-10-20", "code": "B", "finish": 5, "last3f": 37.5, "venue": "東京"},
                {"date": "2026-12-01", "code": "A", "finish": 1, "last3f": 33.0}]   # 当日以降は使わない
        k = S.kick_factor(hist, "2026-11-28", l3)
        self.assertEqual([u["rank"] for u in k["recent"]], [5, 1])      # 新しい順
        self.assertAlmostEqual(k["k2"], ((1 - 0.8) + (1 - 0.0)) / 3, places=3)
        self.assertEqual(S.kick_factor([], "2026-11-28", l3)["mult"], 1.0)

    def test_ties_share_rank(self):
        k = S.kick_factor([{"date": "2026-10-01", "code": "A", "finish": 3, "last3f": 34.0}], "2026-11-28", {"A": [33.0, 34.0, 34.0, 35.0, 36.0]})
        self.assertEqual(k["recent"][0]["rank"], 2)

    def test_dist_apt_sign_and_cap(self):
        hist = [{"date": "2026-01-%02d" % i, "code": str(i), "finish": 1, "dist": 1600} for i in range(1, 9)] + [{"date": "2026-02-01", "code": "x", "finish": 9, "dist": 2400}]
        f = S.dist_factor(hist, "2026-11-28", 1600)
        self.assertGreater(f["apt"], 0); self.assertLessEqual(f["mult"], round(math.exp(0.7 * 0.15), 3) + 1e-9)
        self.assertEqual(S.dist_factor(hist, "2026-11-28", 3000)["apt"], 0.0)

    def test_trainer_shrink_and_cap(self):
        f = S.trainer_factor({"t": [100, 100]}, [20000, 100000], "t")
        self.assertAlmostEqual(f["mult"], round(math.exp(S.COEF["T1"]["coef_per_unit"] * S.CAP_SD * S.COEF["T1"]["sd"]), 3))
        self.assertEqual(S.trainer_factor({}, [20000, 100000], "zz")["t1"], 0.0)


if __name__ == "__main__":
    unittest.main()
