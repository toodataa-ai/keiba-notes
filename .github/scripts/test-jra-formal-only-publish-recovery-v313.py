#!/usr/bin/env python3
"""Gate prereace only Git-proof recovery from an already sealed JRA v3.13 source."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]
source=(root/".github/workflows/jra-formal-only-publish-recovery-v313.yml").read_text(encoding="utf8")
for piece in (
 ".github/requests/jra-formal-only-v313-publish-recovery/*.json",
 "git','rev-parse',proof+':'+snap",
 "git','hash-object',snap",
 "pending_git_proof",
 "race started; cannot publish",
 "original_proof_commit",
 "jra-prestart-pipeline-v313.mjs --seal",
 "validate-jra-portfolio-v313.mjs",
 "weasyprint==68.0",
 "validate-jra-pdf-layout.py",
 "jra-publish-live-v313.py",
 "cmp -s",
):
 assert piece in source,('recovery must not bypass mandatory gate',piece)
for prohibited in (
 "python3 experience_regime_v1/",
 "gh workflow run experience-regime",
 "e2e_validation/requests/recovery",
 "--refresh-all",
 "git push --force",
 "git reset --hard",
):
 assert prohibited not in source,('forbidden E012 or unsafe recovery action',prohibited)
assert "git rebase --abort" in source
assert "docs/data/races.json" in source
print("PASS_JRA_V313_PRESERVE_PROOF_PUBLICATION_ONLY_RECOVERY")
