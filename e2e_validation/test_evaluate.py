from __future__ import annotations

import json
import unittest
from pathlib import Path

from e2e_validation.evaluate import (
    ValidationError,
    aggregate,
    evaluate_prediction,
    run,
    validate_distribution,
)


class EvaluateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.base_prediction = json.loads(
            (
                self.repo_root
                / "e2e_validation/fixtures/smoke/predictions/v3.0.json"
            ).read_text(encoding="utf-8")
        )
        self.candidate_prediction = json.loads(
            (
                self.repo_root
                / "e2e_validation/fixtures/smoke/predictions/v3.1.json"
            ).read_text(encoding="utf-8")
        )
        self.result = json.loads(
            (self.repo_root / "e2e_validation/fixtures/smoke/result.json").read_text(
                encoding="utf-8"
            )
        )

    def test_candidate_beats_smoke_baseline_on_marks(self) -> None:
        baseline = evaluate_prediction(self.base_prediction, self.result)
        candidate = evaluate_prediction(self.candidate_prediction, self.result)
        self.assertEqual(baseline["honmei_win"], 0)
        self.assertEqual(candidate["honmei_win"], 1)
        self.assertLess(baseline["top3_marks_capture"], candidate["top3_marks_capture"])
        self.assertLess(candidate["win_brier"], baseline["win_brier"])

    def test_probability_distribution_rejects_bad_sum(self) -> None:
        with self.assertRaises(ValidationError):
            validate_distribution({"a": 0.8, "b": 0.8}, label="bad")

    def test_aggregate_roi(self) -> None:
        metrics = evaluate_prediction(self.candidate_prediction, self.result)
        agg = aggregate([{"metrics": metrics}])
        self.assertEqual(agg["stake_yen"], 200)
        self.assertEqual(agg["payout_yen"], 530)
        self.assertEqual(agg["roi_pct"], 265.0)

    def test_synthetic_run_has_no_real_strict_cases(self) -> None:
        status = run(
            self.repo_root,
            self.repo_root / "e2e_validation/fixtures",
            self.repo_root / "e2e_validation/config.json",
        )
        self.assertEqual(status["case_counts"]["strict"], 0)
        self.assertEqual(status["case_counts"]["synthetic"], 1)
        self.assertEqual(status["errors"], [])
        self.assertEqual(status["versions"]["v3.0"]["all_non_synthetic"]["cases"], 0)


if __name__ == "__main__":
    unittest.main()
