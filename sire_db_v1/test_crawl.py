import unittest
from bs4 import BeautifulSoup
from sire_db_v1 import crawl as c

PAGE = """<title>競馬 - クロワデュノール データベース - スポーツナビ</title><div>性齢 牡 4歳 生年月日 2022年3月21日 毛色</div>
<div class="hr-horsePedigree__gen1st hr-horsePedigree__gen1st--sire">キタサンブラック</div>
<div class="hr-horsePedigree__gen1st hr-horsePedigree__gen1st--dam">ライジングクロス</div>
<div class="hr-horsePedigree__genSecond hr-horsePedigree__genSecond--sire">ブラックタイド</div>
<div class="hr-horsePedigree__genSecond hr-horsePedigree__genSecond--dam">シュガーハート</div>
<div class="hr-horsePedigree__genSecond hr-horsePedigree__genSecond--sire">Cape Cross</div>
<div class="hr-horsePedigree__genSecond hr-horsePedigree__genSecond--dam">Woodrising</div>
<table><tr><th>日付</th><th>レース</th><th>着順</th><th>馬番</th><th>騎手 (斤量)</th><th>人気 (オッズ)</th></tr>
<tr><td>2026/11/01</td><td><a href="/keiba/race/index/2605041111">天皇賞</a><span>GI</span><p>東京 芝2000m 17頭</p></td><td>5</td><td>1</td><td>x<p>(58.0)</p></td><td>1<p>(2.3)</p></td></tr>
<tr><td>2024/06/09</td><td><a href="/keiba/race/index/2405030405">新馬</a><p>東京 芝1800m 11頭</p></td><td>1</td><td>6</td><td>x</td><td>2<p>(3.1)</p></td></tr></table>"""


class T(unittest.TestCase):
    def test_parse_horse(self):
        h = c.parse_horse(BeautifulSoup(PAGE, "html.parser"))
        self.assertEqual((h["name"], h["sex"], h["birth"]), ("クロワデュノール", "牡", "2022-03-21"))
        self.assertEqual((h["ped"]["sire"], h["ped"]["dam_sire"]), ("キタサンブラック", "Cape Cross"))
        self.assertEqual(len(h["history"]), 2)
        r = h["history"][0]
        self.assertEqual((r["date"], r["venue"], r["surface"], r["dist"], r["heads"], r["finish"], r["ninki"], r["odds"]),
                         ("2026-11-01", "東京", "芝", 2000, 17, 5, 1, 2.3))

    def test_denma_only_runners(self):
        html = """<table><tr><th>枠番</th><th>馬番</th><th>馬名 性齢/毛色</th></tr>
        <tr><td>1</td><td>1</td><td><a href="/keiba/directory/horse/2022105102/">A</a> 牡4 <a href="/keiba/directory/horse/2012102013/">父</a></td></tr></table>
        <a href="/keiba/directory/horse/1999999999/">other</a>"""
        self.assertEqual(c.parse_denma_horses(BeautifulSoup(html, "html.parser")), ["2022105102"])

    def test_race_code(self):
        codes = dict((d, k) for d, k in c.race_codes(["2026"]) if d == "2026-10-31" and k.endswith("11"))
        self.assertEqual(codes["2026-10-31"][:2], "26")
        self.assertIn("2605041011", [k for d, k in c.race_codes(["2026"])])   # 東京4回10日目 11R


if __name__ == "__main__":
    unittest.main()
