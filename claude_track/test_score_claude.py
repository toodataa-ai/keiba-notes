import json, tempfile, unittest
from pathlib import Path
from claude_track import score_claude as sc

RESULT = {"race_id": "r1", "scheduled_start_at": "2026-11-08T15:00:00+09:00", "finish_order": [5, 10, 8, 7],
          "official_payouts_yen_per_100": {"単勝": {"5": 1130}, "馬連": {"5-10": 1960}, "馬単": {"5-10": 4760}, "三連複": {"5-8-10": 19450}}}


def pred(**kw):
    p = {"schema_version": 1, "predictor": "claude", "race_id": "r1", "generated_at": "2026-11-08T08:00:00+09:00",
         "odds_seen_before_step1": False,
         "horses": [{"no": 5, "mark": "◎", "win_prob": 0.5}, {"no": 10, "mark": "○", "win_prob": 0.3}, {"no": 8, "mark": "▲", "win_prob": 0.1}, {"no": 7, "win_prob": 0.1}],
         "bets": [{"type": "三連複", "selection": [10, 8, 5], "stake_yen": 100}, {"type": "馬単", "selection": [10, 5], "stake_yen": 100}]}
    p.update(kw); return p


class T(unittest.TestCase):
    def test_keys_unordered_vs_ordered(self):
        self.assertEqual(sc.bet_key("三連複", [10, 8, 5]), "5-8-10")
        self.assertEqual(sc.bet_key("馬単", [10, 5]), "10-5")

    def test_scoring(self):
        e = sc.score_prediction(pred(), RESULT)
        self.assertTrue(e["prospective"]); self.assertTrue(e["honmei_win"]); self.assertEqual(e["marked_in_top3"], 3)
        self.assertEqual(e["payout_yen"], 19450)      # 三連複 hit, 馬単 10-5 missed (paid on 5-10)
        self.assertAlmostEqual(e["log_loss"], -__import__("math").log(0.5))

    def test_after_start_is_not_prospective(self):
        e = sc.score_prediction(pred(generated_at="2026-11-08T16:00:00+09:00"), RESULT)
        self.assertFalse(e["prospective"])
        self.assertEqual(sc.aggregate([e])["races"], 0)

    def test_odds_seen_is_not_prospective(self):
        self.assertFalse(sc.score_prediction(pred(odds_seen_before_step1=True), RESULT)["prospective"])

    def test_run_counts_first_file_only(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / "p/r1").mkdir(parents=True); (d / "res").mkdir()
            (d / "res/r1.json").write_text(json.dumps(RESULT), encoding="utf-8")
            (d / "p/r1/a.json").write_text(json.dumps(pred()), encoding="utf-8")
            (d / "p/r1/b.json").write_text(json.dumps(pred(bets=[])), encoding="utf-8")
            r = sc.run(d / "p", d / "res")
            self.assertEqual(r["summary"]["races"], 1); self.assertEqual(r["summary"]["payout_yen"], 19450)


if __name__ == "__main__":
    unittest.main()


class PublicTest(unittest.TestCase):
    def test_public_build(self):
        from claude_track import build_public as bp
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); (d / "p/r1").mkdir(parents=True); (d / "res").mkdir()
            (d / "p/r1/a.json").write_text(json.dumps(pred(race_name="テストS", venue="東京", date="2026-11-08")), encoding="utf-8")
            r = bp.build(d / "p", d / "res")
            self.assertEqual(r["races"][0]["race_name"], "テストS"); self.assertIsNone(r["races"][0]["result"])
            self.assertEqual([m["mark"] for m in r["races"][0]["marks"]], ["◎", "○", "▲"])
            (d / "res/r1.json").write_text(json.dumps(RESULT), encoding="utf-8")
            r = bp.build(d / "p", d / "res")
            self.assertEqual(r["races"][0]["result"]["payout_yen"], 19450)
