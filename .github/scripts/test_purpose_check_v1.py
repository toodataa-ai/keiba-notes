import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(__file__))
import purpose_check_v1 as pc


def put(root, *a, text="{}"):
    f = os.path.join(root, *a)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    open(f, "w", encoding="utf-8").write(text)


class T(unittest.TestCase):
    def test_counts(self):
        r = tempfile.mkdtemp()
        pc.ROOT = r
        for rid, v in (("2026-11-07-03-11", "福島"), ("2026-11-07-05-11", "東京")):
            put(r, "claude_track", "inputs", rid, "20261107T023000Z.json", text=json.dumps({"venue": v}))
        put(r, "claude_track", "odds", "2026-11-07-03-11", "a.json")
        put(r, "claude_track", "results", "2026-11-07-03-11.json")
        put(r, "claude_track", "predictions", "2026-11-07-03-11", "step1-x.json")      # step2 が無い → 数えない
        put(r, "claude_track", "predictions", "2026-11-07-05-11", "step1-x.json")
        put(r, "claude_track", "predictions", "2026-11-07-05-11", "step2-x.json")
        put(r, "baba_models_v2", "live", "2026-11-07_fukushima.json")
        put(r, "baba_models_v2", "forecast_archive", "2026", "11", "20261107_0604.json.gz")
        put(r, "baba_models_v2", "forecast_archive", "2026", "11", "20261107_1210.json.gz")
        s = pc.day_status("2026-11-07")
        self.assertEqual(s["race_cards"], {"done": 2, "expected": 2})
        self.assertEqual(s["odds"], {"done": 1, "expected": 2})
        self.assertEqual(s["results"], {"done": 1, "expected": 2})
        self.assertEqual(s["predictions"], {"done": 1, "expected": 2})
        self.assertEqual(s["going_live"], {"done": 1, "expected": 1})   # 対象は福島だけ
        self.assertEqual(s["forecast_am"]["done"], 1)
        self.assertEqual(s["going_official"], {"done": 1, "expected": 1})
        self.assertEqual(s["forecast_pm"]["done"], 0)
        self.assertEqual(pc.day_status("2026-11-06")["odds"], {"done": 0, "expected": 0})   # 開催なしは対象なし


if __name__ == "__main__":
    unittest.main()
