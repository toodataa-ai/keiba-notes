import unittest

from claude_track import head_to_head as h


def c(date, venue, name, stake, pay, prosp=True):
    return {"date": date, "venue": venue, "race_name": name,
            "result": {"prospective": prosp, "stake_yen": stake, "payout_yen": pay}}


def g(date, venue, name, stake, pay):
    return {"date": date, "venue": venue, "race": name, "scope": "jra-main", "performance": {"stake_yen": stake, "payout_yen": pay}}


class T(unittest.TestCase):
    def test_common_only_and_skip_counted(self):
        cs = {"races": [c("2026-11-08", "東京", "天皇賞（秋）", 0, 0),          # Claude 見送り＝購入0円で数える
                        c("2026-11-08", "京都", "まほろばS", 1000, 3000),
                        c("2026-11-08", "福島", "福島記念", 500, 0),            # ChatGPT なし
                        c("2026-11-08", "阪神", "別のレース", 500, 0)]}          # 名前が違う
        gr = {"races": [g("2026-11-08", "東京", "天皇賞(秋)", 2800, 0), g("2026-11-08", "京都", "まほろばステークス", 5000, 4000),
                        g("2026-11-08", "阪神", "ほかのレース", 100, 0), g("2026-11-08", "小倉", "小倉記念", 100, 0)]}
        d = h.build(cs, gr)
        self.assertEqual(d["races"], 2)
        self.assertEqual(d["claude"]["stake_yen"], 1000)
        self.assertEqual(d["claude"]["skipped_races"], 1)
        self.assertEqual(d["chatgpt"]["stake_yen"], 7800)
        self.assertEqual(len(d["excluded"]["claude_only"]), 1)
        self.assertEqual(len(d["excluded"]["name_mismatch"]), 1)
        self.assertEqual([x["venue"] for x in d["excluded"]["chatgpt_only"]], ["小倉"])
        self.assertIn("結論を出さない", d["verdict"])

    def test_not_prospective_excluded(self):
        d = h.build({"races": [c("2026-11-08", "東京", "天皇賞（秋）", 100, 0, prosp=False)]},
                    {"races": [g("2026-11-08", "東京", "天皇賞（秋）", 100, 0)]})
        self.assertEqual(d["races"], 0)


if __name__ == "__main__":
    unittest.main()
