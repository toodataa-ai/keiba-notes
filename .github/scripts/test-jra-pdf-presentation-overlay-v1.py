#!/usr/bin/env python3
"""Regression guard for the JRA presentation-only Japanese/compact audit overlay."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name('jra-pdf-presentation-overlay-v1.py')
spec = importlib.util.spec_from_file_location('jra_pdf_overlay', SCRIPT)
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

codes = list(overlay.METHOD_NAMES)
def section(idx, total, modes):
    table = '<table class="table dense"><thead><tr>' + ''.join(
        '<th>'+x+'</th>' for x in ('ID', '券種', '方式', '点数', '集合的中率', '期待純利益', '実損率')
    ) + '</tr></thead><tbody>'
    for i, code in enumerate(modes):
        table += f'<tr><td>S{i+idx*20:03d}</td><td>馬連</td><td>{code}</td><td>4</td>'
        table += '<td>20%</td><td>5円</td><td>80%</td></tr>'
    table += '</tbody></table>'
    return (f'<section class="page"><div class="chapter">購入最適化監査｜方式別セット比較 '
            f'{idx+1}/{total}</div><p>全点の集合確率を検証。</p>{table}</section>')

html = '<html><body data-tail-pagination="dynamic">' + (
    section(0, 2, codes[:9]) + section(1, 2, codes[9:])
) + '</body></html>'
converted, rows, pages = overlay.apply(html)
assert rows == len(codes) and pages == 2
assert len(converted) == len(converted.encode('utf-8').decode('utf-8'))
assert all(f'<td>{label}</td>' in converted for label in overlay.METHOD_NAMES.values())
assert not any(f'<td>{code}</td>' in converted for code in codes)
assert len(overlay.PAGE.findall(converted)) == 2
try:
    overlay.apply(html.replace('<td>single</td>', '<td>unknown_purchase_code</td>', 1))
except ValueError as e:
    assert 'unmapped ticket method' in str(e)
else:
    raise AssertionError('unknown strategy must fail closed')

# The approved reader-v1 A4 CSS must fit 14 comparison rows on one page.
# This prevents reverting to seven short rows per page or silently overflowing.
import tempfile
import fitz
from weasyprint import HTML
css = (SCRIPT.parents[2] / "docs/assets/jra-pdf-reader-v1.css").read_text(encoding="utf-8")
dense_html = ('<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>' +
              css + '</style></head><body data-tail-pagination="dynamic">')
dense_html += section(0, 3, (codes * 2)[:14])
dense_html += section(1, 3, (codes * 2)[2:16])
dense_html += section(2, 3, (codes * 2)[12:19])
dense_html += '</body></html>'
localized, row_count, page_count = overlay.apply(dense_html)
assert row_count == 35 and page_count == 3
with tempfile.TemporaryDirectory() as tmp:
    pdf = Path(tmp) / 'compact-audit.pdf'
    HTML(string=localized).write_pdf(str(pdf))
    with fitz.open(pdf) as doc:
        assert len(doc) == 3, f'14-row audit must fit A4; got {len(doc)} pages'
        assert all('方式別セット比較' in p.get_text() and len(p.get_text().strip()) > 200
                   for p in doc), 'blank or clipped audit page'
print('PASS: 14 comparison rows per A4 page under immutable v3.7 reader CSS')

print('PASS: all real JRA strategy methods localized; unknown codes rejected; rows/pages preserved')
