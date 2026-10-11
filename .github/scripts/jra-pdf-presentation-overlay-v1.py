#!/usr/bin/env python3
"""Presentation-only Japanese labels for the frozen JRA v3.12 HTML/PDF.

No prediction, odds, strategy evaluation, selected bet, or historical artifact is changed.
The original v3.12 report renderer and approved CSS remain byte-identical.
"""
import argparse
import re
from pathlib import Path

METHOD_NAMES = {
    "single": "1点買い",
    "multiple_singles": "複数頭の単点買い",
    "box": "ボックス",
    "key_wheel": "1頭軸流し",
    "key_wheel_first": "1着固定流し",
    "key_wheel_second": "2着固定流し",
    "key_wheel_multi": "1頭軸マルチ",
    "one_key_wheel": "1頭軸流し",
    "two_key_wheel": "2頭軸流し",
    "formation": "フォーメーション",
    "one_key_fixed": "1頭軸固定",
    "two_key_fixed": "2頭軸固定",
    "one_key_multi": "1頭軸マルチ",
    "two_key_multi": "2頭軸マルチ",
    "win_place_support": "単複併用",
}
STATUS_NAMES = {"unpriced": "個別オッズ未確認", "over_budget": "全点購入は予算超過"}
TABLE = re.compile(r'<table class="table dense">.*?</table>', re.S)
METHOD_ROW = re.compile(r'(<tr><td>[^<]+</td><td>[^<]+</td><td>)([^<]+)(</td>)')
PAGE = re.compile(
    r'<section class="page"><div class="chapter">購入最適化監査｜方式別セット比較 \d+/\d+</div>(.*?)</section>', re.S
)
ROW_COUNT = re.compile(r'<tbody>(.*?)</tbody>', re.S)

def apply(html_source):
    pages = PAGE.findall(html_source)
    if not pages:
        raise ValueError("JRA presentation blocker: mode comparison pages absent")
    total_before = sum(len(re.findall(r'<tr>', m.group(1))) for p in pages for m in ROW_COUNT.finditer(p))
    changed = [0]

    def transform_table(match):
        section = match.group(0)
        if '<th>方式</th>' not in section or '<th>ID</th>' not in section:
            return section

        def transform_row(row):
            raw = row.group(2)
            if raw not in METHOD_NAMES:
                raise ValueError("JRA presentation blocker: unmapped ticket method " + raw)
            changed[0] += 1
            return row.group(1) + METHOD_NAMES[raw] + row.group(3)

        result = METHOD_ROW.sub(transform_row, section)
        for original, localized in STATUS_NAMES.items():
            result = result.replace('<td>' + original + '</td>', '<td>' + localized + '</td>')
        return result

    converted = TABLE.sub(transform_table, html_source)
    if changed[0] != total_before or total_before == 0:
        raise ValueError(
            f"JRA presentation blocker: mapped {changed[0]} / {total_before} strategy rows"
        )
    if len(PAGE.findall(converted)) != len(pages):
        raise ValueError("JRA presentation blocker: comparison page count changed")
    return converted, changed[0], len(pages)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    src = args.html.read_text(encoding="utf-8")
    if args.check:
        if any('<td>' + code + '</td>' in src for code in METHOD_NAMES):
            raise SystemExit("JRA presentation blocker: raw method code displayed")
        if not PAGE.findall(src):
            raise SystemExit("JRA presentation blocker: no audit pages")
        print("PASS: purchase-method labels are Japanese")
        return
    result, rows, pages = apply(src)
    args.html.write_text(result, encoding="utf-8")
    print(f"PASS: {rows} method labels translated across {pages} audit pages")

if __name__ == "__main__":
    main()
