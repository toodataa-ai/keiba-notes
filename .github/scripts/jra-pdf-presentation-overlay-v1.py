#!/usr/bin/env python3
"""Presentation-only Japanese labels for the frozen JRA v3.12 HTML/PDF.

No prediction, odds, strategy evaluation, selected bet, or historical artifact is changed.
The original v3.12 report renderer and approved CSS remain byte-identical.
"""
import argparse
import html as html_module
import json
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
METHOD_ROW = re.compile(r'(<tr><td>([^<]+)</td><td>([^<]+)</td><td>)([^<]+)(</td>)')
PAGE = re.compile(
    r'<section class="page"><div class="chapter">購入最適化監査｜方式別セット比較 \d+/\d+</div>(.*?)</section>', re.S
)
ROW_COUNT = re.compile(r'<tbody>(.*?)</tbody>', re.S)


def numbers(values):
    if not isinstance(values, list) or not values or any(not isinstance(x, int) for x in values):
        raise ValueError("JRA presentation blocker: incomplete strategy horse-number definition")
    return "・".join(map(str, values))


def method_definition(st):
    """Display the specific combinations without changing the source strategy."""
    d = st.get("definition") or {}
    kind = st["strategy_kind"]
    if kind == "single":
        return numbers(d["selection"])
    if kind == "multiple_singles" or kind == "box":
        return numbers(d["horses"])
    if kind == "formation":
        slots = d["slots"]
        return "／".join(f"{i}列:{numbers(slot)}" for i, slot in enumerate(slots, 1))
    if kind in ("key_wheel", "key_wheel_first", "key_wheel_second", "key_wheel_multi",
                "one_key_wheel", "one_key_fixed", "one_key_multi"):
        prefix = ("1着" if kind == "key_wheel_first" else
                  "2着" if kind == "key_wheel_second" else
                  f"{d['position']}着" if kind == "one_key_fixed" else "軸")
        return f"{prefix}{d['key']}→{numbers(d['partners'])}"
    if kind in ("two_key_wheel", "two_key_fixed", "two_key_multi"):
        detail = f"軸{numbers(d['axes'])}"
        if kind == "two_key_fixed":
            detail += f"（位置{numbers(d['positions'])}）"
        return f"{detail}→{numbers(d['partners'])}"
    if kind == "win_place_support":
        return f"馬番{d['horse']}の単複"
    raise ValueError("JRA presentation blocker: unsupported strategy definition " + kind)


def bet_key(line):
    typ = line["type"]
    sel = tuple(int(x) for x in line["selection"])
    if typ in ("枠連", "馬連", "ワイド", "三連複"):
        sel = tuple(sorted(sel))
    return typ, sel


def strategy_registry(prediction):
    if not isinstance(prediction, dict):
        raise ValueError("JRA presentation blocker: sealed prediction JSON is required")
    strategies = prediction.get("purchase_strategy_evaluations")
    if not isinstance(strategies, list) or not strategies:
        raise ValueError("JRA presentation blocker: strategy definitions missing")
    final = prediction.get("final_bets")
    if not isinstance(final, list):
        raise ValueError("JRA presentation blocker: final_bets missing")
    selected = {bet_key(x) for x in final}
    registry = {}
    for st in strategies:
        sid = st["strategy_id"]
        if sid in registry or st["strategy_kind"] not in METHOD_NAMES:
            raise ValueError("JRA presentation blocker: duplicate/unmapped strategy " + sid)
        lines = st.get("lines")
        if not isinstance(lines, list) or not lines:
            raise ValueError("JRA presentation blocker: expanded strategy lines missing " + sid)
        ticket_keys = {bet_key(x) for x in lines}
        if len(ticket_keys) != len(lines):
            raise ValueError("JRA presentation blocker: duplicate expanded strategy lines " + sid)
        registry[sid] = (st, len(ticket_keys & selected), len(ticket_keys))
    return registry

def apply(html_source, prediction):
    pages = PAGE.findall(html_source)
    if not pages:
        raise ValueError("JRA presentation blocker: mode comparison pages absent")
    total_before = sum(len(re.findall(r'<tr>', m.group(1))) for p in pages for m in ROW_COUNT.finditer(p))
    changed = [0]
    registry = strategy_registry(prediction)
    seen = set()

    def transform_table(match):
        section = match.group(0)
        if '<th>方式</th>' not in section or '<th>ID</th>' not in section:
            return section

        def transform_row(row):
            sid, typ, raw = row.group(2), row.group(3), row.group(4)
            if raw not in METHOD_NAMES:
                raise ValueError("JRA presentation blocker: unmapped ticket method " + raw)
            if sid not in registry or sid in seen:
                raise ValueError("JRA presentation blocker: missing/duplicate strategy definition " + sid)
            st, adopted, total = registry[sid]
            if st["type"] != typ or st["strategy_kind"] != raw:
                raise ValueError("JRA presentation blocker: strategy/type mismatch " + sid)
            detail = html_module.escape(method_definition(st), quote=True)
            state = "全点採用" if adopted == total else "一部採用" if adopted else "不採用"
            label = html_module.escape(METHOD_NAMES[raw], quote=True)
            shown = (f"{label}<div class=\"tiny\">{detail}｜{state}{adopted}/{total}点</div>")
            seen.add(sid)
            changed[0] += 1
            return row.group(1) + shown + row.group(5)

        result = METHOD_ROW.sub(transform_row, section)
        for original, localized in STATUS_NAMES.items():
            result = result.replace('<td>' + original + '</td>', '<td>' + localized + '</td>')
        return result

    converted = TABLE.sub(transform_table, html_source)
    if changed[0] != total_before or total_before == 0 or seen != set(registry):
        raise ValueError(
            f"JRA presentation blocker: mapped {changed[0]} / {total_before} strategy rows"
        )
    if len(PAGE.findall(converted)) != len(pages):
        raise ValueError("JRA presentation blocker: comparison page count changed")
    # The original final_bets table remains unchanged. Explain when a final cross-type
    # portfolio contains only part of a listed BOX/formation/wheel.
    selected_note = ("採用した個別買い目は、ボックス・流し・フォーメーション等の"
                     "全点購入案と必ずしも一致しません。監査表には馬番の組合せと"
                     "全点採用／一部採用／不採用を区別して表示。重複購入は計上しません。")
    anchor = re.compile(r'(<section class="page"><div class="chapter">採用買い目｜1/\d+</div>)')
    converted, count = anchor.subn(
        lambda m: m.group(1) + '<p>' + html_module.escape(selected_note) + '</p>',
        converted, count=1)
    if count != 1:
        raise ValueError("JRA presentation blocker: selected-ticket chapter absent")
    return converted, changed[0], len(pages)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    src = args.html.read_text(encoding="utf-8")
    prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
    if args.check:
        if any('<td>' + code + '</td>' in src for code in METHOD_NAMES):
            raise SystemExit("JRA presentation blocker: raw method code displayed")
        if not PAGE.findall(src):
            raise SystemExit("JRA presentation blocker: no audit pages")
        print("PASS: purchase-method labels are Japanese")
        return
    result, rows, pages = apply(src, prediction)
    args.html.write_text(result, encoding="utf-8")
    print(f"PASS: {rows} method labels translated across {pages} audit pages")

if __name__ == "__main__":
    main()
