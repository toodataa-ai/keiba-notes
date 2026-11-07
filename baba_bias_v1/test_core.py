import unittest

from baba_bias_v1 import core, daily


def page(name, going, rows, dist=1600, surf="芝"):
    head = (f"2025年12月28日（日） 5回阪神8日 16:05発走 {name} {surf}・右 {dist}m 天気： 晴 馬場： {going} "
            f"3歳以上 3勝クラス(1600万下) （混合）（特指） 定量 本賞金：1840、740万円 出馬表")
    table = [["着順", "枠番", "馬番", "馬名 性齢/馬体重/B", "タイム 着差", "通過順位 上がり3Fタイム", "騎手名 斤量", "人気 （オッズ）", "調教師"]]
    for fin, no, pos, tm, pop in rows:
        table.append([str(fin), str(no), str(no), f"馬{no} 牡4/480(0)", tm, f"{pos} 34.0", "騎手 56.0", f"{pop} (5.0)", "調教師"])
    return {"text": head, "tables": [[["単勝", "1"]], table]}


def field(n, front_good):
    """n頭。front_good=True：前（最終コーナーが前）の馬ほど人気より好走する並び。"""
    rows = []
    for i in range(n):
        pos = i + 1 if front_good else n - i
        rows.append((i + 1, i + 1, f"{pos:02d}-{pos:02d}", "1:34.%d" % (i % 9), n - i if front_good else i + 1))
    return rows


class T(unittest.TestCase):
    def test_parse(self):
        r = core.parse_result_page(page("テストS", "良", field(10, True)), "2509050811", "2025-12-28")
        self.assertEqual((r["venue"], r["kai"], r["day"], r["surf"], r["dist"], r["going"]), ("阪神", 5, 8, "芝", 1600, "良"))
        self.assertEqual(r["n"], 10)
        self.assertEqual(r["horses"][0]["pos"], [1, 1])
        self.assertAlmostEqual(core.winner_time(r), 94.0)
        self.assertIsNone(core.parse_result_page({"text": "なし", "tables": []}, "x", "2025-01-01"))
        h = core.parse_result_page(page("障害テスト", "良", field(10, True)), "x", "2025-01-01")
        self.assertFalse(core.usable({**h, "hurdle": True}))

    def test_front_sign(self):
        ef = [0.1 + 0.08 * i for i in range(10)]  # 人気どおりの着順
        # 人気薄(後ろの人気)の馬が前にいて好走 → front は＋、逆は−
        good = core.parse_result_page(page("A", "良", field(12, True)), "1", "2025-01-01")
        bad = core.parse_result_page(page("B", "良", field(12, False)), "2", "2025-01-01")
        self.assertIsNotNone(core.race_front_outer(good, ef))
        self.assertGreater(core.race_front_outer(good, ef)["front"], core.race_front_outer(bad, ef)["front"])

    def test_speed_and_day(self):
        races = []
        for i in range(30):
            rows = field(10, i % 2 == 0)
            races.append(core.parse_result_page(page(f"R{i}", "良", rows), f"{i:010d}", f"2025-03-{1 + i % 28:02d}"))
        races = [r for r in races if r]
        base = core.build_baselines(races, {"from": "2025-01-01", "to": "2025-12-31"})
        self.assertEqual(len(base["ef"]), 10)
        key = core.time_key(races[0])
        self.assertIn(key, base["time"])
        # 基準より速い勝ち時計 → speed は＋
        fast = core.parse_result_page(page("F", "良", [(1, 1, "01-01", "1:33.0", 1)] + field(10, True)[1:]), "99", "2025-04-01")
        self.assertGreater(core.race_speed(fast, base["time"]), 0)
        ds = core.day_scores(races[:6], {**base, "sd": {s: {"speed": 1, "front": 1, "outer": 1} for s in core.SURFACES}})
        self.assertIn("turf", ds)
        self.assertEqual(ds["turf"]["n_races"], 6)
        per = ds["turf"]["races"]
        self.assertEqual(len(per), 6)
        self.assertEqual(set(per[0]), {"r", "d", "speed", "front"})
        self.assertNotIn("dirt", ds)

    def test_min_races(self):
        r = core.parse_result_page(page("A", "良", field(10, True)), "1", "2025-01-01")
        self.assertEqual(core.day_scores([r, r, r], {"ef": [0.5] * 10, "time": {}, "sd": {s: {} for s in core.SURFACES}}), {})

    def test_labels(self):
        self.assertEqual(core.label("speed", 0.2), "ふつう")
        self.assertEqual(core.label("speed", 0.7), "やや高速")
        self.assertEqual(core.label("front", -1.4), "かなり差し有利")
        self.assertEqual(core.label("outer", None), "ふつう")

    def test_assemble_has_no_names(self):
        races = [core.parse_result_page(page(f"R{i}", "良", field(10, True)), f"{i:010d}", "2025-03-01") for i in range(6)]
        base = {"ef": [0.1 + 0.08 * i for i in range(10)], "time": {}, "sd": {s: {"speed": 1, "front": 1, "outer": 1} for s in core.SURFACES}, "source": {"races": 1}}
        doc = daily.assemble("2025-03-01", {"阪神": races}, base, min_read=1)
        self.assertEqual(daily.assemble("2025-03-01", {"阪神": races}, base)["venues"], {})  # 11未満は出さない
        s = str(doc)
        self.assertNotIn("馬1", s)
        self.assertIn("阪神", doc["venues"])
        self.assertIn("label", doc["venues"]["阪神"]["surfaces"]["turf"]["front"])


    def test_pending_dates(self):
        import datetime as dt, os, tempfile
        d = tempfile.mkdtemp(); o = tempfile.mkdtemp()
        for n in ("2026-11-06-03-11", "2026-11-07-03-11", "2026-11-07-05-11", "2026-11-08-03-11", "2026-10-01-03-11"):
            os.makedirs(os.path.join(d, n))
        open(os.path.join(o, "2026-11-06.json"), "w").write("{}")
        self.assertEqual(daily.pending_dates(d, o, dt.date(2026, 11, 8)), ["2026-11-07", "2026-11-08"])

    def test_header_variants_and_hurdle(self):
        def pg(h):
            return {"text": h, "tables": [[["着順", "枠番", "馬番", "馬名", "タイム 着差", "通過順位 上がり3Fタイム", "騎手名 斤量", "人気 （オッズ）", "調教師"]] + [[str(i), "1", str(i), "馬", "1:34.0", "01-01 34.0", "騎 56", f"{i} (5.0)", "調"] for i in range(1, 8)]]}
        tail = "天気： 晴 馬場： 良 3歳以上 オープン 定量 本賞金：1840万円 出馬表"
        r = core.parse_result_page(pg("5回中山1日 15:45発走 ステイヤーズS GII 芝・右・内2周 3600m " + tail), "1", "2025-12-06")
        self.assertEqual((r["surf"], r["dist"], r["hurdle"]), ("芝", 3600, False))
        r = core.parse_result_page(pg("5回阪神8日 11:35発走 サラ系障害3歳上未勝利 障害・芝→ダート 2970m " + tail), "2", "2025-12-06")
        self.assertTrue(r["hurdle"]); self.assertFalse(core.usable(r))
        r = core.parse_result_page(pg("4回東京1日 11:00発走 未勝利 ダート・左 1400m " + tail), "3", "2025-12-06")
        self.assertEqual((r["surf"], r["dist"]), ("ダート", 1400))
        small = core.parse_result_page({"text": "4回阪神5日 10:50発走 未勝利 芝・右 2000m " + tail, "tables": [pg("")["tables"][0][:4] + [] ]}, "4", "2025-12-06")
        self.assertIsNotNone(small)
        self.assertFalse(core.usable(small))  # 少頭数は数えるが、傾向には使わない

    def test_next_morning_page(self):
        hdr = ["着順", "枠番", "馬番", "馬名", "タイム 着差", "通過順位 上がり3Fタイム", "騎手名 斤量", "人気 （オッズ）", "調教師"]
        rows = [[str(i), "1", str(i), "馬", "1:34.0", "34.0", "騎 56", f"- ({3.0 * i:.1f})", "調"] for i in range(1, 9)]
        corner = [["コーナー", "通過順位"], ["4コーナー", "3 (1,2)(4,5)6,7,8"]]
        tail = "天気： 晴 馬場： 良 3歳以上 オープン 定量 本賞金：1840万円 出馬表"
        r = core.parse_result_page({"text": "4回東京1日 11:00発走 未勝利 ダート・左 1400m " + tail, "tables": [[hdr] + rows, corner]}, "9", "2025-12-06")
        h = {x["no"]: x for x in r["horses"]}
        self.assertEqual(h[1]["pop"], 1)
        self.assertEqual(h[8]["pop"], 8)
        self.assertEqual(h[3]["pos"], [1.0])
        self.assertEqual(h[1]["pos"], [2.5])
        self.assertEqual(h[8]["pos"], [8.0])
        self.assertEqual(len(core.horse_rows(r)), 8)


if __name__ == "__main__":
    unittest.main()
