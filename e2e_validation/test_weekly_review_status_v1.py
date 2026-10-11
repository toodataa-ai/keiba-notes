import unittest
from e2e_validation.weekly_review_status_v1 import evaluate

def race(rid,reviewed):
    x={"id":rid,"scope":"jra-main","date":"2026-10-12",
       "status":"reviewed" if reviewed else "predicted"}
    if reviewed:
        x.update(result={"official_url":"official"},settlements=[{"id":"a"}],
                 performance={"total":1},review="checked",e2e_case="case.json")
    return x

class MeetingReviewTest(unittest.TestCase):
    def setUp(self):
        self.calendar={"meetings":[{"meeting_id":"holiday","dates":["2026-10-11","2026-10-12"],
                                    "expected_main_race_ids":["sun","mon"]}]}
        self.e2e={"errors":[],"entries":[{"race_id":id,"grade":"prospective_strict",
                                         "proof":{"read_from_proof_commit":True}} for id in ("sun","mon")],
                  "comparison":{"state":"insufficient_data"},"case_counts":{"strict":2}}
        self.shadow={"errors":[{"race_id":"sun","version":"v3.12","error":"missing evidence"}],"versions":{}}
    def test_holiday_monday_holds_week_decision(self):
        d=evaluate({"races":[race("sun",True),race("mon",False)]},self.e2e,self.shadow,self.calendar,"v3.13")
        m=d["meetings"][0]
        self.assertEqual(m["weekly_improvement_decision"],"not_evaluated")
        self.assertEqual(m["formal_grade_a_review_state"],"pending")
        self.assertEqual(d["shadow_research"]["state"],"evidence_incomplete")
        self.assertTrue(d["formal_grade_a"]["passed"])
    def test_full_review_without_paired_comparison_keeps_prompt(self):
        d=evaluate({"races":[race("sun",True),race("mon",True)]},self.e2e,self.shadow,self.calendar,"v3.13")
        self.assertEqual(d["meetings"][0]["weekly_improvement_decision"],"no_change")
        self.assertEqual(d["meetings"][0]["formal_grade_a_review_state"],"complete")
        self.assertEqual(d["shadow_research"]["state"],"evidence_incomplete")
    def test_unverified_proof_cannot_complete(self):
        e2e=dict(self.e2e,entries=self.e2e["entries"][:1])
        d=evaluate({"races":[race("sun",True),race("mon",True)]},e2e,self.shadow,self.calendar,"v3.13")
        self.assertEqual(d["meetings"][0]["weekly_improvement_decision"],"not_evaluated")

if __name__=="__main__":
    unittest.main()
