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



class V316StrictReadOnlyTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        self.prior = {
            "status": "formal_prestart", "purchase_strategy_version": "v3.15",
            "model_version": "v3.13", "source_race_id": "synthetic",
            "source_prediction_path": "original-v313.json",
            "source_prediction_sha256": "a" * 64,
            "final_bets_fixed_at": "2026-10-25T08:10:00+09:00",
            "formal_bets": [{"type":"馬単","selection":[1,2],"stake_yen":100}]
        }
        self.content = json.dumps(self.prior,ensure_ascii=False)
        self.pred = {
            "purchase_strategy_version":"v3.16","model_version":"v3.13",
            "source_race_id":"synthetic","source_prediction_path":"original-v313.json",
            "source_prediction_sha256":"a" * 64,
            "source_purchase_path":"original-v315.json",
            "source_purchase_sha256":hashlib.sha256(self.content.encode("utf-8")).hexdigest(),
            "source_purchase_proof":"some-prerace-commit",
            "final_bets_fixed_at":"2026-10-25T10:00:00+09:00",
            "formal_bets":[{"type":"馬単","selection":[1,2],"stake_yen":300}]
        }

    def _run(self, prediction):
        from datetime import datetime
        from unittest.mock import patch
        from e2e_validation.evaluate import normalize_v316_for_e2e
        with patch("e2e_validation.evaluate.git_text", return_value=self.content), \
             patch("e2e_validation.evaluate.git_commit_time",return_value=datetime.fromisoformat("2026-10-25T09:30:00+09:00")), \
             patch("e2e_validation.evaluate.normalize_v315_for_e2e",return_value={"prompt_version":"v3.13"}) as bridge:
            output=normalize_v316_for_e2e(Path("."),"new-publication","source-publication",prediction)
            if bridge.called:
                self.assertEqual(bridge.call_args.args[3]["formal_bets"],prediction["formal_bets"])
                self.assertEqual(bridge.call_args.args[3]["purchase_strategy_version"],"v3.15")
            return output

    def test_only_amounts_change_and_old_data_unmodified(self):
        original=json.dumps(self.pred,sort_keys=True)
        projected=self._run(self.pred)
        self.assertEqual(projected["purchase_strategy_version"],"v3.16")
        self.assertEqual(json.dumps(self.pred,sort_keys=True),original)

    def test_refuses_changed_ticket_selection(self):
        self.pred["formal_bets"][0]["selection"]=[2,1]
        with self.assertRaisesRegex(ValidationError,"must not change"):
            self._run(self.pred)

    def test_refuses_modified_v315_sha(self):
        self.pred["source_purchase_sha256"]="0"*64
        with self.assertRaisesRegex(ValidationError,"SHA256"):
            self._run(self.pred)

    def test_refuses_changed_ability_model(self):
        self.pred["model_version"]="v3.16"
        with self.assertRaisesRegex(ValidationError,"v3.13"):
            self._run(self.pred)


if __name__ == "__main__":
    unittest.main()
