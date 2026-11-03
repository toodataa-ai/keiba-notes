import unittest
from bs4 import BeautifulSoup
from claude_track.fetch_results import parse_result, yen

HTML = """<table><tr><th></th><th>馬番</th><th>払戻金</th><th>人気</th></tr>
<tr><th>単勝</th><td>17</td><td>1,080円</td><td>4</td></tr>
<tr><th>複勝</th><td>17</td><td>320円</td><td>3</td></tr><tr><td>10</td><td>880円</td><td>8</td></tr><tr><td>3</td><td>370円</td><td>4</td></tr>
<tr><th>馬連</th><td>10-17</td><td>12,970円</td><td>24</td></tr></table>
<table><tr><th></th><th>馬番</th><th>払戻金</th><th>人気</th></tr>
<tr><th>ワイド</th><td>3-17</td><td>1,290円</td><td>10</td></tr><tr><td>10-17</td><td>3,330円</td><td>23</td></tr>
<tr><th>馬単</th><td>17-10</td><td>25,490円</td><td>46</td></tr><tr><th>3連複</th><td>3-10-17</td><td>42,010円</td><td>84</td></tr>
<tr><th>3連単</th><td>17-10-3</td><td>297,820円</td><td>455</td></tr></table>
<table><tr><th>着順</th><th>枠番</th><th>馬番</th><th>馬名 性齢/馬体重/B</th><th>タイム</th></tr>
<tr><td>1</td><td>8</td><td>17</td><td>ダノンデサイル 牡5/516(-4)</td><td>1:56.7</td></tr>
<tr><td>2</td><td>5</td><td>10</td><td>ネブラディスク 牡4/458(+2)</td><td>1:57.1</td></tr>
<tr><td>3</td><td>2</td><td>3</td><td>レガレイラ 牝5/494(+4)</td><td>1:57.2</td></tr></table>
<p>天気： 晴 馬場： 良 3歳以上</p>"""


class T(unittest.TestCase):
    def test_parse(self):
        p = parse_result(BeautifulSoup(HTML, "html.parser"))
        self.assertEqual(p["finish_order"], [17, 10, 3])
        self.assertEqual(p["payouts"]["単勝"], {"17": 1080})
        self.assertEqual(p["payouts"]["複勝"], {"17": 320, "10": 880, "3": 370})
        self.assertEqual(p["payouts"]["ワイド"], {"3-17": 1290, "10-17": 3330})
        self.assertEqual(p["payouts"]["三連複"], {"3-10-17": 42010})
        self.assertEqual(p["payouts"]["三連単"], {"17-10-3": 297820})
        self.assertEqual(p["going"], "良")
        self.assertEqual(p["finish_top3"][0]["horse"], "ダノンデサイル")

    def test_incomplete(self):
        with self.assertRaises(ValueError):
            parse_result(BeautifulSoup("<table><tr><th>着順</th><th>枠番</th><th>馬番</th><th>x</th></tr></table>", "html.parser"))

    def test_yen(self):
        self.assertEqual(yen("1,080円"), 1080); self.assertIsNone(yen("-"))


if __name__ == "__main__":
    unittest.main()
