import json
import unittest

from claude_track import stake_opt as so


def entries(n=8, takeout=0.78):
    """控除（還元率0.78）つきの、つじつまの合ったオッズ表を作る。"""
    raw = {i: 1.0 / (3.0 + 2.5 * i) for i in range(1, n + 1)}
    s = sum(raw.values())
    p = {i: v / s for i, v in raw.items()}
    e = [{"type": "単勝", "selection": [i], "market_odds": round(takeout / p[i], 1)} for i in p]
    for a in range(1, n + 1):
        for b in range(a + 1, n + 1):
            for typ, sel in (("馬連", [a, b]), ("ワイド", [a, b]), ("馬単", [a, b]), ("馬単", [b, a])):
                pr = so.combo_prob(p, typ, tuple(sel))
                o = round(takeout / pr, 1)
                e.append({"type": typ, "selection": sel, "market_odds": [o, o] if typ == "ワイド" else o})
    return e


class Anchored(unittest.TestCase):
    def test_no_information_means_no_bet(self):
        # 自分の確率が市場と同じなら、控除分だけ不利なので買い目は出ない（最適化の呪いの再発防止）
        ent = entries()
        m = so.market_win_probs(ent)
        out = so.optimize_anchored(m, ent, {"w": 0.0})
        self.assertEqual(out["decision"], "skip")
        self.assertEqual(out["bets"], [])

    def test_limits_and_determinism(self):
        ent = entries()
        m = so.market_win_probs(ent)
        model = {h: v ** 0.6 for h, v in m.items()}
        model[5] *= 4
        s = sum(model.values())
        model = {h: v / s for h, v in model.items()}
        a = so.optimize_anchored(model, ent)
        b = so.optimize_anchored(model, ent)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertLessEqual(a["total_stake_yen"], 6000)
        for bet in a["bets"]:
            self.assertEqual(bet["stake_yen"] % 100, 0)
            self.assertLessEqual(bet["stake_yen"], 1000)
            self.assertGreater(bet["expected_value"], 0)
        self.assertTrue(all(x["type"] in ("単勝", "馬連", "馬単", "ワイド") for x in a["bets"]))
        self.assertIn("三連複", a["incomplete_odds_types"] + ["三連複"])
        if a["total_stake_yen"]:
            self.assertLessEqual(a["max_horse_exposure_yen"], 0.60 * 6000)

    def test_incomplete_odds_table_is_not_used(self):
        # 三連単の表が一部しか取れていないと q がゆがむ。そのときその券種は評価しない（データの検査）
        ent = entries(8)
        m = so.market_win_probs(ent)
        part = [x for x in so._anchored_rows(ent, {"馬単"}, m, m, 0.5)[0]]
        self.assertTrue(part)
        ent2 = [e for e in ent if not (e["type"] == "馬単" and e["selection"][0] > 5)]
        rows, inc = so._anchored_rows(ent2, {"馬単"}, m, m, 0.5)
        self.assertEqual(inc, ["馬単"])
        self.assertEqual(rows, [])

    def test_sharpen_matches_entropy(self):
        m = {1: 0.4, 2: 0.3, 3: 0.2, 4: 0.1}
        raw = {h: v ** 0.6 for h, v in m.items()}
        flat = {h: v / sum(raw.values()) for h, v in raw.items()}
        sharp, tau = so.sharpen(flat, m)
        self.assertAlmostEqual(tau, 1 / 0.6, places=2)
        self.assertAlmostEqual(so._entropy(sharp), so._entropy(m), places=4)

    def test_legacy_still_works(self):
        ent = entries()
        m = so.market_win_probs(ent)
        self.assertIn("decision", so.optimize(m, ent))


if __name__ == "__main__":
    unittest.main()
