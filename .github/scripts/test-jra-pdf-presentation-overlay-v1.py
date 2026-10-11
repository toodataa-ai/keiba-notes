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
    return {"purchase_strategy_evaluations":plans, "purchase_decision":"buy",
            "total_stake_yen":100,
            "purchase_portfolio_selection":{
                "expected_net_profit_yen_scenarios":{"central":12.5},
                "hit_probability_scenarios":{"central":0.13},
                "loss_probability_scenarios":{"central":0.68}},
            "final_bets":[{"type":"馬連", "selection":[1, 2], "stake_yen":100, "id":"B01"}]}


prefix = ('<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>' +
          css + '</style></head><body data-tail-pagination="dynamic">'
          '<section class="page"><div class="chapter">本日の正式予想｜表紙</div>'
          '<h1>東京11R 合成レース</h1><p>2026-10-11 芝1800m</p><p>旧来の表紙</p></section>'
          '<section class="page"><div class="chapter">採用買い目｜1/1</div><p>詳細</p></section>'
          '<section class="page"><div class="chapter">不採用買い目｜1/1</div><p>除外理由は後半</p></section>')
source = prefix + section(0, 2, codes[:9]) + section(1, 2, codes[9:]) + "</body></html>"
converted, rows, pages = overlay.apply(source, prediction_for(source))
assert (rows, pages) == (len(codes), 2)
assert "ボックス 1,2,3（採用1/2点）" in converted
assert "フォーメーション 1,2/2,3（採用1/2点）" in converted
assert "2頭軸マルチ 軸1,2→2,3（採用1/2点）" in converted
assert "BOX" not in converted  # Actual Japanese descriptions, not English shorthand.
assert len(overlay.PAGE.findall(converted)) == 2
assert converted.index('最終購入結論｜本日の正式予想') < converted.index('採用買い目｜1/1')
assert converted.index('不採用買い目｜1/1') < converted.index('方式別セット比較')
assert "馬連</td><td>1-2" in converted and "購入予定額 100円" in converted
assert "期待純利益（推定）" in converted and "12.5円" in converted
assert "除外理由は後半" not in converted.split('</section>', 1)[0]
assert not any("<td>"+code+"</td>" in converted for code in codes)
assert "重複買い目は計上しません" in converted

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
        assert len(doc) == 6, f"front conclusion, adopted, rejected and 3 audit pages expected, got {len(doc)}"
        assert all(len(page.get_text().strip()) > 150 for page in list(doc)[3:])
        assert '最終購入結論' in doc[0].get_text() and '馬連' in doc[0].get_text()
        assert '1-2' in doc[0].get_text() and '100円' in doc[0].get_text()
        assert '採用買い目' in doc[1].get_text() and '重複買い目' in doc[1].get_text()
        assert '不採用買い目' in doc[2].get_text()

# Explicitly check no-purchase conclusion and a large, multi-type candidate set.
skipped = prediction_for(source)
skipped["final_bets"] = []
skipped["purchase_decision"] = "pass"
skipped["total_stake_yen"] = 0
skipped_html, _, _ = overlay.apply(source, skipped)
assert "最終購入結論：購入見送り" in skipped_html
assert "採用 0点／購入予定額 0円" in skipped_html
assert "購入見送りの詳しい理由" in skipped_html
assert "不採用買い目｜1/1" in skipped_html

many = prediction_for(source)
many["final_bets"] = [
    {"type":"馬連", "selection":[i, i+1], "stake_yen":100, "id":f"B{i:02d}"}
    for i in range(1, 31)
]
many["purchase_decision"] = "buy"
many["total_stake_yen"] = 3000
full, _, _ = overlay.apply(source, many)
assert "採用 30点／購入予定額 3,000円" in full
assert "ほか24点（後半に全件記載）" in full
assert "B01" not in full.split('</section>', 1)[0]
assert "馬連" in full.split('</section>', 1)[0]

print("PASS: every strategy-mode label and concrete bundle definition; full/partial adoption, 14-row A4 PDF")
