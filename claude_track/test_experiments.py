import json, math, tempfile, unittest
from pathlib import Path
from claude_track import experiments as ex

RESULT = {"race_id": "r1", "scheduled_start_at": "2026-11-08T15:00:00+09:00", "finish_order": [5, 10, 8, 7]}


def card(front_numbers, career=None):
    hs = []
    for n in range(1, 9):
        pos = 1 if n in front_numbers else 8
        hs.append({"number": n, "past": [{"passing_positions": [pos, pos], "field_size": 8}] * 3,
                   "starts_before_race": (career or {}).get(n)})
    return {"horses": hs}


class T(unittest.TestCase):
    def test_overlay_sums_to_one_and_boosts_fronts_in_slow_pace(self):
        probs = {n: 1 / 8 for n in range(1, 9)}
        out = ex.overlay(card({1})["horses"], probs)          # 1 leader -> slow pace -> front boosted
        self.assertAlmostEqual(sum(out.values()), 1.0)
        self.assertGreater(out[1], out[2])

    def test_first_distance_group(self):
        c = {"age_condition": "2歳", "distance_m": 1600}
        past = lambda *ds: [{"distance_m": d} for d in ds]
        g = lambda n, ps, cc=c: ex.first_distance_group(cc, {"starts_before_race": n, "past": ps})
        self.assertEqual(g(2, past(1400, 1400)), "extension")
        self.assertEqual(g(2, past(1800, 1800)), "shorten")
        self.assertEqual(g(2, past(1400, 1600)), "known")
        self.assertEqual(g(0, []), "debut")
        self.assertIsNone(g(6, past(1400, 1400)))                       # 出走歴が全部は分からない
        self.assertIsNone(g(2, past(1400, 1400), {"age_condition": "3歳以上", "distance_m": 1600}))   # 2歳戦だけ

    def test_regime(self):
        self.assertEqual([ex.regime(x) for x in (None, 0, 1, 3, 4)], [None, "E0", "E1", "E1", "E2"])

    def test_run(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / "p/r1").mkdir(parents=True); (d / "res").mkdir(); (d / "in").mkdir()
            (d / "res/r1.json").write_text(json.dumps(RESULT), encoding="utf-8")
            (d / "in/r1.json").write_text(json.dumps(card({5}, {5: 0, 10: 2, 8: 6})), encoding="utf-8")
            step1 = {"schema_version": 1, "predictor": "claude", "stage": "step1", "race_id": "r1", "generated_at": "2026-11-08T08:00:00+09:00",
                     "odds_seen_before_step1": False, "input_file": "in/r1.json",
                     "horses": [{"no": n, "win_prob": 0.125} for n in range(1, 9)]}
            (d / "p/r1/step1-a.json").write_text(json.dumps(step1), encoding="utf-8")
            r = ex.run(d / "p", d / "res", root=d)
            self.assertEqual(r["pace"]["pairs"], 1)
            self.assertTrue(r["experience"]["career_data_available"])
            self.assertEqual(r["experience"]["regimes"]["E0"]["horses"], 1)
            self.assertEqual(r["experience"]["regimes"]["E0"]["actual_wins"], 1)   # horse 5 won
            self.assertEqual(r["pace"]["state"], "collecting")
if __name__ == "__main__": unittest.main()


class TestGoingAndPortfolio(unittest.TestCase):
    def test_going_overlay(self):
        from claude_track import experiments as ex
        card = {"surface": "ダート", "horses": [
            {"number": 1, "past": [{"surface": "ダート", "going": "重", "finish": 1, "field_size": 10},
                                   {"surface": "ダート", "going": "良", "finish": 8, "field_size": 10}]},
            {"number": 2, "past": []}]}
        probs, adj = ex.going_overlay(card, {1: 0.5, 2: 0.5}, "重")
        self.assertEqual(adj, 1); self.assertGreater(probs[1], probs[2]); self.assertAlmostEqual(sum(probs.values()), 1.0)
        self.assertIsNone(ex.going_overlay(card, {1: 0.5, 2: 0.5}, None))

    def test_mechanical_set_cap(self):
        from claude_track import experiments as ex
        odds = {("単勝", (1,)): 2.5, ("単勝", (2,)): 3.0, ("馬連", (1, 2)): 6.0}
        kept = ex.mechanical_set({1: 0.6, 2: 0.4}, odds, 300)
        self.assertTrue(all(b["stake_yen"] == 100 for b in kept))
        self.assertLessEqual(sum(b["stake_yen"] for b in kept), 300)
