import gzip, unittest
from pathlib import Path
from claude_track import fetch_race_inputs as f

FIX = Path(__file__).parent / "fixtures" / "card_tokyo_20261031_r11.html.gz"


class ParseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.card = f.parse_card(f.decode(gzip.decompress(FIX.read_bytes())))

    def test_header(self):
        c = self.card
        self.assertEqual((c["race_name"], c["date"], c["race_no"]), ("ペルセウスステークス", "2026-10-31", 11))
        self.assertEqual((c["surface"], c["distance_m"], c["start_at"]), ("ダート", 1600, "2026-10-31T15:30:00+09:00"))

    def test_horses(self):
        hs = self.card["horses"]
        self.assertGreaterEqual(len(hs), 12)
        h1 = hs[0]
        self.assertEqual((h1["number"], h1["name"], h1["weight_kg"], h1["body_weight_kg"]), (1, "ハセドン", 55.0, 496))
        self.assertEqual(h1["sire"], "モーリス")
        self.assertTrue(h1["past"] and h1["past"][0]["finish"] == 8 and h1["past"][0]["passing_positions"][:2] == [8, 9])

    def test_price_blind(self):
        import json
        s = json.dumps(self.card, ensure_ascii=False)
        # current odds/popularity must be gone from every horse record outside the past-run excerpts
        for h in self.card["horses"]:
            rec = {k: v for k, v in h.items() if k != "past"}
            self.assertNotIn("番人気", json.dumps(rec, ensure_ascii=False))
        self.assertNotIn("93.1 (14", s)


if __name__ == "__main__":
    unittest.main()
