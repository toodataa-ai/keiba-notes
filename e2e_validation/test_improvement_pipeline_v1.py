import copy
import datetime as dt
import json
import unittest
from pathlib import Path

from e2e_validation import improvement_pipeline_v1 as p

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "e2e_validation/improvement_pipeline_policy_v1.json").read_text(encoding="utf-8"))


def model(track, surface, status, prod=False):
    return {"track": track, "surface": surface, "status": status, "routing": {"production": prod}}


def base_inputs():
    baba = {"updated_at": "2026-10-05", "models": []}
    for k, _ in POLICY["tracks"]:
        for s in ("turf", "dirt"):
            baba["models"].append(model(k, s, "pilot"))
    cycle = {"formal": {"hypotheses": [
        {"id": h, "next_decision": {"screening": {"ready_to_design_experiment": False, "qualifying_race_reviews": 1, "minimum_qualifying_race_reviews": 3}}}
        for h in ("pace_positioning", "track_condition", "ticket_portfolio", "field_experience")]},
        "research": {"regimes": [{"id": r, "next_decision": {"win_probability_horse_records_remaining": 30, "additional_races_estimate": 3}} for r in ("experience_e0", "experience_e1", "experience_e2")]}}
    evidence = {"horses": 100, "factor_support_counts": {"6": 100}, "week_id": "w"}
    return {"registry": {"experiments": []}, "status": {"experiments": []}, "cycle": cycle, "baba": baba, "evidence": evidence}


def run(i, today=dt.date(2026, 11, 2)):
    return p.build(POLICY, i["registry"], i["status"], i["cycle"], i["baba"], i["evidence"], today)


def unit(res, uid):
    return next(u for u in res["units"] if u["id"] == uid)


class PipelineTest(unittest.TestCase):
    def test_baseline_everything_in_research(self):
        r = run(base_inputs())
        self.assertFalse(r["automatic_promotion"])
        self.assertEqual({u["state"] for u in r["units"]}, {"research"})
        self.assertEqual(list(p.issue_drafts(r)), [])

    def test_baba_track_needs_both_surfaces(self):
        i = base_inputs()
        for m in i["baba"]["models"]:
            if m["track"] == "tokyo" and m["surface"] == "turf":
                m["status"] = "candidate"
        self.assertEqual(unit(run(i), "track_condition:track:tokyo")["state"], "research")
        for m in i["baba"]["models"]:
            if m["track"] == "tokyo":
                m["status"] = "candidate"
        r = run(i)
        self.assertEqual(unit(r, "track_condition:track:tokyo")["state"], "ready_to_register")
        self.assertEqual([d["unit_id"] for d in p.issue_drafts(r)], ["track_condition:track:tokyo"])

    def test_production_track_is_not_a_challenger_candidate(self):
        i = base_inputs()
        for m in i["baba"]["models"]:
            if m["track"] == "nakayama":
                m["status"] = "validated"
                m["routing"]["production"] = True
        u = unit(run(i), "track_condition:track:nakayama")
        self.assertEqual(u["state"], "in_production")
        self.assertEqual(list(p.issue_drafts(run(i))), [])

    def test_experience_regime_ready_at_zero_remaining(self):
        i = base_inputs()
        i["cycle"]["research"]["regimes"][0]["next_decision"]["win_probability_horse_records_remaining"] = 0
        r = run(i)
        self.assertEqual(unit(r, "field_experience:e0")["state"], "ready_to_register")
        self.assertEqual(unit(r, "field_experience:e1")["state"], "research")

    def test_pedigree_needs_regimes_and_coverage(self):
        i = base_inputs()
        for k in (0, 1):
            i["cycle"]["research"]["regimes"][k]["next_decision"]["win_probability_horse_records_remaining"] = 0
        self.assertEqual(unit(run(i), "field_experience:pedigree")["state"], "ready_to_register")
        i["evidence"]["factor_support_counts"]["6"] = 50
        self.assertEqual(unit(run(i), "field_experience:pedigree")["state"], "research")

    def test_hypothesis_wide_experiment_does_not_leak_to_finer_units(self):
        i = base_inputs()
        i["registry"]["experiments"].append({"id": "EXP-002", "hypothesis_ids": ["track_condition"], "status": "collecting"})
        i["status"]["experiments"].append({"id": "EXP-002", "status": "collecting", "minimum_prospective_pairs": 20, "prospective": {"pairs": 5}})
        r = run(i)
        o = unit(r, "track_condition:official")
        self.assertEqual((o["state"], o["stage"], o["experiment_id"]), ("comparing", 2, "EXP-002"))
        self.assertAlmostEqual(o["frac"], 0.25)
        self.assertEqual(unit(r, "track_condition:track:tokyo")["state"], "research")

    def test_unit_ids_register_a_single_unit(self):
        i = base_inputs()
        i["registry"]["experiments"].append({"id": "EXP-010", "hypothesis_ids": ["field_experience"], "unit_ids": ["field_experience:e0"], "status": "collecting"})
        i["status"]["experiments"].append({"id": "EXP-010", "status": "collecting", "minimum_prospective_pairs": 20, "prospective": {"pairs": 0}})
        r = run(i)
        self.assertEqual(unit(r, "field_experience:e0")["state"], "comparing")
        self.assertEqual(unit(r, "field_experience:e1")["state"], "research")

    def test_staleness(self):
        r = run(base_inputs(), dt.date(2026, 11, 2))
        self.assertTrue(r["baba_registry_freshness"]["is_stale"])
        r = run(base_inputs(), dt.date(2026, 10, 10))
        self.assertFalse(r["baba_registry_freshness"]["is_stale"])


if __name__ == "__main__":
    unittest.main()
