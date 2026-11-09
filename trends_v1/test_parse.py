import unittest
from trends_v1.parse import parse_race, klass

REC = {"code": "2509050812", "date": "2025-12-28", "pages": {"result": {
    "text": "x 2025年12月28日（日） 5回阪神8日 16:05発走 カウントダウンステークス 芝・右・外 1200m 天気： 晴 馬場： 良 3歳以上 3勝クラス(1600万下) （混合）（特指） 定量 本賞金：1840 万円",
    "tables": [[["着順", "枠番", "馬番", "馬名 性齢/馬体重/B", "タイム 着差", "通過順位 上がり3Fタイム", "騎手名 斤量", "人気 （オッズ）", "調教師"],
                ["1", "6", "6", "イツモニコニコ 牝4/500(0)/B⟨/keiba/directory/horse/2021107063/⟩", "1:08.4 -", "03-02 33.2",
                 "田中 健 56.0⟨/keiba/directory/jockey/01114/⟩", "2 (4.0)", "浜田 多実雄⟨/keiba/directory/trainer/01138/⟩"],
                ["中止", "1", "1", "ヒーロー 牡4/446(-2)", "", "", "富田 暁 58.0⟨/keiba/directory/jockey/01168/⟩", "8 (22.8)", "吉田 直弘⟨/keiba/directory/trainer/01101/⟩"]]]}}}


class ParseTest(unittest.TestCase):
    def test_race_and_rows(self):
        race, rows = parse_race(REC)
        self.assertEqual((race["venue"], race["surface"], race["dist"], race["going"], race["klass"]), ("阪神", "芝", 1200, "良", "3勝"))
        self.assertEqual(race["inout"], "外")
        a, b = rows
        self.assertEqual((a["finish"], a["frame"], a["pass"], a["last3"], a["pop"], a["odds"]), (1, 6, [3, 2], 33.2, 2, 4.0))
        self.assertEqual((a["jockey"], a["jockey_name"], a["trainer"], a["trainer_name"], a["time"]), ("01114", "田中 健", "01138", "浜田 多実雄", 68.4))
        self.assertIsNone(b["finish"]); self.assertEqual(b["odds"], 22.8)

    def test_klass(self):
        self.assertEqual(klass("3歳 未勝利 馬齢"), "未勝利")
        self.assertEqual(klass("サラ系3歳以上 1000万下"), "2勝")
        self.assertEqual(klass("3歳以上 オープン"), "OP・重賞")


if __name__ == "__main__":
    unittest.main()
