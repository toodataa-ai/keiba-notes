#!/usr/bin/env python3
"""Fail-closed acceptance test for JRA reader-v1 HTML / rendered PDF.

Run before committing docs/pdfs. Historical PDFs are never modified.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    import fitz
except ImportError as exc:
    raise SystemExit("ERROR: PyMuPDF required: python -m pip install pymupdf==1.26.4") from exc

HEADING = "全頭診断・個別評価"
BAD_WORDS = re.compile(r"undefined|\[object Object\]|(?:^|\W)NaN(?:\W|$)|Traceback", re.I)
OPAQUE_ID = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{24,}(?![0-9a-fA-F])")
LONG_DECIMAL = re.compile(r"(?<!\d)\d{12,}(?!\d)")
HORSE_TAG = re.compile(r'<section\s+class=["\x27]horse["\x27]', re.I)
PAGE_TAG = re.compile(r'<section\s+class=["\x27]page["\x27]', re.I)
HORSE_HEAD = re.compile(r'<h1>\s*([◎○▲△×])\s*(\d+)\s+([^<]+)</h1>')

def validate(html_path, pdf_path, policy_path):
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    html = Path(html_path).read_text(encoding="utf-8")
    errors = []
    css_match = re.search(r"<style>(.*?)</style>", html, re.S | re.I)
    if not css_match:
        errors.append("The accepted CSS must be embedded in <style> without substitutions")
    else:
        actual = hashlib.sha256(css_match.group(1).encode("utf-8")).hexdigest()
        if actual != policy["style_sha256"]:
            errors.append("CSS differs from accepted jra-reader-v1 template (layout drift)")
    style_file = Path(policy_path).parent.parent / "assets" / "jra-pdf-reader-v1.css"
    if not style_file.exists():
        errors.append("Canonical CSS file not found")
    elif hashlib.sha256(style_file.read_bytes()).hexdigest() != policy["style_sha256"]:
        errors.append("Canonical CSS fingerprint changed without versioned contract")

    expected_horses = len(HORSE_TAG.findall(html))
    if not expected_horses or expected_horses > 22:
        errors.append(f"Invalid number of horse pages: {expected_horses}")
    base_pages = policy["front_and_tail_pages"]
    if len(PAGE_TAG.findall(html)) != base_pages:
        errors.append(f"Expected exactly {base_pages} non-horse .page sections")
    horses = HORSE_HEAD.findall(html)
    if len(horses) != expected_horses:
        errors.append(f"Horse headings {len(horses)} != horse pages {expected_horses}")
    if len({number for _, number, _ in horses}) != len(horses):
        errors.append("Duplicate horse number in diagnosis pages")
    if BAD_WORDS.search(html):
        errors.append("HTML contains unresolved placeholder")
    visible_html = re.sub(r"<[^>]*>", " ", html)
    if OPAQUE_ID.search(visible_html) or LONG_DECIMAL.search(visible_html):
        errors.append("Visible HTML contains an opaque internal ID")

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        errors.append(f"PDF missing: {pdf_path}")
        return errors
    doc = fitz.open(str(pdf_path))
    if not doc.is_pdf or doc.is_encrypted:
        errors.append("Output is not an unencrypted PDF")
    if len(doc) != expected_horses + base_pages:
        errors.append(f"PDF pages {len(doc)} != expected {expected_horses + base_pages}: overflow or blank page")
    for index, page in enumerate(doc):
        number = index + 1
        r = page.rect
        if abs(r.width - 595.276) > 1.5 or abs(r.height - 841.89) > 1.5:
            errors.append(f"Page {number}: page size is not A4 portrait")
        contents = page.get_text("text")
        if len(re.sub(r"\s", "", contents)) < policy["minimum_nonspace_chars_per_page"]:
            errors.append(f"Page {number}: empty/sparse page detected")
        if BAD_WORDS.search(contents) or "\ufffd" in contents or "\u25a1" in contents:
            errors.append(f"Page {number}: missing glyph or unresolved placeholder")
        if OPAQUE_ID.search(contents) or LONG_DECIMAL.search(contents):
            errors.append(f"Page {number}: leaked internal SHA or long numeric identifier")
        for block in page.get_text("dict").get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    piece = span.get("text", "").strip()
                    if not piece:
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    if x0 < 5 or y0 < 5 or x1 > r.width - 5 or y1 > r.height - 5:
                        errors.append(f"Page {number}: text outside safe print bounds: {piece[:25]!r}")
                    if span.get("size", 99) < policy["minimum_font_pt"]:
                        errors.append(f"Page {number}: font size too small: {piece[:25]!r}")
        start = policy["horse_page_start_1_based"]
        if start <= number < start + expected_horses:
            offset = number - start
            if contents.count(HEADING) != 1:
                errors.append(f"Page {number}: missing or duplicated horse diagnosis")
            if offset < len(horses):
                mark, horse_no, name = horses[offset]
                normalized = re.sub(r"\s", "", contents)
                if re.sub(r"\s", "", f"{mark}{horse_no}{name}") not in normalized:
                    errors.append(f"Page {number}: incorrect horse/page mapping: {horse_no} {name}")
                if f"{offset+1}/{expected_horses}" not in contents.replace(" ", ""):
                    errors.append(f"Page {number}: wrong horse counter")
        elif HEADING in contents:
            errors.append(f"Page {number}: horse diagnosis spilled into another page")
    return errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--policy", default="docs/data/jra_pdf_layout_policy_v1.json")
    args = parser.parse_args()
    errors = validate(args.html, args.pdf, args.policy)
    if errors:
        for error in errors:
            print(f"::error::{error}", file=sys.stderr)
        print(f"FAILED: {len(errors)} PDF layout violations", file=sys.stderr)
        return 1
    print(f"PASS: A4 / stable layout / all individual horse pages / no exposed IDs: {args.pdf}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
