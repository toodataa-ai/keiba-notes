import unittest

from e2e_validation.challengers import pace_v1
from e2e_validation.experiment_runner_v1 import git_blob_sha, score, top3_probs, ROOT, read, REGISTRY
from e2e_validation.improvement_cycle_v1 import build


def horse(no, p, corners, mark=""):
    runs = [{"source_excerpt": f"2026年1月1日 東京 X 1 着 10 頭 {no} 番 1 番人気 騎手 57.0 kg 1600芝 1:33.0 良 100 480 kg {c} 3F 34.0 Y (0.1)"}
            for c in corners]
    return {"horse_number": no, "win_probability": p, "mark": mark, "past_performances": runs}


class PaceChallengerTests(unittest.TestCase):
    def test_style_from_first_corner(self):
        self.assertEqual(pace_v1.runner_style(horse(1, .1, ["1 1", "2 2"]))[1], "front")
        self.assertEqual(pace_v1.runner_style(horse(1, .1, ["10 9", "9 9"]))[1], "closer")
        self.assertEqual(pace_v1.runner_style(horse(1, .1, []))[1], "unknown")

    def test_slow_pace_favors_lone_leader_and_sums_to_one(self):
        f = {"step1_ranking": [horse(1, .25, ["1 1"]), horse(2, .25, ["5 5"]),
                               horse(3, .25, ["10 10"]), horse(4, .25, [])]}
        out = pace_v1.predict(f)
        self.assertEqual(out["pace_forecast"], "S")
        p = {r["horse_number"]: r["challenger_win_probability"] for r in out["runners"]}
        self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertGreater(p[1], .25)
        self.assertLess(p[3], .25)
        self.assertEqual(out["marks"]["◎"], 1)

    def test_high_pace_favors_closers(self):
        f = {"step1_ranking": [horse(i, .1, ["1 1"]) for i in range(1, 6)]
             + [horse(i, .1, ["10 10"]) for i in range(6, 11)]}
        out = pace_v1.predict(f)
        self.assertEqual(out["pace_forecast"], "H")
        p = {r["horse_number"]: r["challenger_win_probability"] for r in out["runners"]}
        self.assertGreater(p[6], p[1])

    def test_requires_sealed_probabilities(self):
        with self.assertRaises(ValueError):
            pace_v1.predict({"step1_ranking": [{"horse_number": 1}]})


class RunnerTests(unittest.TestCase):
    def test_top3_probabilities_sum_to_three(self):
        t = top3_probs({1: .4, 2: .3, 3: .2, 4: .1})
        self.assertAlmostEqual(sum(t.values()), 3.0)
        self.assertTrue(all(0 <= v <= 1 + 1e-9 for v in t.values()))

    def test_score_ignores_scratched_runner(self):
        s = score({1: .5, 2: .3, 3: .2, 9: .5}, 1, [1, 2, 3])
        self.assertEqual(s["honmei_win"], 1)
        self.assertAlmostEqual(s["winner_probability"], .5)

    def test_registered_code_is_pinned(self):
        for exp in read(REGISTRY)["experiments"]:
            self.assertEqual(git_blob_sha(ROOT / exp["code"]["path"]), exp["code"]["git_blob_sha"],
                             "challenger code changed: register a new experiment instead")

    def test_cycle_reports_registered_challenger(self):
        rs = {"latest_formal_prompt_version": "v3.13", "formal_grade_a": {"passed": True},
              "meetings": [], "shadow_research": {"prerace_evidence_gap_count": 0}}
        e = {"entries": [], "errors": [], "comparison": {}}
        topics = {"topics": [{"id": "pace", "title": "展開", "pattern": "先行", "investigation": "t"}]}
        exps = {"experiments": [{"id": "EXP-1", "title": "t", "hypothesis_ids": ["pace"],
                                 "baseline": "v3.13", "challenger": "c", "status": "collecting"}]}
        status = {"experiments": [{"id": "EXP-1", "minimum_prospective_pairs": 20,
                                   "remaining_prospective_pairs": 13, "prospective": {"pairs": 7}}]}
        x = build({"races": []}, rs, e, rs["shadow_research"], {"overall": {}}, topics, exps,
                  experiment_status=status)
        h = x["formal"]["hypotheses"][0]
        self.assertEqual(h["next_decision"]["stage"], "collect_challenger_pairs")
        self.assertFalse(h["next_decision"]["formal_comparison"]["challenger_not_yet_registered"])
        self.assertEqual(h["next_decision"]["formal_comparison"]["remaining_paired_races"], 13)
        self.assertEqual(x["experiments"][0]["prospective_pairs"], 7)
        self.assertFalse(x["gates"]["automated_prompt_change"])


if __name__ == "__main__":
    unittest.main()
