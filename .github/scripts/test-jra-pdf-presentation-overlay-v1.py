#!/usr/bin/env python3
"""Regression for Japanese named BOX/formation/multi bundles in JRA PDF."""
import importlib.util
import re
import tempfile
from pathlib import Path
import fitz
from weasyprint import HTML

SCRIPT = Path(__file__).with_name("jra-pdf-presentation-overlay-v1.py")
spec = importlib.util.spec_from_file_location("jra_pdf_overlay", SCRIPT)
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
codes = list(overlay.METHOD_NAMES)
css = (SCRIPT.parents[2] / "docs/assets/jra-pdf-reader-v1.css").read_text(encoding="utf-8")


def section(idx, total, modes):
    table = '<table class="table dense"><thead><tr>' + "".join(
        "<th>"+x+"</th>" for x in ("ID", "券種", "方式", "点数", "集合的中率", "期待純利益", "実損率")
    ) + "</tr></thead><tbody>"
    for i, code in enumerate(modes):
        table += f'<tr><td>S{i+idx*20:03d}</td><td>馬連</td><td>{code}</td><td>2</td>'
        table += "<td>20%</td><td>5円</td><td>80%</td></tr>"
    table += "</tbody></table>"
    return (f'<section class="page"><div class="chapter">購入最適化監査｜方式別セット比較 '
            f'{idx+1}/{total}</div><p>全点の集合確率を検証。</p>{table}</section>')


def prediction_for(source):
    found = re.findall(r"<tr><td>(S\d+)</td><td>馬連</td><td>([a-z_]+)</td>", source)
    plans = []
    definition = dict(selection=[1, 2], horses=[1, 2, 3], key=1, partners=[2, 3],
                      axes=[1, 2], positions=[1, 2], slots=[[1, 2], [2, 3]],
                      position=1, horse=1)
    for sid, kind in found:
        plans.append({"strategy_id":sid, "type":"馬連", "strategy_kind":kind,
                      "definition":definition, "lines":[
                          {"type":"馬連", "selection":[1, 2]},
                          {"type":"馬連", "selection":[2, 3]}
                      ]})
    return {"purchase_strategy_evaluations":plans,
            "final_bets":[{"type":"馬連", "selection":[1, 2], "id":"B01"}]}


prefix = ('<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>' +
          css + '</style></head><body data-tail-pagination="dynamic">'
          '<section class="page"><div class="chapter">採用買い目｜1/1</div><p>詳細</p></section>')
source = prefix + section(0, 2, codes[:9]) + section(1, 2, codes[9:]) + "</body></html>"
converted, rows, pages = overlay.apply(source, prediction_for(source))
assert (rows, pages) == (len(codes), 2)
assert "ボックス<div class=\"tiny\">1・2・3｜一部採用1/2点" in converted
assert "フォーメーション<div class=\"tiny\">1列:1・2／2列:2・3" in converted
assert "2頭軸マルチ<div class=\"tiny\">軸1・2→2・3" in converted
assert "BOX" not in converted  # Actual Japanese descriptions, not English shorthand.
assert len(overlay.PAGE.findall(converted)) == 2
assert not any("<td>"+code+"</td>" in converted for code in codes)
assert "重複購入は計上しません" in converted

tampered = source.replace("<td>single</td>", "<td>unknown_mode</td>", 1)
try:
    overlay.apply(tampered, prediction_for(source))
except ValueError as exc:
    assert "unmapped ticket method" in str(exc)
else:
    raise AssertionError("unknown purchase mode must stop")

wrong = prediction_for(source)
wrong["purchase_strategy_evaluations"][0]["definition"] = {}
try:
    overlay.apply(source, wrong)
except (ValueError, KeyError):
    pass
else:
    raise AssertionError("undefined bundle detail must fail closed")

# Short 14-row audit pages are accepted without changing v3.7 CSS.
dense = prefix + section(0, 3, (codes * 2)[:14])
dense += section(1, 3, (codes * 2)[2:16])
dense += section(2, 3, (codes * 2)[12:19]) + "</body></html>"
localized, row_count, page_count = overlay.apply(dense, prediction_for(dense))
assert row_count == 35 and page_count == 3
with tempfile.TemporaryDirectory() as tmp:
    pdf = Path(tmp) / "compact-audit.pdf"
    HTML(string=localized).write_pdf(str(pdf))
    with fitz.open(pdf) as doc:
        assert len(doc) == 4, f"one adopted page and three audit pages expected, got {len(doc)}"
        assert all(len(page.get_text().strip()) > 150 for page in list(doc)[1:])
        assert '採用買い目' in doc[0].get_text() and '重複購入' in doc[0].get_text()
print("PASS: every strategy-mode label and concrete bundle definition; full/partial adoption, 14-row A4 PDF")
