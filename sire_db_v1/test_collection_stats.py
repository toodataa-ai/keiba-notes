import datetime as dt
import json
import os
import tempfile
import unittest

from sire_db_v1 import collection_stats as cs

JST = cs.JST


def _w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp()
        _w(os.path.join(self.root, "baba_models_v2", "going_labels", "jra_going_2025.csv"), "h\n1\n2\n3\n4\n")
        _w(os.path.join(self.root, "baba_models_v2", "going_labels", "jra_going_2026.csv"), "h\n1\n2\n")
        _w(os.path.join(self.d, "races_done.txt"), "2501011101\n2501011102\n2601011101\n\n")
        h1 = {"name": "A", "ped": {"sire": "S1", "dam": "D1"}, "history": [
            {"date": "2025-01-05", "jockey_id": "1", "odds": 3.2, "last3f": None, "race": "x"},
            {"date": "2026-02-01", "jockey_id": "2", "odds": None, "race": "y"}]}
        h2 = {"name": "B", "ped": {"sire": "S1", "dam": "D2"}, "history": [
            {"date": "2024-12-01", "jockey_id": "1", "odds": 1.0, "race": "z"}]}
        _w(os.path.join(self.d, "horses_2023.jsonl"), json.dumps(h1) + "\n")
        _w(os.path.join(self.d, "horses_2024.jsonl"), json.dumps(h2) + "\nnot json\n")
        rec = {"code": "2501011101", "pages": {"result": {"tables": [[["a", "b"], ["c", ""]]], "text": "abcd"},
                                              "denma": {"tables": [], "text": "xy"}}}
        _w(os.path.join(self.d, "race_pages", "2025.jsonl"), json.dumps(rec) + "\n")
        _w(os.path.join(self.d, "race_pages_done.txt"), "2501011101\n")

    def test_build(self):
        s = cs.build(self.d, dt.datetime(2026, 11, 8, 6, 0, tzinfo=JST), root=self.root)
        self.assertEqual(s["past_races"], {"done": 3, "total": 6, "frac": 0.5})
        self.assertEqual([(y["year"], y["done"], y["total"]) for y in s["by_year"]], [(2025, 2, 4), (2026, 1, 2)])
        self.assertEqual((s["horses"], s["run_rows"]), (2, 3))
        self.assertEqual(s["data_values"], 4 + 3 + 4)  # None・空は数えない
        self.assertEqual((s["sires"], s["dams"], s["jockeys"]), (1, 2, 2))
        self.assertEqual((s["first_date"], s["last_date"]), ("2024-12-01", "2026-02-01"))
        self.assertEqual(s["race_pages"]["done"], 1)
        self.assertEqual((s["race_pages"]["cells"], s["race_pages"]["chars"]), (3, 6))
        self.assertGreater(s["race_pages"]["bytes"], 0)
        self.assertNotIn("A", json.dumps(s))  # 馬名は出さない

    def test_history_and_growth(self):
        s = cs.build(self.d, dt.datetime(2026, 11, 8, 6, 0, tzinfo=JST), root=self.root)
        h = cs.update_history({}, s)
        self.assertEqual(cs.growth(h, s), None)  # 1点だけ
        s2 = dict(s)
        s2["generated_at"] = "2026-11-08T18:00:00+09:00"  # 同じ日は上書き
        h = cs.update_history(h, s2)
        self.assertEqual(len(h["points"]), 1)
        older = {"points": [{"date": "2026-11-06", "races_done": 1, "horses": 1, "run_rows": 1,
                             "data_values": 1, "race_pages_done": 0}]}
        h = cs.update_history(older, s)
        g = cs.growth(h, s)
        self.assertEqual(g["days"], 2)
        self.assertEqual(g["per_day"]["races_done"], 1)  # (3-1)/2
        self.assertEqual(g["eta_days_past_races"], 3)  # 残り3 ÷ 1日1件

    def test_history_cap(self):
        s = cs.build(self.d, dt.datetime(2026, 11, 8, 6, 0, tzinfo=JST), root=self.root)
        pts = [{"date": (dt.date(2026, 1, 1) + dt.timedelta(days=i)).isoformat(), "races_done": i, "horses": 0,
                "run_rows": 0, "data_values": 0, "race_pages_done": 0} for i in range(120)]
        h = cs.update_history({"points": pts}, s)
        self.assertEqual(len(h["points"]), cs.HISTORY_DAYS)


if __name__ == "__main__":
    unittest.main()
