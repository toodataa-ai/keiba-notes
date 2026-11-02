"""Regression tests for seven experimental plans, none of which can claim Grade A evidence."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "e2e_validation"))
from validate_all_experiment_designs_v1 import validate  # noqa: E402


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class AllExperimentDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = read("e2e_validation/improvement_experiments_v1.json")
        cls.evidence = read("docs/data/jra_improvement_cycle_v1.json")
        cls.latest = read("docs/data/latest_prompt.json")
        cls.models = read("baba_models_v2/model_registry.json")

    def run_validation(self, registry=None, evidence=None, latest=None, models=None):
        return validate(registry or self.registry, evidence or self.evidence,
                        latest or self.latest, models or self.models)

    def test_seven_designs_all_unrun(self):
        errors, status = self.run_validation()
        self.assertEqual(errors, [])
        self.assertEqual(status["experiment_count"], 7)
        self.assertEqual(status["registered_design_count"], 3)
        self.assertEqual(status["awaiting_evidence_count"], 4)
        self.assertEqual(status["strict_paired_cases_total"], 0)
        self.assertFalse(status["candidate_execution_implemented"])

    def test_all_four_formal_topics_separate(self):
        errors, status = self.run_validation()
        self.assertFalse(errors)
        self.assertEqual(len([x for x in status["experiments"] if x["family"] == "formal_jra"]), 4)

    def test_no_research_historical_horses_converted_to_scores(self):
        errors, status = self.run_validation()
        self.assertFalse(errors)
        research = [x for x in status["experiments"] if x["family"] == "experience_regime_research"]
        self.assertEqual(len(research), 3)
        self.assertTrue(all(x["qualified_observations"] == 0 for x in research))

    def test_no_fake_paired_comparisons(self):
        registry = copy.deepcopy(self.registry)
        registry["experiments"][0]["strict_pairs_count"] = 1
        self.assertTrue(self.run_validation(registry=registry)[0])

    def test_cannot_claim_candidate_runner_is_ready(self):
        registry = copy.deepcopy(self.registry)
        registry["experiments"][0]["runner_ready"] = True
        self.assertTrue(self.run_validation(registry=registry)[0])

    def test_cannot_advance_weak_observation_theme(self):
        registry = copy.deepcopy(self.registry)
        plan = next(x for x in registry["experiments"] if x["id"] == "field_experience")
        plan["status"] = "design"
        self.assertTrue(self.run_validation(registry=registry)[0])

    def test_prestart_proof_required(self):
        registry = copy.deepcopy(self.registry)
        registry["experiments"][0]["prestart_pairing"]["immutable_proof_commit_for_both"] = False
        self.assertTrue(self.run_validation(registry=registry)[0])

    def test_cannot_modify_active_formal_version(self):
        registry = copy.deepcopy(self.registry)
        next(x for x in registry["experiments"] if x["id"] == "ticket_portfolio")["baseline"] = "v3.0"
        self.assertTrue(self.run_validation(registry=registry)[0])

    def test_cannot_change_production_router(self):
        models = copy.deepcopy(self.models)
        models["production_router_changed"] = True
        self.assertTrue(self.run_validation(models=models)[0])


if __name__ == "__main__":
    unittest.main()
