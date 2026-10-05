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
    for path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        version = manifest.get("prompt_version")
        for component in manifest.get("components", []):
            checked += 1
            component_path = component["path"]
            expected = component["git_blob_sha"]
            actual = git_hash_object(repo_root, component_path)
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
