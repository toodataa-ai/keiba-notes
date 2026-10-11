#!/usr/bin/env python3
"""Fail-closed acceptance test for JRA reader-v1 HTML / rendered PDF.

Run before committing docs/pdfs. Historical PDFs are never modified.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
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
# Existing approved palette, NOT a new stylesheet: RGB text colors and matching backgrounds.
GRADE = {'A+':('gAp','#701622','#f29fa9'), 'A':('gA','#6e201c','#f7b8b5'),
         'B+':('gBp','#734a10','#f9c896'), 'B':('gB','#725518','#ffdf9d'),
         'B-':('gBm','#4c6129','#d8e7ba'), 'C':('gC','#2a5570','#d1e7f0')}
GRADE_BADGE = re.compile(r'<span class="g (gAp|gA|gBp|gB|gBm|gC)">(A\+|A|B\+|B|B-|C)</span>')
HORSE_SECTION = re.compile(r'<section class="horse">(.*?)</section>', re.S)
def close_color(actual,expected,tolerance=0.035):
    if isinstance(actual,int):actual=((actual>>16&255)/255,(actual>>8&255)/255,(actual&255)/255)
    exp=tuple(int(expected[i:i+2],16)/255 for i in (1,3,5))
    return actual is not None and len(actual)>=3 and all(abs(a-b)<=tolerance for a,b in zip(actual,exp))


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
    horse_sections = HORSE_SECTION.findall(html)
    expected_badges = []
    if len(horse_sections)!=expected_horses:
        errors.append('Cannot identify all individual horse HTML sections for grade-color audit')
    for index,section in enumerate(horse_sections):
        badges = GRADE_BADGE.findall(section)
        # One overall rating plus exactly nine graded factors; no naked black grades permitted.
        if len(badges)!=10:
            errors.append(f'Horse {index+1}: expected exactly 10 colored grade badges (overall + 9 axes), got {len(badges)}')
        for css,grade in badges:
            if GRADE[grade][0]!=css:
                errors.append(f'Horse {index+1}: grade {grade} uses incorrect CSS color class {css}')
        head=section.split('①〜⑨：評価軸別グレード</h3>',1)
        factor_badges=GRADE_BADGE.findall(head[1].split('</table>',1)[0]) if len(head)==2 else []
        if len(factor_badges)!=9:
            errors.append(f'Horse {index+1}: nine axes not individually grade-colored in HTML')
        expected_badges.append(Counter(grade for _,grade in badges))
    if len(GRADE_BADGE.findall(html))<10*expected_horses:
        errors.append('HTML lacks grade palette markup')
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
            if offset<len(expected_badges):
                # Inspect the rendered PDF, not just source CSS. A completely grey PDF must fail.
                wanted=expected_badges[offset]
                found=Counter()
                for block in page.get_text('dict').get('blocks',[]):
                    for line in block.get('lines',[]):
                        for span in line.get('spans',[]):
                            grade=span.get('text','').strip()
                            if grade in GRADE and close_color(span.get('color'),GRADE[grade][1]):
                                found[grade]+=1
                for grade,count in wanted.items():
                    if found[grade]<count:
                        errors.append(f'Page {number}: grade {grade} colored PDF text missing ({found[grade]}/{count})')
                fills=Counter()
                for drawing in page.get_drawings():
                    rgb=drawing.get('fill')
                    if rgb is None:continue
                    for grade,(_,_,hex_bg) in GRADE.items():
                        if close_color(rgb,hex_bg):fills[grade]+=1
                for grade,count in wanted.items():
                    if fills[grade]<count:
                        errors.append(f'Page {number}: grade {grade} colored PDF background missing ({fills[grade]}/{count})')
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
    print(f"PASS: A4 / stable layout / all individual horse pages / verified A+ through C grade text/background palette / no exposed IDs: {args.pdf}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
