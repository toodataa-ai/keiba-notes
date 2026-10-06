from __future__ import annotations

import unittest

from experience_regime_v1.sampling import (
    SamplingValidationError,
    select_races,
)


POLICY = {
    "version": "stratified-v0.1",
    "seed_namespace": "test-seed",
    "race_number_min": 1,
    "race_number_max": 12,
    "always_include": {"official_prediction_races": True},
    "categories": {
        "debut": {"label": "新馬", "target_per_week": 2},
        "maiden": {"label": "未勝利", "target_per_week": 1},
    },
    "shortage_policy": "test",
    "selection_policy": "test",
}


class StratifiedSamplingTests(unittest.TestCase):
    def _pool(self) -> dict:
        return {
            "week_id": "2026-10-10",
            "races": [
                {"race_id": "a", "date": "2026-10-10", "venue": "東京", "race_no": 4, "race_category": "debut"},
                {"race_id": "b", "date": "2026-10-10", "venue": "京都", "race_no": 5, "race_category": "debut"},
                {"race_id": "c", "date": "2026-10-11", "venue": "東京", "race_no": 5, "race_category": "debut"},
                {"race_id": "d", "date": "2026-10-11", "venue": "京都", "race_no": 2, "race_category": "maiden"},
                {"race_id": "e", "date": "2026-10-12", "venue": "東京", "race_no": 11, "race_category": "maiden", "official_prediction": True},
            ],
        }

    def test_deterministic_selection_and_quota(self) -> None:
        first = select_races(self._pool(), POLICY)
        second = select_races(self._pool(), POLICY)
        self.assertEqual(first["selected_races"], second["selected_races"])
        debut = first["category_summary"]["debut"]
        maiden = first["category_summary"]["maiden"]
        self.assertEqual(debut["selected_stratified_races"], 2)
        self.assertEqual(maiden["selected_stratified_races"], 1)

    def test_official_prediction_is_always_included_and_does_not_fill_quota(self) -> None:
        result = select_races(self._pool(), POLICY)
        selected = {r["race_id"]: r for r in result["selected_races"]}
        self.assertIn("e", selected)
        self.assertEqual(selected["e"]["sample_origin"], "official_prediction")
        self.assertIn("d", selected)
        self.assertEqual(selected["d"]["sample_origin"], "stratified_sample")

    def test_rejects_out_of_scope_race_number(self) -> None:
        pool = self._pool()
        pool["races"][0]["race_no"] = 13
        with self.assertRaises(SamplingValidationError):
            select_races(pool, POLICY)

    def test_rejects_unknown_category(self) -> None:
        pool = self._pool()
        pool["races"][0]["race_category"] = "unknown"
        with self.assertRaises(SamplingValidationError):
            select_races(pool, POLICY)


if __name__ == "__main__":
    unittest.main()
