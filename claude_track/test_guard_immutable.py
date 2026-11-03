import unittest
from claude_track.guard_immutable import violations

P = "claude_track/predictions/r1/a.json"

class T(unittest.TestCase):
    def test_add_ok(self): self.assertEqual(violations([f"A\t{P}"]), [])
    def test_modify_ng(self): self.assertEqual(len(violations([f"M\t{P}"])), 1)
    def test_delete_ng(self): self.assertEqual(len(violations([f"D\t{P}"])), 1)
    def test_rename_ng(self): self.assertEqual(len(violations([f"R100\t{P}\tclaude_track/x.json"])), 1)
    def test_move_in_ng(self): self.assertEqual(len(violations([f"R090\tdocs/a.json\t{P}"])), 1)
    def test_other_paths_ok(self): self.assertEqual(violations(["M\te2e_validation/x.json", "M\tclaude_track/README.md"]), [])

if __name__ == "__main__": unittest.main()
