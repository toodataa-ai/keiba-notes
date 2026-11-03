import json, tempfile, unittest
from pathlib import Path
from bs4 import BeautifulSoup
from claude_track import wakakoma as w

DENMA = """<table><tr><th>枠番</th><th>馬番</th><th>馬名 性齢/毛色</th><th>騎手名 斤量</th><th>人気(オッズ)</th></tr>
<tr><td>1</td><td>1</td><td><a href="/keiba/directory/horse/2024107186/">インサイドエッジ</a> 牝2/青鹿毛</td><td>ルメール</td><td>1( 2.1 )</td></tr>
<tr><td>2</td><td>2</td><td><a href="/keiba/directory/horse/2024100001/">シュネーバレン</a> 牝2/青鹿毛</td><td>木幡</td><td>8( 74.8 )</td></tr></table>"""
HORSE = """<table><tr><th>日付</th><th>レース</th><th>着順</th></tr>
<tr><td>2026/11/01</td><td>未勝利</td><td>1</td></tr><tr><td>2026/08/16</td><td>未勝利</td><td>3</td></tr><tr><td>2026/06/20</td><td>新馬</td><td>2</td></tr></table>"""


class T(unittest.TestCase):
    def test_denma(self):
        d = w.parse_denma(BeautifulSoup(DENMA, "html.parser"))
        self.assertEqual(d["horses"][0]["horse_path"], "/keiba/directory/horse/2024107186/")
        self.assertEqual((d["horses"][1]["ninki"], d["horses"][1]["odds"]), (8, 74.8))
        w.implied(d["horses"]); self.assertAlmostEqual(sum(h["p"] for h in d["horses"]), 1.0, places=5)

    def test_history_and_prior(self):
        h = w.parse_horse_history(BeautifulSoup(HORSE, "html.parser"))
        self.assertEqual(len(h), 3)
        self.assertEqual(w.prior_starts(h, "2026-11-01"), 2)       # the race itself is not counted
        self.assertEqual(w.prior_starts(h, "2026-06-20"), 0)       # debut
        self.assertEqual([w.category(x) for x in (0, 1, 3, 4, 9)], ["E0", "E1", "E1", "E2", "E2"])

    def test_aggregate(self):
        with tempfile.TemporaryDirectory() as t:
            r = Path(t); (r / "2026-11-01").mkdir()
            (r / "2026-11-01" / "x.json").write_text(json.dumps({"race_id": "x", "horses": [
                {"p": 0.5, "prior_starts": 0, "win": True}, {"p": 0.5, "prior_starts": 5, "win": False}]}))
            a = w.aggregate(r)
            self.assertEqual(a["categories"]["E0"]["actual_wins"], 1); self.assertEqual(a["categories"]["E2"]["horses"], 1)
            self.assertFalse(a["categories"]["E0"]["confirmable"])


if __name__ == "__main__":
    unittest.main()
