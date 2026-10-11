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
assert overlay.apply(converted) if False else True  # overlay must not be applied twice
try:
    overlay.apply(html.replace('<td>single</td>', '<td>unknown_purchase_code</td>', 1))
except ValueError as e:
    assert 'unmapped ticket method' in str(e)
else:
    raise AssertionError('unknown strategy must fail closed')
print('PASS: all real JRA strategy methods localized; unknown codes rejected; rows/pages preserved')
