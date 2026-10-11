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
assert "BOX 1,2,3（採用1/2点）" in converted
assert "フォーメーション 1,2/2,3（採用1/2点）" in converted
assert "2頭軸マルチ 軸1,2→2,3（採用1/2点）" in converted
assert "BOX" in converted  # Normal JRA betting-screen spelling.
assert len(overlay.PAGE.findall(converted)) == 2
assert converted.index('最終購入結論｜本日の正式予想') < converted.index('採用買い目｜1/1')
assert converted.index('不採用買い目｜1/1') < converted.index('方式別セット比較')
assert "個別指定（1点）</td><td>1-2</td><td>1点×100円＝100円" in converted
assert "購入予定額 100円" in converted
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
assert "採用買い目の全件明細を参照" in full
assert sum(x["amount_yen"] for x in overlay.purchase_commands(many)) == 3000
assert sum(x["tickets"] for x in overlay.purchase_commands(many)) == 30
assert "B01" not in full.split('</section>', 1)[0]
assert "馬連" in full.split('</section>', 1)[0]


# Realistic explicit purchase instructions: never turn part of a box into a BOX.
def line(typ, nums, idx, stake=100):
    return {"type": typ, "selection": nums, "stake_yen": stake, "id": f"B{idx:02d}"}

box_lines = [[2, 5], [2, 8], [5, 8]]
box_def = {"strategy_id": "BOX1", "type": "馬連",
           "strategy_kind": "box", "definition": {"horses": [2,5,8]},
           "lines": [{"type":"馬連", "selection":x} for x in box_lines]}
full_box = {"final_bets":[line("馬連", nums, i+1) for i,nums in enumerate(box_lines)],
            "purchase_strategy_evaluations":[box_def]}
full_command = overlay.purchase_commands(full_box)
assert len(full_command) == 1 and full_command[0]["method"] == "BOX"
assert full_command[0]["numbers"] == "2・5・8"
assert full_command[0]["tickets"] == 3 and full_command[0]["amount_yen"] == 300
partial_box = {"final_bets":[line("馬連",[2,5],1),line("馬連",[2,8],2)],
               "purchase_strategy_evaluations":[box_def]}
partial_command = overlay.purchase_commands(partial_box)
assert len(partial_command) == 1
assert partial_command[0]["method"] == "1頭軸流し"
assert partial_command[0]["numbers"] == "軸馬：2／相手馬：5・8"
assert sum(x["amount_yen"] for x in partial_command) == 200
# 1,2,3 exact ordered permutations: six trifecta BOX tickets, not three unordered lines.
from itertools import permutations
ordered = [list(p) for p in permutations([1, 2, 3])]
trifecta = {"final_bets":[line("三連単", nums, i+1) for i,nums in enumerate(ordered)],
    "purchase_strategy_evaluations":[{"strategy_id":"TBOX","type":"三連単",
    "strategy_kind":"box","definition":{"horses":[1,2,3]},
    "lines":[{"type":"三連単","selection":x} for x in ordered]}]}
trifecta_cmd = overlay.purchase_commands(trifecta)
assert len(trifecta_cmd) == 1 and trifecta_cmd[0]["method"] == "BOX"
assert trifecta_cmd[0]["tickets"] == 6 and trifecta_cmd[0]["amount_yen"] == 600
trifecta["final_bets"].pop()
assert all(x["method"] == "個別指定（1点）" for x in overlay.purchase_commands(trifecta))
# Full axis wheel must be clearly specified; a partial wheel becomes individual tickets.
wheel = {"strategy_id":"W1","type":"馬連","strategy_kind":"key_wheel",
         "definition":{"key":2,"partners":[5,8]},
         "lines":[{"type":"馬連","selection":[2,5]},{"type":"馬連","selection":[2,8]}]}
wheel_all = {"final_bets":[line("馬連",[2,5],1),line("馬連",[2,8],2)],
             "purchase_strategy_evaluations":[wheel]}
wheel_cmd = overlay.purchase_commands(wheel_all)
assert len(wheel_cmd) == 1
assert wheel_cmd[0]["method"] == "1頭軸流し" and wheel_cmd[0]["numbers"] == "軸馬：2／相手馬：5・8"
wheel_all["final_bets"] = [line("馬連",[2,5],1)]
assert overlay.purchase_commands(wheel_all)[0]["method"] == "個別指定（1点）"

# Wrong source expansion must not cause a wheel/formation label to buy extra tickets.
bad_wheel = {"final_bets":[line("馬連",[2,5],1),line("馬連",[5,8],2)],
    "purchase_strategy_evaluations":[wheel]}
assert len(overlay.purchase_commands(bad_wheel)) == 1
assert overlay.purchase_commands(bad_wheel)[0]["numbers"] == "軸馬：5／相手馬：2・8"
form = {"strategy_id":"F1","type":"馬単","strategy_kind":"formation",
        "definition":{"slots":[[2],[5,8]]},
        "lines":[{"type":"馬単","selection":[2,5]},{"type":"馬単","selection":[2,8]}]}
form_pred = {"final_bets":[line("馬単",[2,5],1),line("馬単",[2,8],2)],
             "purchase_strategy_evaluations":[form]}
form_cmd = overlay.purchase_commands(form_pred)
assert len(form_cmd) == 1 and form_cmd[0]["method"] == "フォーメーション"
assert form_cmd[0]["numbers"] == "1着：2／2着：5,8"
assert "● 1着：2" in overlay._format_purchase_numbers(form_cmd[0])
assert "└─ 2着：5・8" in overlay._format_purchase_numbers(form_cmd[0])
form_pred["final_bets"].pop()
assert overlay.purchase_commands(form_pred)[0]["method"] == "個別指定（1点）"

# Do not label as BOX when there are multiple stakes, even with all combinations present.
different_stakes = {"final_bets":[line("馬連",nums,i+1,200 if i==0 else 100)
                                 for i,nums in enumerate(box_lines)],
                    "purchase_strategy_evaluations":[box_def]}
assert all(x["method"] != "BOX" for x in overlay.purchase_commands(different_stakes))
# Include a cross-type purchase plan and ensure the HTML describes the actual operation.
screen_prediction = prediction_for(source)
for st in screen_prediction["purchase_strategy_evaluations"]:
    if st["strategy_kind"] == "box":
        st["definition"] = box_def["definition"]
        st["lines"] = box_def["lines"]
screen_prediction["final_bets"] = [line("馬連",n,i+1) for i,n in enumerate(box_lines)]
screen_prediction["total_stake_yen"] = 300
screen_html, _, _ = overlay.apply(source, screen_prediction)
assert "BOX</td><td>2・5・8</td><td>3点×100円＝300円" in screen_html
assert "フォーメーションは着順・列ごとのツリー表記" in screen_html
assert "不採用買い目｜1/1" in screen_html
screen_prediction["final_bets"] = [line("馬連",[2,5],1)]
screen_prediction["total_stake_yen"] = 100
screen_html, _, _ = overlay.apply(source, screen_prediction)
first_page = screen_html.split('</section>', 1)[0]
assert "BOX</td>" not in first_page
assert "個別指定（1点）</td><td>2-5" in first_page


# Grouped buy instructions MUST be independent of strategy presence or historical audit metadata.
synthetic_box = {"final_bets":[line("馬連", n, i + 1) for i, n in enumerate(box_lines)],
                 "purchase_strategy_evaluations":[]}
synthetic_commands = overlay.purchase_commands(synthetic_box)
assert len(synthetic_commands) == 1
assert synthetic_commands[0]["method"] == "BOX"
assert synthetic_commands[0]["numbers"] == "2・5・8"
assert synthetic_commands[0]["amount_yen"] == 300
synthetic_wheel = {"final_bets":[line("馬連", n, i+1)
                                  for i,n in enumerate([[3,5],[3,7],[3,9]])],
                   "purchase_strategy_evaluations":[]}
wheel_commands = overlay.purchase_commands(synthetic_wheel)
assert len(wheel_commands) == 1 and wheel_commands[0]["method"] == "1頭軸流し"
assert wheel_commands[0]["numbers"] == "軸馬：3／相手馬：5・7・9"
assert wheel_commands[0]["tickets"] == 3

# The vertical tree is for *purchase* formations. Ordered bets use 着, unordered bets 列目.
for typ, slots, expected in [
    ("三連単", [[2],[5],[8,9]], ("● 1着：2", "└─ 2着：5", "└─ 3着：8・9")),
    ("三連複", [[2],[5],[8,9]], ("● 1列目：2", "└─ 2列目：5", "└─ 3列目：8・9"))
]:
    from itertools import product
    lines = [list(x) for x in product(*slots)]
    formation = {"strategy_id":"FORM-"+typ, "type":typ,
                 "strategy_kind":"formation", "definition":{"slots":slots},
                 "lines":[{"type":typ,"selection":x} for x in lines]}
    pred = {"final_bets":[line(typ, x, i+1) for i,x in enumerate(lines)],
            "purchase_strategy_evaluations":[formation]}
    cm = overlay.purchase_commands(pred)
    assert len(cm) == 1 and cm[0]["method"] == "フォーメーション"
    rendered = overlay._format_purchase_numbers(cm[0])
    assert "jra-formation-tree" in rendered
    for row in expected:
        assert row in rendered, (typ, row, rendered)
    assert cm[0]["tickets"] == len(lines)
    pred["final_bets"].pop()
    assert all(c.get("_formation_slots") is None for c in overlay.purchase_commands(pred))

print("PASS: every strategy-mode label and concrete bundle definition; full/partial adoption, 14-row A4 PDF")
