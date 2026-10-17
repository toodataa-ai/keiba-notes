#!/usr/bin/env python3
"""Build an evidence-only UI change ledger from user-curated approval state and git blobs.

This script reads GitHub checkout metadata and writes ONLY docs/lab/change-board.json.
It does not approve, promote, delete, or edit any prediction, PDF or staging code.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".github/lab/feature-registry.json"
OUTPUT = ROOT / "docs/lab/change-board.json"

def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        return ""
    return result.stdout.strip()

def tree_blob(path):
    # An absent path is an explicit defect, never quietly equal to an empty blob.
    sha = git("rev-parse", "--verify", "HEAD:" + path)
    return sha or None

def recent_commit(paths):
    return git("log", "-1", "--format=%H", "--", *paths) or None

def main():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert registry["schema_version"] == 1
    ids = set()
    entries = []
    for feature in registry["features"]:
        fid = feature["id"]
        assert fid not in ids and fid and "/" not in fid, fid
        ids.add(fid)
        assert feature["phase"] in ("lab_development","lab_evaluation","needs_review","staging_review","released","reference_only")
        assert feature["approval"] and feature["name"] and feature["next_action"]
        assert feature["preview_path"].startswith(("staging/","lab/"))
        assert ((ROOT / "docs" / feature["preview_path"]).is_file() or
                (ROOT / "docs" / feature["preview_path"] / "index.html").is_file()), feature["preview_path"]
        paths = feature.get("lab_paths",[]) + feature["staging_paths"] + feature["production_paths"]
        assert paths and len(paths) == len(set(paths))
        assert all(p.startswith("docs/staging/") for p in feature["staging_paths"])
        assert all(p.startswith("docs/lab/") for p in feature.get("lab_paths",[]))
        assert all(p.startswith("docs/") and not p.startswith("docs/staging/") and not p.startswith("docs/data/") for p in feature["production_paths"])
        evidence = {path: tree_blob(path) for path in paths}
        if any(sha is None for sha in evidence.values()):
            raise ValueError("Missing tracked UI source; review before publishing board: " +
                ", ".join(x for x,sha in evidence.items() if sha is None))
        entries.append({
            "id": fid, "name": feature["name"], "phase": feature["phase"],
            "approval": feature["approval"], "next_action": feature["next_action"],
            "preview_path": feature["preview_path"],
            "staging_paths": feature["staging_paths"],
            "lab_paths": feature.get("lab_paths",[]),
            "production_paths": feature["production_paths"],
            "file_blob_shas": evidence,
            "latest_source_change_commit": recent_commit(paths)
        })
    data = {
        "schema_version": 1,
        "kind": "read_only_ui_development_inventory",
        "state": "verified_git_source",
        "scan_commit": recent_commit([".github/lab/feature-registry.json"] + [p for f in registry["features"] for p in f.get("lab_paths",[])+f["staging_paths"]+f["production_paths"]]),
        "policy": registry["policy"],
        "counts": {x: sum(f["phase"] == x for f in entries) for x in
                   ("lab_development","lab_evaluation","needs_review","staging_review","released","reference_only")},
        "features": entries,
        "note": "Git source hashes and timestamps are automatic; approval and phase are curated explicitly. LAB hosts live experiment copies; legacy staging paths redirect for compatibility."
    }
    result = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv[1:]:
        assert OUTPUT.is_file() and OUTPUT.read_text(encoding="utf-8") == result, (
            "LAB_CHANGE_BOARD_STALE: regenerate board in current checkout")
        print("PASS_LAB_BOARD_EXACT_SOURCE", len(entries), data["scan_commit"])
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(result, encoding="utf-8")
    print("LAB_BOARD_REGENERATED", len(entries), data["scan_commit"])
if __name__ == "__main__":
    main()
