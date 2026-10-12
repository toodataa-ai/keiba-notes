import unittest
from e2e_validation.validate_experience_history_v312 import validate_known_gaps

A={"case":"e2e_validation/cases/a/case.json","sha":"a"*40,
   "race_id":"a","version":"v3.12","grade":"prospective_strict","error":"missing"}
B={"case":"e2e_validation/cases/b/case.json","sha":"b"*40,
   "race_id":"b","version":"v3.13","grade":"prospective_strict","error":"missing2"}

class ArchivedShadowGapGateTests(unittest.TestCase):
    def setUp(self):
        self.entries=[A,B]
        self.errors=[{k:e[k] for k in ("case","race_id","version","grade","error")} for e in self.entries]
        self.hash=lambda p:{"e2e_validation/cases/a/case.json":"a"*40,
                           "e2e_validation/cases/b/case.json":"b"*40}[p]
    def test_exact_baseline_allows_only_integrity_success(self):
        v=validate_known_gaps(self.errors,self.entries,self.hash)
        self.assertEqual(v["disclosed_archived_gaps"],2)
        self.assertFalse(v["shadow_promotable"])
    def test_new_missing_record_is_regression(self):
        with self.assertRaises(ValueError):
            validate_known_gaps(self.errors+[dict(self.errors[0],case="e2e_validation/cases/new/case.json")],self.entries,self.hash)
    def test_tampered_history_is_regression(self):
        with self.assertRaises(ValueError):
            validate_known_gaps(self.errors,self.entries,lambda p:"0"*40)
    def test_missing_known_error_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_known_gaps(self.errors[:-1],self.entries,self.hash)
    def test_changed_reason_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_known_gaps([dict(self.errors[0],error="unexplained"),self.errors[1]],self.entries,self.hash)

if __name__=="__main__":
    unittest.main()
