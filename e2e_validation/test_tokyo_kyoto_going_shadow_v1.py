import copy
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "e2e_validation"))
from tokyo_kyoto_going_shadow_v1 import capture  # noqa: E402


class PilotCaptureTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat("2027-01-03T10:00:00+09:00")
        self.input = {
            "schema_version": 1,
            "race_id": "2027-test-tokyo-main",
            "track": "tokyo",
            "surface": "turf",
            "scheduled_start_at": "2027-01-03T15:00:00+09:00",
            "information_cutoff_at": "2027-01-03T09:00:00+09:00",
            "morning_moisture_observed_at": "2027-01-03T07:00:00+09:00",
            "morning_moisture": 15.0,
            "jra_moisture_source_url": "https://www.jra.go.jp/keiba/baba/",
            "weather": {
                "observed_through_at": "2027-01-03T08:00:00+09:00",
                "source_url": "https://www.data.jma.go.jp/",
                "rain_after_measurement_mm": 0.4,
                "hours_since_last_rain": 1.0,
                "temperature_c": 12.0,
                "wind_mps": 2.0,
                "sunshine_hours": 1.0,
                "elapsed_hours_since_measurement": 2.0
            }
        }

    def test_pilot_capture_not_formal_grade_a(self):
        out = capture(self.input, now=self.now)
        self.assertFalse(out["counts_toward_formal_new_old_pairs"])
        self.assertFalse(out["grade_a_formal_pair"])
        self.assertTrue(out["not_full_step1_prediction"])
        self.assertEqual(out["candidate"], "v3.13-tokyo-kyoto-track-condition-shadow-v0.1")
        self.assertAlmostEqual(sum(out["prediction"]["condition_probs_operational"].values()), 1, delta=0.001)

    def test_other_venue_fails_closed(self):
        self.input["track"] = "nakayama"
        with self.assertRaises(ValueError):
            capture(self.input, now=self.now)

    def test_cutoff_after_start_rejected(self):
        self.input["information_cutoff_at"] = "2027-01-03T16:00:00+09:00"
        with self.assertRaises(ValueError):
            capture(self.input, now=self.now)

    def test_weather_after_cutoff_rejected(self):
        self.input["weather"]["observed_through_at"] = "2027-01-03T11:00:00+09:00"
        with self.assertRaises(ValueError):
            capture(self.input, now=self.now)

    def test_poststart_execution_rejected(self):
        after = datetime.fromisoformat("2027-01-03T15:01:00+09:00")
        with self.assertRaises(ValueError):
            capture(self.input, now=after)

    def test_not_a_proven_source_without_urls(self):
        self.input["weather"]["source_url"] = ""
        with self.assertRaises(ValueError):
            capture(self.input, now=self.now)


if __name__ == "__main__":
    unittest.main()
