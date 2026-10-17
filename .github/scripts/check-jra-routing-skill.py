#!/usr/bin/env python3
"""Read-only validation that routing policy remains discoverable and coherent."""
import json
from pathlib import Path
r=Path(__file__).resolve().parents[2]
a=(r/'AGENTS.md').read_text()
s=(r/'.github/skills/keiba-site-change-routing/SKILL.md').read_text()
c=(r/'.github/skills/keiba-site-change-routing/references/release-checklist.md').read_text()
l=(r/'.github/lab/README.md').read_text()
o=(r/'docs/operations/JRA_UI_APPROVAL_DATA_AUTO_RELEASE.md').read_text()
assert s.startswith('---\nname: keiba-site-change-routing\n')
assert 'keiba-site-change-routing/SKILL.md' in a
for term in ['STAGING','LAB','DATA','main/docs','ユーザー','final_bets','staging-baseline-v2.py','明示承認']:
 assert term in s,term
for term in ['STAGING','LAB','DATA','承認','tree SHA']:
 assert term in c,term
assert 'keiba-site-change-routing' in l and 'keiba-site-change-routing' in o
f=json.loads((r/'.github/lab/feature-registry.json').read_text())['features']
assert any(x['id']=='simulator' and x['preview_path'].startswith('lab/') for x in f)
assert any(x['id']=='experience-regime' and x['phase']=='released' for x in f)
assert (r/'docs/staging/this-week.html').is_file()
assert (r/'docs/lab/race-simulator.html').is_file()
print('PASS_KEIBA_ROUTING_SKILL_STAGING_LAB_DATA_APPROVAL_AND_LATEST_SITE')
