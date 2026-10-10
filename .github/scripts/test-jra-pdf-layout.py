#!/usr/bin/env python3
"""Exercise positive and negative cases against the actual PDF renderer."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "docs/assets/jra-pdf-reader-v1.css").read_text(encoding="utf-8")
POLICY = ROOT / "docs/data/jra_pdf_layout_policy_v1.json"
VALIDATOR = ROOT / ".github/scripts/validate-jra-pdf-layout.py"
FILLER = "発走前の客観的な能力評価と適性の根拠を丁寧に記述します。" * 13

def section(kind, title, number=None):
    heading = f'<h1>◎ {number} サンプル馬{number}</h1>' if kind == "horse" else f'<h2>{title}</h2>'
    sub = f"<h2>全頭診断・個別評価</h2><p>{number-4}/2　1頭1ページ</p>" if kind == "horse" else ""
    return f'<section class="{kind}">{sub}{heading}<p>{FILLER}</p></section>'

def run(html, pdf, expect_ok=True):
    result = subprocess.run([sys.executable, str(VALIDATOR), "--html", str(html), "--pdf", str(pdf),
                             "--policy", str(POLICY)], text=True, capture_output=True)
    if (result.returncode == 0) != expect_ok:
        raise AssertionError(f"Unexpected validator result: {result.stdout}\n{result.stderr}")
    print(("PASS" if expect_ok else "NEGATIVE PASS"), html.name, pdf.name)
    return result

def main():
    with tempfile.TemporaryDirectory(prefix="jra-reader-guard-") as t:
        root = Path(t)
        # 5 front pages, 2 horse pages, 3 final pages: the accepted reader-v1 structure.
        body = "".join(section("page", f"準備ページ {i}") for i in range(5))
        body += section("horse", "個別診断1", 5) + section("horse", "個別診断2", 6)
        body += "".join(section("page", f"最終ページ {i}") for i in range(3))
        source = '<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>' + CSS + \
                 '</style></head><body>' + body + '</body></html>'
        html = root / "positive.html"
        pdf = root / "positive.pdf"
        html.write_text(source, encoding="utf-8")
        subprocess.run([sys.executable, "-m", "weasyprint", str(html), str(pdf)], check=True)
        run(html, pdf)
        wrong_css = root / "wrong_style.html"
        wrong_css.write_text(source.replace("font-size:11.5pt", "font-size:11.0pt", 1), encoding="utf-8")
        run(wrong_css, pdf, False)
        altered = fitz.open(str(pdf))
        altered.insert_page(5)
        blank = root / "extra_blank.pdf"
        altered.save(str(blank))
        altered.close()
        run(html, blank, False)
        altered = fitz.open(str(pdf))
        altered[0].insert_text((65, 100), "201175357108308c4fadcdda7470f9daed35e9bc", fontsize=8)
        leaked = root / "leaked_sha.pdf"
        altered.save(str(leaked))
        altered.close()
        run(html, leaked, False)
    print("JRA reader-v1 layout guard smoke + 3 negative regressions passed")

if __name__ == "__main__":
    main()
