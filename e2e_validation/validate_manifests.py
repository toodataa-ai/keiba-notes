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

    current_ci = json.loads((repo_root / "docs/data/jra_current_e2e_ci_supersession_v1.json").read_text(encoding="utf-8"))
    current_exceptions = {item["path"]:item for item in current_ci["superseded_components"]}

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
            override = current_exceptions.get(src)
            approved_current = (override["current_blob_sha"]
                                if src == "e2e_validation/validate_manifests.py" and override
                                else exception["current_blob_sha"])
            if git_hash_object(repo_root, src) != approved_current:
                raise RuntimeError("unapproved changed legacy SHA: " + src)
            original = subprocess.run(["git", "rev-parse", historic_anchor + ":" + src],
                                      cwd=repo_root, capture_output=True, text=True)
            if original.returncode or original.stdout.strip() != exception["original_blob_sha"]:
                raise RuntimeError("missing original audited Git history for " + src)

    # Append-only current-operations bridge. Historic manifests remain unchanged.
    # The old workflow and validator blobs must still exist at the historical
    # anchor and the active replacements must match exactly approved hashes.
    if current_ci.get("schema_version") != 1 or current_ci.get("scope") != "current_e2e_orchestration_supersession_only":
        raise RuntimeError("invalid current E2E CI supersession")
    if set(current_exceptions) != {
        ".github/workflows/e2e-validation.yml",
        "e2e_validation/validate_experience_history_v312.py",
        "e2e_validation/validate_manifests.py",
    } or len(current_ci["superseded_components"]) != 3:
        raise RuntimeError("unexpected current E2E CI supersession scope")
    if not all(current_ci.get("safeguards",{}).get(key) is True for key in (
        "no_legacy_manifest_mutation","old_blob_sha_retention","old_workflow_sources_preserved_in_git",
        "formal_grade_a_unchanged","shadow_promotion_blocked","only_current_ci_behavior_changed",
        "unknown_shadow_errors_fail")):
        raise RuntimeError("current E2E safeguards weakened")
    ledger_path = current_ci["ledger_path"]
    if ledger_path != "e2e_validation/experience_archived_gaps_v1.json" or (
        git_hash_object(repo_root, ledger_path) != current_ci["ledger_blob_sha"]
    ):
        raise RuntimeError("SHA-pinned Shadow gap ledger changed")
    for component_path, exception in current_exceptions.items():
        if git_hash_object(repo_root, component_path) != exception["current_blob_sha"]:
            raise RuntimeError("current E2E component changed without supersession")
        old_object = subprocess.run(
            ["git","rev-parse",current_ci["historical_anchor_commit"]+":"+component_path],
            cwd=repo_root,capture_output=True,text=True,
        )
        if old_object.returncode or old_object.stdout.strip() != exception["original_blob_sha"]:
            raise RuntimeError("original E2E CI Git history unavailable: "+component_path)

    for path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        version = manifest.get("prompt_version")
        for component in manifest.get("components", []):
            checked += 1
            component_path = component["path"]
            expected = component["git_blob_sha"]
            actual = git_hash_object(repo_root, component_path)
            exception = accepted.get(component_path)
            if actual != expected and exception and version in ("v3.11", "v3.12", "v3.13"):
                is_expected = (expected == exception["historical_blob_sha"] and
                               actual == exception["current_blob_sha"])
                old_object = subprocess.run(["git", "cat-file", "-t", expected],
                                            cwd=repo_root, text=True, capture_output=True)
                is_original_preserved = old_object.returncode == 0 and old_object.stdout.strip() == "blob"
                updated_text = (repo_root / component_path).read_text(encoding="utf-8")
                if is_expected and is_original_preserved and exception["required_compatibility_marker"] in updated_text:
                    continue
            current_override = current_exceptions.get(component_path)
            if actual != expected and current_override and version in ("v3.12","v3.13"):
                if (expected == current_override.get("manifest_blob_sha",current_override["original_blob_sha"]) and
                        actual == current_override["current_blob_sha"]):
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
