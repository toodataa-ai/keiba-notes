import unittest
from claude_track import open_ready_issues as o

class T(unittest.TestCase):
    def test_nothing_when_collecting(self):
        e = {"pace": {"state": "collecting"}, "experience": {"regimes": {"E0": {"state": "collecting"}}}}
        self.assertEqual(o.needed(e), [])
    def test_ready_items(self):
        e = {"pace": {"state": "ready_for_decision", "pairs": 20, "mean_log_loss_base": 2.3, "mean_log_loss_pace": 2.2, "races_improved": 12, "races_worse": 8},
             "experience": {"regimes": {"E0": {"state": "ready_for_review", "horses": 31, "races": 6, "predicted_wins": 2.5, "actual_wins": 4},
                                        "E1": {"state": "collecting"}}}}
        t = [x["title"] for x in o.needed(e)]
        self.assertEqual(t, ["[Claude単独] 位置取りの補正：判定できます", "[Claude単独] 若駒（0戦）：確認できます"])
if __name__ == "__main__": unittest.main()
