#!/usr/bin/env python3
"""Validate that immutable prompt manifests still point at the exact Git blobs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def git_hash_object(repo_root: Path, path: str) -> str:
    proc = subprocess.run(
        ["git", "hash-object", path],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cannot hash {path}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_dir = repo_root / "e2e_validation" / "manifests"
    errors = []
    checked = 0
    supersession = json.loads(
        (repo_root / "docs/data/jra_ci_supersession_v312.json").read_text(encoding="utf-8")
    )
    accepted = {x["path"]: x for x in supersession["superseded_components"]}
    if set(accepted) != {".github/workflows/validate-jra-balanced-v311.yml"}:
        raise RuntimeError("unexpected grandfathered SHA exceptions")

    # A separately pinned v3.13 bridge verifies exact approved legacy Git blobs.
    # No previous manifest is rewritten; checks run against the real original commit.
    formal_version = json.loads((repo_root / "docs/data/latest_prompt.json").read_text(encoding="utf-8")).get("version")
    grandfathered = {}
    historic_anchor = None
    if formal_version == "v3.13":
        bridge = json.loads((repo_root / "docs/data/jra_v313_historical_adapter_v1.json").read_text(encoding="utf-8"))
        grandfathered = {item["path"]: item for item in bridge["superseded_components"]}
        historic_anchor = bridge["historical_anchor_commit"]
        authorized = {
            ".github/scripts/validate-jra-ci-forward-v312.mjs",
            ".github/scripts/validate-jra-prompt-v312.mjs",
            ".github/scripts/validate-jra-archived-compact-v312.mjs",
            ".github/scripts/validate-jra-prerace-v312.mjs",
            "e2e_validation/validate_manifests.py",
        }
        if set(grandfathered) != authorized or not bridge.get("fail_closed_on_other_changes"):
            raise RuntimeError("unapproved legacy v3.13 SHA exception list")
        for src, exception in grandfathered.items():
            if git_hash_object(repo_root, src) != exception["current_blob_sha"]:
                raise RuntimeError("unapproved changed legacy SHA: " + src)
            original = subprocess.run(["git", "rev-parse", historic_anchor + ":" + src],
                                      cwd=repo_root, capture_output=True, text=True)
            if original.returncode or original.stdout.strip() != exception["original_blob_sha"]:
                raise RuntimeError("missing original audited Git history for " + src)

    for path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        version = manifest.get("prompt_version")
        for component in manifest.get("components", []):
            checked += 1
            component_path = component["path"]
            expected = component["git_blob_sha"]
            actual = git_hash_object(repo_root, component_path)
            exception = accepted.get(component_path)
            if actual != expected and exception and version in ("v3.11", "v3.12"):
                is_expected = (expected == exception["historical_blob_sha"] and
                               actual == exception["current_blob_sha"])
                old_object = subprocess.run(["git", "cat-file", "-t", expected],
                                            cwd=repo_root, text=True, capture_output=True)
                is_original_preserved = old_object.returncode == 0 and old_object.stdout.strip() == "blob"
                updated_text = (repo_root / component_path).read_text(encoding="utf-8")
                if is_expected and is_original_preserved and exception["required_compatibility_marker"] in updated_text:
                    continue
            override = grandfathered.get(component_path)
            if actual != expected and override:
                if expected == override["original_blob_sha"] and actual == override["current_blob_sha"]:
                    continue
            if actual != expected:
                errors.append(
                    {
                        "manifest": str(path.relative_to(repo_root)),
                        "version": version,
                        "component": component_path,
                        "expected": expected,
                        "actual": actual,
                    }
                )
    result = {"checked_components": checked, "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
