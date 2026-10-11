import copy
import unittest
from e2e_validation.evaluate import normalize_formal_v312_for_e2e

class V313PrestartAdapterTest(unittest.TestCase):
    def test_v313_prospective_projection_never_modifies_source(self):
        p={"race_id":"2026-10-12-october-stakes","stage":"formal_prestart",
           "prompt_version":"v3.13",
           "step1_fixed_at":"2026-10-12T06:52:59+09:00",
           "final_bets_fixed_at":"2026-10-12T06:55:00+09:00",
           "market_coverage_snapshot_at":"2026-10-12T06:54:30+09:00",
           "step1_ranking":[{"horse_number":1,"mark":"◎"},
                            {"horse_number":2,"mark":"○"},
                            {"horse_number":3,"mark":"▲"}],
           "final_bets":[{"id":"B01","type":"単勝","selection":[1],"stake_yen":300}],
           "race_context":{"race_no":11}}
        original=copy.deepcopy(p)
        v=normalize_formal_v312_for_e2e(p)
        self.assertEqual(p,original)
        self.assertEqual(v["prompt_manifest"],"e2e_validation/manifests/v3.13.json")
        self.assertEqual(v["marks"],{"win":1,"second":2,"third":3})
        self.assertIsNone(v["step1_ranking"])
        self.assertEqual(v["bets"][0]["stake_yen"],300)
        self.assertEqual(v["information_cutoff_at"],v["generated_at"])
    def test_reject_bad_triple_seal(self):
        p={"prompt_version":"v3.13","stage":"formal_prestart",
           "step1_ranking":[{"horse_number":1,"mark":"◎"},{"horse_number":2,"mark":"○"},{"horse_number":3,"mark":"▲"}],
           "final_bets":[{"id":"B1","type":"単勝","selection":[1],"stake_yen":100}]}
        from e2e_validation.evaluate import ValidationError
        with self.assertRaises(ValidationError):
            normalize_formal_v312_for_e2e(p)

if __name__=="__main__":
    unittest.main()
