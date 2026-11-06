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

    def test_sire_research_units_stay_in_research_and_never_notify(self):
        r = run(base_inputs())
        for uid in ("field_experience:sire_db", "field_experience:debut_sire"):
            self.assertEqual((unit(r, uid)["state"], unit(r, uid)["stage"]), ("research", 0))
        self.assertEqual(list(p.issue_drafts(r)), [])
        self.assertFalse(any(u["id"].startswith("field_experience:e") or u["id"] == "field_experience:pedigree" for u in r["units"]))

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
        i["registry"]["experiments"].append({"id": "EXP-010", "hypothesis_ids": ["field_experience"], "unit_ids": ["field_experience:debut_sire"], "status": "collecting"})
        i["status"]["experiments"].append({"id": "EXP-010", "status": "collecting", "minimum_prospective_pairs": 20, "prospective": {"pairs": 0}})
        r = run(i)
        self.assertEqual(unit(r, "field_experience:debut_sire")["state"], "comparing")
        self.assertEqual(unit(r, "field_experience:sire_db")["state"], "research")

    def test_staleness(self):
        r = run(base_inputs(), dt.date(2026, 11, 2))
        self.assertTrue(r["baba_registry_freshness"]["is_stale"])
        r = run(base_inputs(), dt.date(2026, 10, 10))
        self.assertFalse(r["baba_registry_freshness"]["is_stale"])



class GoingAdoptTest(unittest.TestCase):
    def test_both_usable_means_ready_to_adopt_without_comparison(self):
        i = base_inputs()
        for m in i["baba"]["models"]:
            if m["track"] == "fukushima":
                m["going_status"] = {"state": "usable", "label": "使える見込み",
                                     "without_forecast": {"logloss_gain_pct": 6.0, "brier_gain_pct": 10.0},
                                     "perfect_forecast": {"logloss_gain_pct": 50.0, "brier_gain_pct": 40.0}, "races": 400}
            elif m["track"] == "tokyo":
                m["going_status"] = {"state": "usable" if m["surface"] == "turf" else "waiting_forecast", "label": "x"}
        r = run(i)
        self.assertEqual(unit(r, "track_condition:track:fukushima")["state"], "ready_to_adopt")
        self.assertEqual(unit(r, "track_condition:track:tokyo")["state"], "research")
        drafts = list(p.issue_drafts(r, i["cycle"]))
        self.assertEqual([d["title"] for d in drafts if "fukushima" in d["unit_id"]],
                         ["[採用できます] 福島（track_condition:track:fukushima）"])


if __name__ == "__main__":
    unittest.main()


class TestClaudeEvidence(unittest.TestCase):
    def test_claude_screening_counts_races_and_weeks(self):
        import tempfile, json
        from pathlib import Path
        import e2e_validation.improvement_pipeline_v1 as ip
        with tempfile.TemporaryDirectory() as t:
            old = ip.CLAUDE_REVIEWS; ip.CLAUDE_REVIEWS = Path(t)
            try:
                for rid in ("2026-11-01-05-11", "2026-11-02-09-11", "2026-11-08-05-11", "2026-11-09-09-11"):
                    (Path(t) / f"{rid}.json").write_text(json.dumps({"race_id": rid, "failure_types": ["展開"]}))
                (Path(t) / "x.json").write_text(json.dumps({"race_id": "2026-11-08-06-11", "failure_types": ["能力"]}))
                r = ip.claude_screening("pace_positioning", 3, 2)
                self.assertEqual((r["races"], r["meetings"], r["met"]), (4, 2, True))
                self.assertFalse(ip.claude_screening("track_condition", 3, 2)["met"])
            finally:
                ip.CLAUDE_REVIEWS = old
