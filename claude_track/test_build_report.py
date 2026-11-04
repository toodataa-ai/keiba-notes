import unittest
from claude_track import build_report as br

P = {"race_id": "2026-11-08-tokyo-11", "race_name": "テスト<賞>", "venue": "東京", "date": "2026-11-08", "prompt_version": "claude-v1.0",
     "generated_at": "2026-11-08T09:20:00+09:00", "going_forecast": {"probs": {"良": 0.8, "稍重": 0.2}, "most_likely": "良"},
     "horses": [{"no": 2, "name": "B", "mark": None, "ability": "C", "win_prob": 0.1, "top3_prob": 0.3, "reason": "x"},
                {"no": 1, "name": "A", "mark": "◎", "ability": "A", "win_prob": 0.4, "top3_prob": 0.7, "reason": "<script>"}]}
S2 = {"bets": [{"type": "馬単", "selection": [1, 2], "stake_yen": 300, "market_odds": 12.3, "reason": "r"}], "total_stake_yen": 300, "odds_observed_at": "t"}


class T(unittest.TestCase):
    def test_render(self):
        h = br.render(P, S2, {"summary": "反省", "lessons": ["l"]}, None, None)
        self.assertIn("テスト&lt;賞&gt;", h); self.assertNotIn("<script>", h)
        self.assertIn("1→2", h); self.assertIn("反省会", h); self.assertIn("良 80.0%", h)
        self.assertNotIn("結果を見る", h)

    def test_skip(self):
        h = br.render(P, {"bets": [], "skip_reason": "オッズ未取得"}, None, None, None)
        self.assertIn("見送り：オッズ未取得", h)


if __name__ == "__main__":
    unittest.main()
