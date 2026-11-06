import unittest

from bs4 import BeautifulSoup

from sire_db_v1 import race_crawl as rc

HTML = """<html><head><title>テストレース 結果</title><script>var x=1;</script></head><body>
<h1>テストレース</h1><p>天気：晴 馬場：良</p>
<table><tr><th>着順</th><th>馬名</th><th>騎手</th></tr>
<tr><td>1</td><td><a href="/keiba/directory/horse/2020100001/">アルファ</a></td><td><a href="/keiba/directory/jockey/01234/">甲 乙</a></td></tr></table>
<table><tr><td>ラップ</td><td>12.3 - 11.0</td></tr></table></body></html>"""


class T(unittest.TestCase):
    def test_dump_keeps_everything(self):
        d = rc.dump_page(BeautifulSoup(HTML, "html.parser"), "http://x/y")
        self.assertEqual(len(d["tables"]), 2)
        self.assertEqual(d["tables"][0][0], ["着順", "馬名", "騎手"])
        self.assertEqual(d["tables"][0][1][1], "アルファ⟨/keiba/directory/horse/2020100001/⟩")
        self.assertEqual(d["tables"][0][1][2], "甲 乙⟨/keiba/directory/jockey/01234/⟩")
        self.assertIn("馬場： 良", d["text"].replace("：良", "： 良"))
        self.assertNotIn("var x", d["text"])
        self.assertEqual(d["tables"][1][0], ["ラップ", "12.3 - 11.0"])
        self.assertEqual(d["title"], "テストレース 結果")

    def test_codes_newest_first(self):
        c = rc.race_codes(["2026", "2025"])
        self.assertTrue(c and c[0][0] >= c[-1][0])
        self.assertEqual(len(c[0][1]), 10)


if __name__ == "__main__":
    unittest.main()
