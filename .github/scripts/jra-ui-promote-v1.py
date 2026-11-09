#!/usr/bin/env python3
"""Promote an approved STAGING UI candidate to production (used by jra-ui-promote-v1.yml).

apply   : copy the candidate's production-form sources byte-for-byte into docs/,
          remove it from .github/staging-candidates.json, print the scope files.
record  : append the approved release to both release ledgers (identical bytes).

Never touches prediction data, reports, PDFs, results, proofs or e2e_validation.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from html.parser import HTMLParser
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".github/staging-candidates.json"
SRC = ROOT / ".github/staging-candidates"
LEDGERS = (ROOT / ".github/production-releases.json", ROOT / "docs/data/production-releases.json")
JST = timezone(timedelta(hours=9))


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def apply(candidate_id: str) -> list[str]:
    m = load_manifest()
    cand = next((c for c in m["candidates"] if c["id"] == candidate_id), None)
    assert cand, f"unknown candidate {candidate_id}"
    assert cand.get("status") == "awaiting_user_approval", cand.get("status")
    scope = []
    for rel in list(cand.get("pages", [])) + list(cand.get("assets", [])):
        assert ".." not in rel and not rel.startswith("data/"), rel
        dest = ROOT / "docs" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / rel, dest)
        (SRC / rel).unlink()
        scope.append("docs/" + rel)
    m["candidates"] = [c for c in m["candidates"] if c["id"] != candidate_id]
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / ".promote-candidate.json").write_text(json.dumps(cand, ensure_ascii=False), encoding="utf-8")
    return scope



class PortalCardLinks(HTMLParser):
    """Only top-page cards are user-facing NEW entrances."""

    def __init__(self):
        super().__init__()
        self.pages = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        info = dict(attrs)
        if "portal-card" not in info.get("class", "").split():
            return
        href = info.get("href", "").split("#", 1)[0].split("?", 1)[0]
        if href.endswith(".html") and "/" not in href and href not in (".html",):
            self.pages.add(href)


def pages_in_index_revision(revision: str) -> set[str]:
    html = subprocess.check_output(
        ["git", "show", f"{revision}:docs/index.html"], cwd=ROOT, text=True
    )
    parser = PortalCardLinks()
    parser.feed(html)
    return parser.pages


def new_entry_pages(commit: str) -> list[str]:
    """Detect new homepage entrances without manually maintaining a badge list."""
    before = pages_in_index_revision(commit + "^")
    after = pages_in_index_revision(commit)
    added = sorted(after - before)
    for path in added:
        assert (ROOT / "docs" / path).is_file(), ("new entrance has no published page", path)
    return added


def verify_badges() -> None:
    ledger = json.loads(LEDGERS[0].read_text(encoding="utf-8"))
    checked = 0
    for release in ledger["releases"]:
        version = tuple(int(x) for x in release["public_version"].split("."))
        if version < (1, 47):  # Older releases retain their historical fixed entries.
            continue
        actual = new_entry_pages(release["commit_sha"])
        recorded = release.get("new_entry_pages")
        assert recorded == actual, (
            "NEW badge release metadata missing/mismatched",
            release["release_id"], recorded, actual
        )
        checked += 1
    print("PASS_NEW_BADGE_RELEASE_REGISTRY", checked)

def next_version(current: str) -> str:
    major, minor = current.split(".")
    return f"{major}.{int(minor) + 1:0{len(minor)}d}"


def record(candidate_json: str, commit: str, run_id: int, approval: str, scope: list[str]) -> str:
    cand = json.loads(Path(candidate_json).read_text(encoding="utf-8"))
    d = json.loads(LEDGERS[0].read_text(encoding="utf-8"))
    version = next_version(d["current_public_version"])
    now = datetime.now(JST)
    rid = f"release/jra-site-v{version}-{now:%Y%m%d}"
    d["releases"].append({
        "release_id": rid, "branch": rid, "commit_sha": commit,
        "deployed_at": now.isoformat(timespec="seconds"),
        "workflow_run_id": run_id, "validation_workflow_run_id": run_id,
        "public_version": version,
        "note": f"{now:%Y-%m-%d}ユーザー明示承認済み。{cand.get('title')}：{cand.get('summary', '')}",
        "user_approval_quote": approval,
        "staging_candidate_id": cand["id"],
        "user_approved": True,
        "immutable_prediction_source_preserved": True,
        "presentation_only": True,
        "staging_identity_not_in_production": True,
        "new_entry_pages": new_entry_pages(commit),
        "scope_files": scope,
        "public_http_files_verified": None,
    })
    d["current_public_release"] = rid
    d["current_public_version"] = version
    text = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    for path in LEDGERS:
        path.write_text(text, encoding="utf-8")
    return rid


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply"); a.add_argument("--candidate", required=True)
    sub.add_parser("verify-badges")
    r = sub.add_parser("record")
    r.add_argument("--commit", required=True); r.add_argument("--run-id", type=int, required=True)
    r.add_argument("--approval", required=True); r.add_argument("--scope", required=True)
    args = p.parse_args()
    if args.cmd == "verify-badges":
        verify_badges()
    elif args.cmd == "apply":
        print(json.dumps(apply(args.candidate)))
    else:
        assert args.approval.strip(), "explicit user approval quote is required"
        print(record(str(ROOT / ".promote-candidate.json"), args.commit, args.run_id,
                     args.approval.strip(), json.loads(args.scope)))


if __name__ == "__main__":
    main()
