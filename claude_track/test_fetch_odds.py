import unittest
from bs4 import BeautifulSoup
from claude_track.fetch_odds import race_code, parse_odds, odds_value


class T(unittest.TestCase):
    def test_code(self):
        self.assertEqual(race_code("pw01dde1005202604101120261031/A5"), "2605041011")
        self.assertEqual(race_code("pw01dde0105202604041120261011/CE"), "2605040411")

    def test_value(self):
        self.assertEqual(odds_value("12.3"), 12.3)
        self.assertEqual(odds_value("1,044.7"), 1044.7)
        self.assertEqual(odds_value("1.5 - 2.3"), [1.5, 2.3])
        self.assertIsNone(odds_value("取消"))

    def test_parse(self):
        html = ("<table><tr><th>枠</th><th>馬番</th><th>馬名</th><th>単勝</th></tr>"
                "<tr><td>1</td><td>1</td><td>A</td><td>3.4</td></tr><tr><td>2</td><td>2</td><td>B</td><td>取消</td></tr></table>")
        self.assertEqual(parse_odds("tfw", BeautifulSoup(html, "html.parser")), {("単勝", (1,)): 3.4})
        h2 = ("<table><tr><th>1</th></tr><tr><td>2</td><td>10.5</td></tr><tr><td>3</td><td>20.0</td></tr></table>")
        self.assertEqual(parse_odds("ur", BeautifulSoup(h2, "html.parser")), {("馬連", (1, 2)): 10.5, ("馬連", (1, 3)): 20.0})

    def test_parse_st(self):
        h = "<table><tr><th>組</th><th>オッズ</th></tr><tr><td>3 - 1 - 2</td><td>55.5</td></tr><tr><td>3-2-1</td><td>取消</td></tr></table>"
        self.assertEqual(parse_odds("st", BeautifulSoup(h, "html.parser")), {("三連単", (3, 1, 2)): 55.5})


if __name__ == "__main__":
    unittest.main()
