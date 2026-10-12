import unittest
from e2e_validation.stabilize_public_reports import stabilize

class TimestampStabilityTests(unittest.TestCase):
    def test_same_content_stable(self):
        prior={"generated_at":"old","races":[{"generated_at":"old-child","state":"complete"}]}
        current={"generated_at":"new","races":[{"generated_at":"new-child","state":"complete"}]}
        self.assertEqual(stabilize(current,prior),prior)
    def test_changed_evidence_never_suppressed(self):
        prior={"generated_at":"old","state":"pending"}
        current={"generated_at":"new","state":"complete"}
        self.assertEqual(stabilize(current,prior),current)
    def test_nested_unchanged_review_time_preserved(self):
        prior={"generated_at":"old","review":{"generated_at":"old-child","status":"ok"},"state":0}
        now={"generated_at":"new","review":{"generated_at":"new-child","status":"ok"},"state":1}
        v=stabilize(now,prior)
        self.assertEqual(v["generated_at"],"new")
        self.assertEqual(v["review"]["generated_at"],"old-child")

if __name__=="__main__":
    unittest.main()
