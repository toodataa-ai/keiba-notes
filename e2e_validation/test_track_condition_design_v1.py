import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "e2e_validation"))
from validate_track_condition_design_v1 import validate  # noqa: E402


class TrackConditionExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "e2e_validation/improvement_experiments_v1.json").read_text(encoding="utf-8"))
        cls.latest = json.loads((ROOT / "docs/data/latest_prompt.json").read_text(encoding="utf-8"))
        cls.models = json.loads((ROOT / "baba_models_v2/model_registry.json").read_text(encoding="utf-8"))

    def test_baseline_passes_as_design_not_approved(self):
        self.assertEqual(validate(self.registry, self.latest, self.models), [])

    def test_no_fake_comparison_counts(self):
        r = copy.deepcopy(self.registry)
        r["experiments"][0]["valid_pairs_count"] = 20
        self.assertTrue(validate(r, self.latest, self.models))

    def test_cannot_mark_active_without_runner_or_proof(self):
        r = copy.deepcopy(self.registry)
        r["experiments"][0]["status"] = "active"
        self.assertTrue(validate(r, self.latest, self.models))

    def test_latest_formal_version_must_match(self):
        latest = copy.deepcopy(self.latest)
        latest["version"] = "other-formal"
        self.assertTrue(validate(self.registry, latest, self.models))

    def test_production_routing_not_allowed(self):
        r = copy.deepcopy(self.models)
        r["production_router_changed"] = True
        self.assertTrue(validate(self.registry, self.latest, r))


if __name__ == "__main__":
    unittest.main()
