import unittest
from datetime import datetime, timezone, timedelta
from claude_track import record_run as rr
JST = timezone(timedelta(hours=9))


class T(unittest.TestCase):
    def test_add_and_trim(self):
        old = {"runs": [{"task": "T2", "date": "2026-10-01", "status": "ok"}]}
        d = rr.add(old, "T3", "ok", "x" * 500, None, datetime(2026, 11, 8, 18, 40, tzinfo=JST))
        self.assertEqual(len(d["runs"]), 1); self.assertEqual(d["runs"][0]["task"], "T3"); self.assertEqual(len(d["runs"][0]["note"]), 200)
        with self.assertRaises(AssertionError):
            rr.add({}, "T9", "ok", "", None, datetime(2026, 11, 8, tzinfo=JST))


if __name__ == "__main__":
    unittest.main()
