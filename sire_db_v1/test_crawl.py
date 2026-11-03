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
<dl><div class="hr-profile__item"><dt>調教師（所属）</dt><dd><a href="/keiba/directory/trainer/01151/">斉藤 崇史</a>(栗東)</dd></div><div class="hr-profile__item"><dt>馬主</dt><dd>有限会社 サンデーレーシング</dd></div></dl>
<table><tr><th>日付</th><th>レース</th><th>着順</th><th>馬番</th><th>騎手 (斤量)</th><th>人気 (オッズ)</th><th>馬体重</th><th>タイム 差</th><th>通過順位 上3F</th></tr>
<tr><td>2026/11/01</td><td><a href="/keiba/race/index/2605041111">天皇賞</a><span class="hr-label hr-label--g1">GI</span><p>東京 芝2000m 17頭</p></td><td>5</td><td>1</td><td><a href="/keiba/directory/jockey/05473/">C.デムーロ</a><p>(58.0)</p></td><td>1<p>(2.3)</p></td><td>512(-2)</td><td>1:57.4<p>(+0.7)</p></td><td>06-06-06<p>34.2</p></td></tr>
<tr><td>2024/06/09</td><td><a href="/keiba/race/index/2405030405">新馬</a><p>東京 芝1800m 11頭</p></td><td>1</td><td>6</td><td>x</td><td>2<p>(3.1)</p></td><td>500(0)</td><td>1:50.0</td><td>03-03<p>35.0</p></td></tr></table>"""


class T(unittest.TestCase):
    def test_parse_horse(self):
        h = c.parse_horse(BeautifulSoup(PAGE, "html.parser"))
        self.assertEqual((h["name"], h["sex"], h["birth"]), ("クロワデュノール", "牡", "2022-03-21"))
        self.assertEqual((h["ped"]["sire"], h["ped"]["dam_sire"]), ("キタサンブラック", "Cape Cross"))
        self.assertEqual(len(h["history"]), 2)
        r = h["history"][0]
        self.assertEqual((r["jockey"], r["jockey_id"], r["carried"], r["body_weight"], r["body_weight_diff"], r["time"], r["margin"], r["passing"], r["last3f"], r["grade"]),
                         ("C.デムーロ", "05473", 58.0, 512, -2, "1:57.4", "+0.7", "06-06-06", 34.2, "GI"))
        self.assertEqual(h["profile"]["調教師（所属）"][:5], "斉藤 崇史"); self.assertEqual(h["profile"]["調教師（所属）_id"], "01151")
        self.assertEqual((h["history"][1]["time"], h["history"][1]["margin"], h["history"][1]["last3f"]), ("1:50.0", None, 35.0))
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
