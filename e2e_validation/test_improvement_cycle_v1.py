import unittest
from e2e_validation.improvement_cycle_v1 import build

def mk(rid,week,txt="先行と馬場"):
    return {"id":rid,"scope":"jra-main","status":"reviewed","date":"2026-10-12",
            "result":{"official_url":"jra"},"performance":{"stake_yen":1},
            "review":txt,"settlements":[{"a":1}],"e2e_case":"case"}
def evaluate(races,proof_ids,meetings,shared=0,study=None):
    rs={"latest_formal_prompt_version":"v3.13","formal_grade_a":{"passed":True},"meetings":meetings,
        "shadow_research":{"prerace_evidence_gap_count":14,"evidence_gaps":[]}}
    e={"entries":[{"race_id":rid,"grade":"prospective_strict","proof":{"read_from_proof_commit":True}} for rid in proof_ids],
       "comparison":{"baseline":"v3.13","candidate":"challenger","strict_shared_cases":shared,
                     "minimum_strict_shared_cases":20,
                     "state":"ready_for_review" if shared>=20 else "insufficient_data"},"errors":[]}
    topics={"topics":[{"id":"pace","title":"展開","pattern":"先行","investigation":"test"}]}
    return build({"races":races},rs,e,rs["shadow_research"],
                 study or {"overall":{}},topics,{"experiments":[]})

class CycleTests(unittest.TestCase):
    def test_verified_complete_week_repeat_needed(self):
        weeks=[{"meeting_id":w,"dates":[],"expected_races":2,"formal_grade_a_review_state":"complete",
                "weekly_improvement_decision":"no_change","races":[{"race_id":rid} for rid in ids]}
               for w,ids in [("w1",["a","b"]),("w2",["c","d"])]]
        x=evaluate([mk(i,None) for i in "abcd"],"abcd",weeks)
        h=x["formal"]["hypotheses"][0]
        self.assertEqual(h["status"],"repeated_in_completed_meetings")
        self.assertEqual(h["race_observation_count"],4)
        self.assertFalse(h["ready_for_formal_promotion"])
    def test_unproven_and_unreviewed_are_not_valid(self):
        weeks=[{"meeting_id":"w1","dates":[],"expected_races":2,"formal_grade_a_review_state":"pending",
                "weekly_improvement_decision":"not_evaluated","races":[{"race_id":"a"},{"race_id":"b"}]}]
        x=evaluate([mk("a",None),mk("b",None)],["a"],weeks)
        self.assertEqual(x["formal"]["strict_verified_reviews"],1)
        self.assertNotEqual(x["formal"]["hypotheses"][0]["status"],"repeated_in_completed_meetings")
    def test_research_counts_not_promoted(self):
        x=evaluate([],[],[],study={"overall":{"E0":{"horse_observations":100,"races":3,
            "win_prediction_observations":0,"top3_prediction_observations":0}}})
        self.assertEqual(x["research"]["regimes"][0]["status"],"prediction_evidence_incomplete")
        self.assertFalse(x["gates"]["automated_prompt_change"])
        self.assertFalse(x["research"]["regimes"][0]["ready_for_formal_promotion"])
    def test_research_screening_needs_predictions_not_only_outcomes(self):
        policy={"policy":{"research_initial_diagnostic":{
            "win_probability_with_result_per_group":30,
            "top3_probability_with_result_per_group":30,
            "minimum_distinct_races":3,"minimum_separate_weeks":2}}}
        rs={"latest_formal_prompt_version":"v3.13","formal_grade_a":{"passed":True},
            "meetings":[],"shadow_research":{"prerace_evidence_gap_count":0}}
        e={"entries":[],"errors":[],"comparison":{"baseline":"v3.0","candidate":"v3.1",
           "strict_shared_cases":0,"minimum_strict_shared_cases":20,"state":"insufficient_data"}}
        study={"week_id":"2026-10-24","overall":{"E0":{"horse_observations":500,"races":20,
           "win_prediction_observations":0,"top3_prediction_observations":0}}}
        x=build({"races":[]},rs,e,rs["shadow_research"],study,{"topics":[]},
                {"experiments":[]},policy)
        r=x["research"]["regimes"][0]
        self.assertEqual(r["horse_observation_count"],500)
        self.assertEqual(r["strict_win_probability_observations"],0)
        self.assertFalse(r["diagnostic_initial_target"]["minimum_data_counts_observed"])
        self.assertFalse(r["ready_for_formal_promotion"])
    def test_separate_research_weeks_are_labeled(self):
        rs={"latest_formal_prompt_version":"v3.13","formal_grade_a":{"passed":True},
            "meetings":[],"shadow_research":{"prerace_evidence_gap_count":0}}
        e={"entries":[],"errors":[],"comparison":{"baseline":"v3.0","candidate":"v3.1"}}
        study={"week_id":"2026-10-24","overall":{"E1":{"horse_observations":21}},
               "history_by_week":{"2026-10-17":{"overall":{"E1":{"horse_observations":45}}}}}
        x=build({"races":[]},rs,e,rs["shadow_research"],study,{"topics":[]},{"experiments":[]})
        r=x["research"]["regimes"][1]
        self.assertEqual(r["horse_observation_count"],21)
        self.assertEqual(r["cumulative_reviewed_horse_observations"],66)
        self.assertEqual(r["cumulative_weeks_with_observations"],2)
    def test_topic_screen_counts_only_completed_meetings(self):
        meetings = [
            {"meeting_id":"done","formal_grade_a_review_state":"complete",
             "expected_races":2,"races":[{"race_id":"a"},{"race_id":"b"}]},
            {"meeting_id":"pending","formal_grade_a_review_state":"pending",
             "expected_races":1,"races":[{"race_id":"c"}]}]
        x=evaluate([mk(i,None) for i in ("a","b","c")],["a","b","c"],meetings)
        h=x["formal"]["hypotheses"][0]
        self.assertEqual(h["race_observation_count"],3)
        self.assertEqual(h["next_decision"]["screening"]["qualifying_race_reviews"],2)
        self.assertEqual(h["next_decision"]["screening"]["remaining_qualifying_race_reviews"],1)
        self.assertEqual(h["next_decision"]["screening"]["remaining_completed_meetings"],1)
        self.assertEqual(h["next_decision"]["screening"]["pending_week_mentions_not_yet_qualifying"],1)
        self.assertFalse(h["next_decision"]["screening"]["ready_to_design_experiment"])
    def test_race_estimates_are_not_historic_evidence(self):
        rs={"latest_formal_prompt_version":"v3.13","formal_grade_a":{"passed":True},
            "meetings":[],"shadow_research":{"prerace_evidence_gap_count":0}}
        e={"entries":[],"errors":[],"comparison":{"baseline":"v3.0","candidate":"v3.1"}}
        runs={"collection_runs":{
            "one":{"complete_evidence_races":4,"prerace_proof_valid_races":4,
                   "regimes":{"E0":{"races":1,"horse_observations":16},
                              "E1":{"races":1,"horse_observations":12},
                              "E2":{"races":2,"horse_observations":24}}},
            "two":{"complete_evidence_races":4,"prerace_proof_valid_races":4,
                   "regimes":{"E0":{"races":1,"horse_observations":14},
                              "E1":{"races":2,"horse_observations":20},
                              "E2":{"races":3,"horse_observations":38}}},
        }}
        x=build({"races":[]},rs,e,rs["shadow_research"],{"overall":{}},
                {"topics":[]},{"experiments":[]},None,runs)
        regimes=x["research"]["regimes"]
        self.assertEqual(regimes[0]["next_decision"]["additional_races_estimate"],3)
        self.assertEqual(regimes[1]["next_decision"]["additional_races_estimate"],3)
        self.assertEqual(regimes[2]["next_decision"]["additional_races_estimate"],3)
        self.assertIsNone(regimes[0]["next_decision"]["future_eligible_race_count"])
        self.assertEqual(regimes[0]["strict_win_probability_observations"],0)
        self.assertTrue(regimes[0]["next_decision"]["record_level_dedup_and_proof_audit_required"])
    def test_stale_version_pair_not_eligible(self):
        rs={"latest_formal_prompt_version":"v3.13","formal_grade_a":{"passed":True},
            "meetings":[],"shadow_research":{"prerace_evidence_gap_count":0}}
        e={"entries":[],"errors":[],"comparison":{"baseline":"v3.0","candidate":"v3.1",
            "strict_shared_cases":25,"minimum_strict_shared_cases":20,
            "state":"ready_for_review"}}
        x=build({"races":[]},rs,e,rs["shadow_research"],{"overall":{}},
                {"topics":[]},{"experiments":[]})
        self.assertFalse(x["formal"]["comparison"]["pair_matches_current_formal"])
        self.assertFalse(x["gates"]["formal_candidate_e2e_ready"])
    def test_paired_threshold_does_not_auto_approve(self):
        x=evaluate([],[],[],shared=20)
        self.assertTrue(x["gates"]["formal_candidate_e2e_ready"])
        self.assertTrue(x["gates"]["a_b_c_manual_approval_required"])
        self.assertFalse(x["gates"]["automated_prompt_change"])

if __name__=="__main__":
    unittest.main()
