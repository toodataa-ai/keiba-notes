import unittest
from datetime import datetime,timezone,timedelta
from experience_regime_v1.prestart_collection_audit_v1 import audit

NOW=datetime(2026,10,12,1,0,tzinfo=timezone.utc)
def forecast():
    return {"race_id":"future-jra-race",
            "race_context":{"start_at":(NOW+timedelta(hours=8)).isoformat()},
            "step1":{"runners":[{"horse_number":1},{"horse_number":2}]}}

class PreraceShadowAuditTest(unittest.TestCase):
    def test_missing_data_is_disclosed_not_synthesized(self):
        report=audit(forecast(),b"original prereace input",NOW)
        self.assertFalse(report["usable_for_e012_shadow"])
        self.assertIn("race_context.race_category",report["missing_prerace_evidence"])
        self.assertIn("experience.horses[1]",report["missing_prerace_evidence"])
        self.assertTrue(report["rules"]["formal_step1_and_final_bets_unaffected"])
    def test_valid_audited_prestart_experience(self):
        d=forecast()
        d["race_context"].update(race_category="graded",sample_origin="official_prediction")
        d["experience"]={"horses":{
            "1":{"starts_before_race":0,"regime":"E0","source_url":"https://www.jra.go.jp/source1","observed_at":NOW.isoformat()},
            "2":{"starts_before_race":6,"regime":"E2","source_url":"https://www.jra.go.jp/source2","observed_at":NOW.isoformat()}}}
        self.assertTrue(audit(d,b"original input",NOW)["usable_for_e012_shadow"])
    def test_poststart_audit_is_forbidden(self):
        with self.assertRaises(ValueError):
            audit(forecast(),b"x",NOW+timedelta(hours=9))

if __name__=="__main__":
    unittest.main()
