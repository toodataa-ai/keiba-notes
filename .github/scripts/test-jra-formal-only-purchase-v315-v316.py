#!/usr/bin/env python3
"""Verify copied formal purchase and stake workflows differ only in safe trigger isolation."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[2]
def content(p):return (root/p).read_text(encoding="utf8")
def sha(p):
    return subprocess.run(["git","hash-object",p],cwd=root,text=True,capture_output=True,check=True).stdout.strip()
oldv315=".github/workflows/jra-prerace-formal-3action-v315.yml"
oldv316=".github/workflows/jra-prerace-formal-stake-v316.yml"
assert sha(oldv315)=="b6990e696aa9c451ea1c8cac7d7abda2b2d31e45","approved v3.15 workflow mutated"
assert sha(oldv316)=="03cd69e099c48091b857c33289ab84fa2ebd53fa","approved v3.16 workflow mutated"
old_name="JRA formal v3.15 PURCHASE 3 actions + mid/large, fully audited prestart replacement"
new_name="JRA formal-only v3.15 PURCHASE 3 actions + mid/large audited prestart replacement"
name316="name: JRA official v3.16 variable-stake prestart post-v3.15 promotion"
new316="name: JRA official formal-only v3.16 variable-stake post-v3.15 promotion"
base315=content(oldv315)
base316=content(oldv316)
new315=content(".github/workflows/jra-prerace-formal-3action-formal-only-v315.yml")
new316actual=content(".github/workflows/jra-prerace-formal-stake-formal-only-v316.yml")
assert base315.count(old_name)==1 and base316.count(old_name)==1
assert new315==base315.replace(old_name,new_name).replace("e2e_validation/requests/v315",".github/requests/jra-formal-only-v315"),"v3.15 must only change request trigger path and workflow name"
assert new316actual==base316.replace(old_name,new_name).replace(name316,new316),"v3.16 must only change source workflow name"
assert ".github/requests/jra-formal-only-v315/*.json" in new315
assert "e2e_validation/requests/v315/*.json" not in new315
for token in ("validate-jra-pdf-layout.py","weasyprint==68.0","jra-build-formal-3action-v315.mjs","jra-promote-formal-3action-v315.py","cmp -s"):
    assert token in new315,("v3.15 approval gate missing",token)
for token in ("jra-build-formal-stake-v316.mjs","weasyprint==68.0","validate-jra-pdf-layout.py"):
    assert token in new316actual,("v3.16 approval gate missing",token)
for w in (new315,new316actual):
    assert "gh workflow run experience-regime" not in w
    assert "python3 experience_regime_v1/" not in w
print("PASS_JRA_V315_V316_FORMAL_ONLY_FORKS_AND_IMMUTABLE_SOURCE")
