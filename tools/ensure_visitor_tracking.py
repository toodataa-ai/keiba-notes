#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TRACKER = DOCS / "assets" / "visitor-counter.js"
VERSION = "20261006-1"
EXCLUDE = {DOCS / "admin.html", DOCS / "staging" / "admin.html",
           DOCS / "lab" / "usage-analytics.html", DOCS / "staging" / "usage-analytics.html"}
# Read-only prestart forecast HTML is legal/evidentiary source material.
# Visitor analytics belong on the surrounding public navigation page, not in
# historical prediction artifacts. Never inject any JS into frozen reports.
FROZEN_REPORT_DIRS = {DOCS / "reports", DOCS / "full-reports", DOCS / "styled-report-sources"}


def script_tag(path: Path) -> str:
    rel = os.path.relpath(TRACKER, path.parent).replace(os.sep, "/")
    return f'<script src="{rel}?v={VERSION}" defer></script>'


def main() -> int:
    changed = []
    for path in sorted(DOCS.rglob("*.html")):
        if path in EXCLUDE or any(directory in path.parents for directory in FROZEN_REPORT_DIRS):
            continue
        text = path.read_text(encoding="utf-8")
        if "visitor-counter.js" in text:
            continue
        if "</body>" not in text:
            print(f"skip(no </body>): {path.relative_to(ROOT)}")
            continue
        tag = script_tag(path)
        text = text.replace("</body>", f"  {tag}\n</body>", 1)
        path.write_text(text, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))
    print(f"visitor tracking ensured: {len(changed)} file(s)")
    for item in changed:
        print(f"  {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
