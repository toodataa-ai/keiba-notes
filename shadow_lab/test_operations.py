"""Registry freshness diagnostics never fabricate prospective experiment pairs."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shadow_lab import operations as ops
from shadow_lab import runtime as rt


class DiscoverRegistryAuditTests(unittest.TestCase):
    DAY = "2026-11-01"

    def run_discover(self, checkout_races, main_races):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rt.dump(root / "docs/data/races.json", {"races": checkout_races})
            with (
                patch.object(rt, "ROOT", root),
                patch.object(ops, "packets", return_value=[]),
                patch.object(rt, "git", return_value=json.dumps({"races": main_races})),
            ):
                reports = ops.discover(self.DAY)
            attempts = list((root / "shadow_lab/evidence/attempts").glob("*-discovery.json"))
            self.assertEqual(len(attempts), 1)
            audit = rt.read(attempts[0])
            self.assertEqual(len(reports), len(rt.THEMES))
            self.assertFalse(list((root / "shadow_lab/evidence/pairs").glob("**/*.json")))
            return reports, audit

    def test_stale_experiment_branch_is_not_reported_as_missing_formal_forecast(self):
        main = [{"id": "2026-11-01-main", "scope": "jra-main", "date": self.DAY}]
        reports, audit = self.run_discover([], main)
        self.assertEqual(audit["registry_audit"]["main_only_races"], ["2026-11-01-main"])
        self.assertTrue(all(r["blocker"].startswith("stale_experiment_checkout_main_has_canonical_races:")
                            for r in reports))

    def test_checkout_with_formal_race_but_no_packet_reports_missing_inputs(self):
        race = {"id": "2026-11-01-main", "scope": "jra-main", "date": self.DAY}
        reports, audit = self.run_discover([race], [race])
        self.assertEqual(audit["registry_audit"]["main_only_races"], [])
        self.assertTrue(all(r["blocker"].startswith("canonical_races_present_but_same_cutoff_inputs_unavailable:")
                            for r in reports))

    def test_workflow_never_pushes_to_main_or_legacy_evidence_branch(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/jra-shadow-runtime.yml").read_text(encoding="utf-8")
        self.assertIn("experiment/jra-shadow-evidence-main-20261102", workflow)
        self.assertNotIn("experiment/jra-shadow-evidence-v1", workflow)
        self.assertNotIn("git push origin HEAD:refs/heads/main", workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success'",
                      workflow)


if __name__ == "__main__":
    unittest.main()
