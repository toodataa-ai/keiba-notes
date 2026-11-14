import gzip, os, unittest
from jra_going_now import parse_going_page
class T(unittest.TestCase):
    def test_tokyo_20261101(self):
        h = gzip.decompress(open(os.path.join(os.path.dirname(__file__), "fixtures", "jra_baba_index_20261101.html.gz"), "rb").read()).decode()
        r = parse_going_page(h)
        self.assertEqual((r["venue"], r["kai"], r["nichi"], r["date"]), ("東京", 4, 11, "2026-11-01"))
        self.assertEqual((r["turf_going"], r["dirt_going"], r["weather"]), ("良", "稍重", "曇"))
        self.assertEqual((r["moist_turf_goal"], r["moist_turf_4c"], r["moist_dirt_goal"], r["moist_dirt_4c"]), (13.8, 13.4, 4.3, 4.3))
        self.assertEqual(r["course"], "B")
        self.assertIn("正午現在", r["as_of"])
    def test_preday_page_reports_race_day(self):
        # 2026-11-14 09:11 JST: the page still said "第3回福島競馬第3日前日 （2026年11月13日）" (not yet flipped).
        h = gzip.decompress(open(os.path.join(os.path.dirname(__file__), "fixtures", "jra_baba_index3_20261114_preday.html.gz"), "rb").read()).decode()
        r = parse_going_page(h)
        self.assertEqual((r["venue"], r["kai"], r["nichi"], r["date"], r["pre_day"]), ("福島", 3, 3, "2026-11-14", True))
        self.assertEqual((r["turf_going"], r["dirt_going"]), ("良", "良"))
        self.assertIn("金曜", r["as_of"])
if __name__ == "__main__": unittest.main()
