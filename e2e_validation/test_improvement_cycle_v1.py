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
    def test_paired_threshold_does_not_auto_approve(self):
        x=evaluate([],[],[],shared=20)
        self.assertTrue(x["gates"]["formal_candidate_e2e_ready"])
        self.assertTrue(x["gates"]["a_b_c_manual_approval_required"])
        self.assertFalse(x["gates"]["automated_prompt_change"])

if __name__=="__main__":
    unittest.main()
