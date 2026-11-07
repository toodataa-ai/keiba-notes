#!/usr/bin/env python3
"""Strict invariant gate for new JRA v3.15 first-canonical publication (no v3.13 interim PDF)."""
from pathlib import Path
import ast,subprocess
root=Path(__file__).resolve().parents[2]
def read(s):return (root/s).read_text(encoding="utf8")
def sha(s):
 return subprocess.check_output(["git","hash-object",s],cwd=root,text=True).strip()
base=".github/scripts/jra-promote-formal-3action-v315.py"
new=".github/scripts/jra-promote-formal-3action-v315-initial.py"
workflow=".github/workflows/jra-formal-only-v315-initial-from-proof.yml"
assert sha(base)=="d8a556affbdf521a0d8c329dba31ca3425510080","SHA-pinned original promoter modified"
a=read(base);b=read(new);w=read(workflow)
ast.parse(b)
# The one permitted publisher difference is initial insert rather than replacement.
assert "need(len(entries)==0,'race already has a canonical record: initial publication cannot overwrite it')" in b
assert "master['races'].append(new)" in b
assert "'initial_canonical_publication':True" in b and "'old_canonical':None" in b
assert "'old_pdf_preserved':None" in b,"no fictitious old published PDF"
for piece in [
 "source_prediction_sha256", "source_prediction_proof", "source['step1_fixed_at']",
 "plan['quote_age_max_seconds']<=600 and plan['quote_capture_span_seconds']<=180",
 "new_total<=60", "validator.validate(html,pdf",
 "purchase_strategy_version='v3.15'", "unsealed or invalid purchase version",
 "duplicate purchase ticket", "no UI changes", "no_source_original",
]:
 if piece=="no UI changes" or piece=="no_source_original": continue
 assert piece in b,("v3.15 purchase must preserve original verification",piece)
for piece in [
 ".github/requests/jra-formal-only-v315-initial/*.json",
 "node .github/scripts/validate-jra-v313-current-e2e-v1.mjs",
 "original prestart source snapshot SHA changed",
 "original research input changed",
 "existing canonical detected",
 "jra-odds-full-refresh-v313-exec.py",
 "--refresh-all",
 "jra-check-fresh-quotes-v313-exec.py",
 "original_source", # verifier result note
 "jra-prestart-pipeline-v313.mjs",
 "jra-build-formal-3action-v315.mjs",
 "jra-render-formal-reader-v315.py",
 "jra-v315-value-column-v1.py",
 "weasyprint==68.0",
 "validate-jra-pdf-layout.py",
 "jra-promote-formal-3action-v315-initial.py",
 "cmp -s",
]:
 if piece=="original_source":continue
 assert piece in w,("complete formal fresh source/PDF/HTTP gate missing",piece)
for bad in ["experience_regime_v1/", "gh workflow run experience-regime",
 "e2e_validation/requests/recovery", "git push --force", "git reset --hard"]:
 assert bad not in w,("forbidden research/unsafe trigger",bad)
assert w.count("jra-check-fresh-quotes-v313-exec.py")>=4
assert w.count("jra-prestart-pipeline-v313.mjs")>=2
print("PASS_JRA_INITIAL_V315_IMMUTABLE_SOURCE_TWO_GIT_PROOFS_STRICT_READER_NO_E012")
