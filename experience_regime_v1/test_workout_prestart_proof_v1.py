"""No online fetching; deterministic authorization/cutoff/integrity regression."""
from __future__ import annotations
import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from experience_regime_v1.workout_prestart_proof_v1 import (
    build_commitment, permission_gate, validate_captured, write_new_commitment)

NOW=datetime.fromisoformat("2026-11-15T08:00:00+09:00")
START="2026-11-15T15:40:00+09:00"
URL="https://umasiru.com/archives/12345"
POLICY={
    "schema_version":1,
    "default_decision":"block_automated_git_commit_until_explicit_reuse_grant",
    "sources":[{
        "host":"umasiru.com",
        "approved_article_prefix":"/archives/",
        "automatic_reuse":"permission_unverified",
        "public_redistribution":"not_approved",
        "permission_evidence_url":None,
        "permission_granted_at":None,
        "rights_owner_verified":False
    }]
}
CAPTURE={
    "race_id":"2026-11-15-tokyo-11","week_id":"2026-11-14",
    "start_at":START,
    "source":{"url":URL,"fetched_at":"2026-11-15T07:00:00+09:00",
              "article_published_at":"2026-11-13T08:00:00+09:00",
              "html_sha256":"c"*64},
    "frozen_roster_proof":{"commit_sha":"a"*40, "sha256":"b"*64},
    "prediction_rank_grade_bets_unchanged":True,
    "production_effect":False,
    "no_odds_or_results_used":True,
    "workout_factor_grades":None,
    "workout_score_calibrated":False,
    "before_post":True,
    "verified_horses":1,"roster_horses":2,
    "observations":[{
        "horse_number":1,"horse_name":"実験用A",
        "workouts":[{"session":"最終追切","observed_split_count":4,
                     "split_seconds":{"6F":None,"5F":66.3,"4F":52.1,"3F":36.6,"1F":11.7}}]
    }]
}


def approved():
    p=copy.deepcopy(POLICY)
    p["sources"][0].update(
        automatic_reuse="explicitly_granted",
        permission_evidence_url="https://publisher.example/license/workout-reuse",
        permission_granted_at="2026-11-01T12:00:00+09:00",
        rights_owner_verified=True)
    return p


class TestWorkoutProof(unittest.TestCase):
    def test_unverified_rights_always_block_before_file_write(self):
        with self.assertRaisesRegex(PermissionError,"PUBLISHER_PERMISSION_NOT_VERIFIED"):
            build_commitment(CAPTURE,now=NOW,policy=POLICY)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PermissionError,"PUBLISHER_PERMISSION_NOT_VERIFIED"):
                write_new_commitment(Path(tmp),CAPTURE,NOW,POLICY)
            self.assertEqual(list(Path(tmp).rglob("*")),[])

    def test_fake_permission_without_source_evidence_is_rejected(self):
        p=approved()
        p["sources"][0]["permission_evidence_url"]=None
        with self.assertRaisesRegex(ValueError,"unverified_permission_document"):
            permission_gate(URL,p)

    def test_factual_hash_only_no_horse_or_clocks_in_git_proof(self):
        p=approved()
        obj=build_commitment(CAPTURE,now=NOW,policy=p)
        self.assertEqual(obj["research_horses_with_source"],1)
        self.assertEqual(obj["research_workout_sessions_with_source"],1)
        self.assertTrue(obj["formal_step1_2_and_bets_untouched"])
        self.assertFalse(obj["production_effect"])
        self.assertEqual(obj["proof_final_status"],"PENDING_REAL_FIRST_GIT_COMMIT_AND_TIMESTAMP_CHECK")
        self.assertNotIn("horse_name",json.dumps(obj))
        self.assertNotIn("11.7",json.dumps(obj))
        self.assertIn("factual_observations_canonical_sha256",obj)
        with tempfile.TemporaryDirectory() as tmp:
            output=write_new_commitment(Path(tmp),CAPTURE,NOW,p)
            self.assertTrue(output.exists())
            self.assertIn("2026-11-15-tokyo-11",str(output))
            with self.assertRaises(FileExistsError):
                write_new_commitment(Path(tmp),CAPTURE,NOW,p)

    def test_poststart_source_or_commit_is_rejected(self):
        p=approved()
        with self.assertRaisesRegex(ValueError,"after_start_capture_or_commit"):
            build_commitment(CAPTURE,now=datetime.fromisoformat("2026-11-15T15:41:00+09:00"),policy=p)
        late=copy.deepcopy(CAPTURE)
        late["source"]["fetched_at"]="2026-11-15T15:40:00+09:00"
        with self.assertRaisesRegex(ValueError,"after_start_capture_or_commit"):
            build_commitment(late,now=NOW,policy=p)

    def test_same_race_results_and_unverified_grades_forbidden(self):
        p=approved()
        for field,value in [("production_effect",True),("no_odds_or_results_used",False),
                            ("workout_factor_grades",{"7":"A"}),("workout_score_calibrated",True),
                            ("prediction_rank_grade_bets_unchanged",False)]:
            c=copy.deepcopy(CAPTURE);c[field]=value
            with self.assertRaises(ValueError,msg=field):
                build_commitment(c,now=NOW,policy=p)

    def test_duplicate_horse_and_empty_clock_forbidden(self):
        p=approved()
        x=copy.deepcopy(CAPTURE)
        x["observations"].append(copy.deepcopy(x["observations"][0]))
        x["verified_horses"]=2
        with self.assertRaisesRegex(ValueError,"duplicate_or_invalid_horse"):
            build_commitment(x,now=NOW,policy=p)
        y=copy.deepcopy(CAPTURE)
        y["observations"][0]["workouts"][0]["split_seconds"]["1F"]=None
        y["observations"][0]["workouts"][0]["split_seconds"].update({"5F":None,"4F":None,"3F":None})
        with self.assertRaisesRegex(ValueError,"source_workout_not_numeric_valid"):
            build_commitment(y,now=NOW,policy=p)

    def test_offline_digests_deterministic(self):
        p=approved()
        a=build_commitment(CAPTURE,now=NOW,policy=p)
        b=build_commitment(CAPTURE,now=NOW,policy=p)
        self.assertEqual(a["factual_observations_canonical_sha256"],
                         b["factual_observations_canonical_sha256"])
        changed=copy.deepcopy(CAPTURE)
        changed["observations"][0]["workouts"][0]["split_seconds"]["1F"]=11.8
        c=build_commitment(changed,now=NOW,policy=p)
        self.assertNotEqual(a["factual_observations_canonical_sha256"],
                            c["factual_observations_canonical_sha256"])


if __name__=="__main__":
    unittest.main()
