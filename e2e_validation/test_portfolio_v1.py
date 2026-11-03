import json
import tempfile
import unittest
from pathlib import Path

from e2e_validation import portfolio_eval_v1 as pe
from e2e_validation.challengers import ticket_div_v1 as td


class SettleTests(unittest.TestCase):
    PAY = {"馬単": {"5-10": 4760}, "三連複": {"5-8-10": 19450}, "ワイド": {"5-10": 300}}

    def test_keys_and_payout(self):
        self.assertEqual(pe.bet_key("三連複", [10, 8, 5]), "5-8-10")
        self.assertEqual(pe.bet_key("馬単", [10, 5]), "10-5")
        s = pe.settle([{"type": "三連複", "selection": [10, 8, 5], "stake_yen": 200},
                       {"type": "馬単", "selection": [10, 5], "stake_yen": 100}], self.PAY)
        self.assertEqual((s["stake_yen"], s["payout_yen"], s["hit"]), (300, 38900, 1))

    def test_summary_excludes_biggest_gap_race(self):
        def row(i, fp, cp):
            mk = lambda p: {"stake_yen": 1000, "payout_yen": p, "net_yen": p - 1000, "hit": int(p > 0), "max_exposure": .5}
            return {"race_id": f"r{i}", "formal": mk(fp), "challenger": mk(cp)}
        out = pe.summarize([row(1, 0, 0), row(2, 0, 20000), row(3, 500, 0)])
        self.assertEqual(out["biggest_gap_race"], "r2")
        self.assertLess(out["roi_delta_without_biggest_gap_race"], 0)  # without the lucky race it is worse
        self.assertGreater(out["roi_delta"], 0)


class DiversifyTests(unittest.TestCase):
    def test_plackett_luce_probabilities_sum_to_one(self):
        p = {1: .5, 2: .3, 3: .2}
        self.assertAlmostEqual(td.combo_prob(p, "三連複", (1, 2, 3)), 1.0)
        self.assertAlmostEqual(td.combo_prob(p, "馬連", (1, 2)), td.order_prob(p, (1, 2)) + td.order_prob(p, (2, 1)))

    def test_small_sets_are_not_applicable(self):
        sealed = {"source_race_id": "x", "source_prediction_path": "p",
                  "formal_bets": [{"type": "単勝", "selection": [1], "stake_yen": 100, "market_odds": 3.0}]}
        out = td.predict(sealed)
        self.assertFalse(out["applicable"])
        self.assertFalse(out["changed"])

    def test_cap_and_budget_respected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "e2e_validation/quote-evidence/x").mkdir(parents=True)
            (root / "pred.json").write_text(json.dumps({"step1_ranking": [
                {"horse_number": i, "win_probability": w} for i, w in enumerate([.4, .2, .15, .1, .08, .07], 1)]}))
            def odds(kind, typ, entries):
                (root / f"e2e_validation/quote-evidence/x/{kind}.json").write_text(json.dumps({"entries": [
                    {"type": typ, "selection": s, "market_odds": o} for s, o in entries]}))
            odds("tfw", "単勝", [([i], 1 / w * 1.3) for i, w in enumerate([.4, .2, .15, .1, .08, .07], 1)])
            odds("ur", "馬連", [([1, i], 20.0) for i in range(2, 7)] + [([2, 3], 30.0), ([4, 5], 90.0)])
            old = td.ROOT
            td.ROOT = root
            try:
                formal = [{"type": "馬連", "selection": [1, i], "stake_yen": 100, "market_odds": 20.0} for i in range(2, 7)] * 2
                out = td.predict({"source_race_id": "x", "source_prediction_path": "pred.json", "formal_bets": formal})
            finally:
                td.ROOT = old
            self.assertTrue(out["applicable"])
            self.assertLessEqual(sum(b["stake_yen"] for b in out["bets"]), 1000)
            self.assertLessEqual(out["challenger_max_exposure"], 0.60 + 1e-9)
            self.assertEqual(len({(b["type"], tuple(b["selection"])) for b in out["bets"]}), len(out["bets"]))


class RegistryPinTests(unittest.TestCase):
    def test_exp003_pinned(self):
        from e2e_validation.experiment_runner_v1 import git_blob_sha, ROOT, read, REGISTRY
        exp = next(e for e in read(REGISTRY)["experiments"] if e["id"] == "EXP-003")
        self.assertEqual(exp["kind"], "portfolio")
        self.assertEqual(git_blob_sha(ROOT / exp["code"]["path"]), exp["code"]["git_blob_sha"])


if __name__ == "__main__":
    unittest.main()
