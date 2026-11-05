#!/usr/bin/env python3
"""Release-ledger and production-UI invariants that hold for EVERY approved UI release.

Replaces the per-release hard-coded checks (which had to be edited by hand for
each version) with rules every release must satisfy, plus pinned facts for the
historical releases so they can never be rewritten.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ("index.html", "this-week.html", "schedule.html", "results.html", "methodology.html",
             "roadmap.html", "e2e.html", "baba-models.html", "local-racing-shadow.html",
             "experience-regime.html", "release-history.html", "improvement-cycle.html", "operations.html", "sire-map.html")
# Historical releases are immutable facts: (release_id, commit_sha, workflow_run_id)
PINNED = {
    "release/jra-site-v1.01-20261012": ("632146ccb581847ae5d4cb9535fb868b8b4517d8", 38185706485),
    "release/jra-site-v1.05-20261025": ("5a965e994667b0454ac71a1c2cd5f023e0917f64", 40159893108),
}
STAGE_LEAKS = ('data-stage="preview"', "staging-shell-marker", "noindex,nofollow", 'href="staging/',
               "<base ", "staging/candidate-assets/")


def main() -> None:
    source = (ROOT / ".github/production-releases.json").read_bytes()
    display = (ROOT / "docs/data/production-releases.json").read_bytes()
    assert source == display, "GitHub UI release registry and public UI history disagree"
    d = json.loads(source)
    policy = json.loads((ROOT / "docs/data/jra_release_channel_policy_v1.json").read_text())
    assert policy["ui"]["user_approval_required"] is True
    assert policy["data"]["update_requires_user_approval"] is False
    assert policy["data"]["auto_publish_after_validation"] is True
    assert d["policy"]["ui_release_requires_explicit_user_approval"] is True
    assert d["policy"]["data_release_requires_user_approval"] is False

    releases = d["releases"]
    versions = [x["public_version"] for x in releases]
    assert len(set(versions)) == len(versions), "duplicate public_version"
    assert versions == sorted(versions, key=lambda v: tuple(int(p) for p in v.split("."))), "versions out of order"
    by_id = {x["release_id"]: x for x in releases}
    for rid, (sha, run) in PINNED.items():
        assert by_id[rid]["commit_sha"] == sha and by_id[rid]["workflow_run_id"] == run, ("pinned release rewritten", rid)
    for x in releases:
        assert re.fullmatch(r"[a-f0-9]{40}", x["commit_sha"])
        subprocess.run(["git", "cat-file", "-e", x["commit_sha"] + "^{commit}"], cwd=ROOT, check=True)
        assert x["branch"].startswith("release/") and x["branch"] == x["release_id"]

    latest = releases[-1]
    assert d["current_public_release"] == latest["branch"]
    assert d["current_public_version"] == latest["public_version"]
    assert latest.get("user_approved") is True, "latest UI release lacks explicit user approval"
    assert latest.get("presentation_only") is True
    assert latest.get("immutable_prediction_source_preserved") is True
    assert latest.get("staging_identity_not_in_production") is True
    assert latest.get("scope_files"), "latest release must list its scope files"
    for f in latest["scope_files"]:
        assert (ROOT / f).is_file(), ("scope file missing", f)

    for name in CANONICAL:
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        leaks = [s for s in STAGE_LEAKS if s in text]
        assert not leaks, ("staging artifacts leaked into production", name, leaks)
    history = (ROOT / "docs/release-history.html").read_text()
    assert "fetch('data/production-releases.json'" in history
    autorevise = (ROOT / ".github/workflows/jra-prerace-rerun-fresh-v313.yml").read_text()
    assert "docs/data/races.json" in autorevise
    print("PASS_RELEASE_LEDGER_AND_PRODUCTION_UI", latest["public_version"], len(latest["scope_files"]))


if __name__ == "__main__":
    main()
