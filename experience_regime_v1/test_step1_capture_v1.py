import unittest
import json
from pathlib import Path
from experience_regime_v1.step1_capture_v1 import check_runners

class TestStrictStep1Capture(unittest.TestCase):
    def example(self):
        horses = {str(i): {"horse_number": i, "horse_name": "馬" + str(i)} for i in (1,2,3)}
        source = {"stage": "formal_prestart", "no_odds_used_to_change_marks": True,
                  "step1_ranking": [{"horse_number":i,"horse_name":"馬"+str(i),
                      "factor_grades":["A"]*9,"mark": mark, "win_probability":p}
                      for i,mark,p in ((1,"◎",0.5),(2,"○",0.3),(3,"▲",0.2))]}
        return source, {"experience": {"horses": horses}}

    def test_existing_oct31_real_formal_source_contract(self):
        root=Path(__file__).resolve().parents[1]
        cases=[
            ("2026-10-31-tokyo-11","2026-10-31-perseus-stakes",
             "v3.13-run41142182394-attempt1.json"),
            ("2026-10-31-kyoto-11","2026-10-31-fantasy-stakes",
             "v3.13-run41143212430-attempt1.json"),
        ]
        for research,formal,name in cases:
            with self.subTest(research=research):
                frozen=json.loads((root/"experience_regime_v1"/"collection"/
                  "2026-10-31"/"snapshots"/(research+".json")).read_text())
                source=json.loads((root/"e2e_validation"/"predictions"/
                  formal/name).read_text())
                rows=check_runners(source,frozen)
                self.assertEqual(len(rows),len(frozen["experience"]["horses"]))
                self.assertTrue(all(len(r["factor_grades"])==9 for r in rows))

    def test_valid_copies_only_actual_probabilities(self):
        source,frozen=self.example()
        result=check_runners(source,frozen)
        self.assertEqual([r["step1_rank"] for r in result], [1,2,3])
        self.assertNotIn("predicted_top3_probability",result[0])
        self.assertEqual(result[0]["predicted_win_probability"],0.5)

    def test_frozen_central_top3_marginal_is_not_invented(self):
        source,frozen=self.example()
        source["outcome_distributions"]={"central":[
            {"finish":[1,2,3],"probability":0.6},
            {"finish":[2,1,3],"probability":0.4},
        ]}
        result=check_runners(source,frozen)
        self.assertAlmostEqual(result[0]["predicted_top3_probability"],1)
        self.assertAlmostEqual(result[1]["predicted_top3_probability"],1)

    def test_invalid_frozen_central_distribution_fails(self):
        source,frozen=self.example()
        source["outcome_distributions"]={"central":[
            {"finish":[1,2,3],"probability":0.5}
        ]}
        with self.assertRaisesRegex(ValueError,"not_normalized"):
            check_runners(source,frozen)

    def test_missing_nine_grades_fails(self):
        source,frozen=self.example()
        source["step1_ranking"][0]["factor_grades"]=[]
        with self.assertRaisesRegex(ValueError,"nine_factor"):
            check_runners(source,frozen)

    def test_field_mismatch_fails(self):
        source,frozen=self.example()
        frozen["experience"]["horses"].pop("3")
        with self.assertRaisesRegex(ValueError,"field_mismatch"):
            check_runners(source,frozen)

    def test_odds_modified_forecast_refused(self):
        source,frozen=self.example()
        source["no_odds_used_to_change_marks"]=False
        with self.assertRaisesRegex(ValueError,"independent_STEP1"):
            check_runners(source,frozen)

    def test_invalid_probabilities_refused(self):
        source,frozen=self.example()
        source["step1_ranking"][0]["win_probability"]=0.9
        with self.assertRaisesRegex(ValueError,"not_normalized"):
            check_runners(source,frozen)

if __name__=="__main__":
    unittest.main()
