#!/usr/bin/env python3
"""Regression gate for an isolated JRA formal-only one-shot workflow."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[2]
def read(path):return (root/path).read_text(encoding="utf-8")
source=read(".github/scripts/jra-gather-live-v314.py")
copy=read(".github/scripts/jra-gather-live-v314-formal-only.py")
old="request_path=safe_path(a.request,'e2e_validation/requests/v314/')"
new="request_path=safe_path(a.request,'.github/requests/jra-formal-only-v314/')"
assert source.count(old)==1,"original collector entrypoint changed"
assert copy==source.replace(old,new),"adapter must differ ONLY in request directory"
sha=subprocess.run(["git","hash-object",".github/scripts/jra-gather-live-v314.py"],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
assert sha=="b1624ff0304b40fe34575f711023e3aceb2aa0d5","immutable source collector changed"
wf=read(".github/workflows/jra-generic-formal-only-v314.yml")
oldwf=read(".github/workflows/jra-generic-one-shot-v314.yml")
assert subprocess.run(["git","hash-object",".github/workflows/jra-generic-one-shot-v314.yml"],cwd=root,capture_output=True,text=True,check=True).stdout.strip()=="d239b9a88a26330c74c262a209db596253f800d3","immutable original workflow changed"
required=[
 ".github/requests/jra-formal-only-v314/*.json",
 "jra-gather-live-v314-formal-only.py",
 "jra-check-fresh-quotes-v313-exec.py",
 "jra-prestart-pipeline-v313.mjs",
 "weasyprint==68.0",
 "validate-jra-pdf-content-v313.py",
 "jra-publish-live-v313.py",
 "cmp -s",
 "git add -- \"$INPUT_PATH\" \"$SNAPSHOT\"",
]
for token in required:assert token in wf,("missing formal validation / seal / publication",token)
for forbidden in ("python3 experience_regime_v1/","SHADOW_EVIDENCE","shadow-collection-audits","gh workflow run experience-regime-step1-freeze-v1.yml"):
 assert forbidden not in wf,("E0/E1/E2 side effect persists",forbidden)
assert ".github/requests/jra-formal-only-v314/*.json" in wf
assert "e2e_validation/requests/v314-formal-only" not in wf
assert "experience_regime_v1/prestart_collection_audit_v1.py" in oldwf
assert "gh workflow run experience-regime-step1-freeze-v1.yml" in oldwf
assert "e2e_validation/requests/v314/" in source and ".github/requests/jra-formal-only-v314/" in copy
assert wf.count("jra-check-fresh-quotes-v313-exec.py")>=2,"before-proof recheck missing"
assert "jra-prerace-formal-3action-v315.yml" not in wf,"separate formal purchase phase must not be silently skipped or represented as completed"
print("PASS_JRA_FORMAL_ONLY_ISOLATION_AND_IMMUTABLE_MODEL_GATES")
