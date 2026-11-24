import csv, tempfile, unittest
from pathlib import Path
import refresh_baba_data as R


def w(p, head, rows):
    R.write_csv(Path(p), head, rows)


class TestMerge(unittest.TestCase):
    def test_weather_keeps_old_replaces_recent(self):
        d = Path(tempfile.mkdtemp())
        head = ["station", "observed_date", "hour", "v"]
        w(d / "old.csv", head, [["A", "2026-09-01", "1", "x"], ["A", "2026-10-01", "1", "old"], ["A", "2026-10-02", "2", "old"]])
        w(d / "new.csv", head, [["A", "2026-10-01", "1", "new"], ["A", "2026-11-20", "10", "new"], ["A", "2026-11-20", "2", "new"]])
        keep, n = R.merge_by_date(d / "old.csv", d / "new.csv", "observed_date", "2026-10-01",
                                  lambda h, r: (r[0], r[1], int(r[2])))
        rows = R.read_csv(d / "old.csv")[1]
        self.assertEqual((keep, n), (1, 4))
        self.assertEqual([r[1:] for r in rows], [["2026-09-01", "1", "x"], ["2026-10-01", "1", "new"], ["2026-11-20", "2", "new"], ["2026-11-20", "10", "new"]])

    def test_year_merge_replaces_that_year_only(self):
        d = Path(tempfile.mkdtemp())
        head = ["year", "k"]
        w(d / "old.csv", head, [["2025", "a"], ["2026", "b"]])
        w(d / "new.csv", head, [["2026", "c"], ["2026", "d"]])
        R.merge_by_year(d / "old.csv", d / "new.csv", "year", {"2026"}, lambda h, r: (r[0], r[1]))
        self.assertEqual(R.read_csv(d / "old.csv")[1], [["2025", "a"], ["2026", "c"], ["2026", "d"]])

    def test_empty_new_is_an_error_and_keeps_old(self):
        d = Path(tempfile.mkdtemp())
        head = ["year", "k"]
        w(d / "old.csv", head, [["2026", "b"]]); w(d / "new.csv", head, [])
        with self.assertRaises(RuntimeError):
            R.merge_by_year(d / "old.csv", d / "new.csv", "year", {"2026"}, lambda h, r: r)
        self.assertEqual(R.read_csv(d / "old.csv")[1], [["2026", "b"]])

    def test_header_mismatch_is_an_error(self):
        d = Path(tempfile.mkdtemp())
        w(d / "old.csv", ["a", "b"], [["1", "2"]]); w(d / "new.csv", ["a", "c"], [["1", "2"]])
        with self.assertRaises(RuntimeError):
            R.merge_by_year(d / "old.csv", d / "new.csv", "a", {"1"}, lambda h, r: r)


if __name__ == "__main__":
    unittest.main()
