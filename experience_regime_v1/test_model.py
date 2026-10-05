from __future__ import annotations

import unittest

from experience_regime_v1.model import (
    ExperienceValidationError,
    aggregate_rows,
    build_horse_rows,
    classify_regime,
    validate_experience_block,
)


class ExperienceRegimeTests(unittest.TestCase):
    def test_regime_boundaries(self) -> None:
        self.assertEqual(classify_regime(0), "E0")
        self.assertEqual(classify_regime(1), "E1")
        self.assertEqual(classify_regime(3), "E1")
        self.assertEqual(classify_regime(4), "E2")
        self.assertEqual(classify_regime(20), "E2")

    def test_invalid_starts_rejected(self) -> None:
        with self.assertRaises(ExperienceValidationError):
            classify_regime(-1)
        with self.assertRaises(ExperienceValidationError):
            classify_regime(1.5)
        with self.assertRaises(ExperienceValidationError):
            classify_regime(True)

    def test_declared_regime_mismatch_rejected(self) -> None:
        prediction = {
            "experience": {
                "horses": {"1": {"starts_before_race": 0, "regime": "E1"}}
            }
        }
        with self.assertRaises(ExperienceValidationError):
            validate_experience_block(prediction)

    def test_build_and_aggregate_rows(self) -> None:
        prediction = {
            "race_id": "x",
            "prompt_version": "v3.1",
            "marks": {"win": 2, "second": 1, "third": 4},
            "step1_ranking": [2, 1, 4, 3, 5],
            "probabilities": {
                "win": {"1": 0.15, "2": 0.40, "3": 0.10, "4": 0.20, "5": 0.15},
                "top3": {"1": 0.70, "2": 0.80, "3": 0.35, "4": 0.70, "5": 0.45},
            },
            "experience": {
                "model_version": "e012-shadow-v0.1",
                "horses": {
                    "1": {"starts_before_race": 0, "regime": "E0"},
                    "2": {"starts_before_race": 2, "regime": "E1"},
                    "3": {"starts_before_race": 3, "regime": "E1"},
                    "4": {"starts_before_race": 5, "regime": "E2"},
                    "5": {"starts_before_race": 10, "regime": "E2"},
                },
            },
        }
        result = {"finish_order": [2, 1, 4, 3, 5]}
        rows = build_horse_rows(prediction, result)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["regime"], "E1")
        agg = aggregate_rows(rows)
        self.assertEqual(agg["E0"]["horse_observations"], 1)
        self.assertEqual(agg["E1"]["horse_observations"], 2)
        self.assertEqual(agg["E2"]["horse_observations"], 2)
        self.assertEqual(agg["E1"]["actual_win_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
