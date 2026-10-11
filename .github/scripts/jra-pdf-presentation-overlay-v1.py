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
    "box": "BOX",
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
    return ",".join(map(str, values))


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
        return "/".join(numbers(slot) for slot in slots)
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


COVER = re.compile(
    r'<section class="page"><div class="chapter">本日の正式予想｜表紙</div>(.*?)</section>', re.S
)
TYPE_ORDER = ("単勝", "複勝", "枠連", "馬連", "馬単", "ワイド", "三連複", "三連単")



def input_numbers(st):
    """Turn the frozen strategy definition into the exact betting-screen input."""
    d = st.get("definition") or {}
    kind = st["strategy_kind"]
    if kind == "formation":
        slots = d["slots"]
        if len(slots) not in (2, 3):
            raise ValueError("JRA purchase blocker: malformed formation slots")
        labels = (["1着", "2着", "3着"] if st["type"] in ("馬単", "三連単")
                  else ["1列", "2列", "3列"])
        return "／".join(f"{labels[i]}：{numbers(slot)}" for i, slot in enumerate(slots))
    if kind in ("single",):
        return "-".join(map(str, d["selection"]))
    if kind in ("box", "multiple_singles"):
        return "・".join(numbers(d["horses"]).split(","))
    if kind in ("key_wheel", "key_wheel_first", "key_wheel_second", "key_wheel_multi",
                "one_key_wheel", "one_key_fixed", "one_key_multi"):
        position = ("1着" if kind == "key_wheel_first" else
                    "2着" if kind == "key_wheel_second" else
                    f"{d['position']}着" if kind == "one_key_fixed" else "軸")
        if st["type"] == "馬連" and kind == "key_wheel":
            return f"軸馬：{d['key']}／相手馬：{'・'.join(numbers(d['partners']).split(','))}"
        return f"{position}：{d['key']}／相手：{'・'.join(numbers(d['partners']).split(','))}"
    if kind in ("two_key_wheel", "two_key_fixed", "two_key_multi"):
        if kind == "two_key_fixed":
            axis = {pos: val for pos, val in zip(d["positions"], d["axes"])}
            slots = "／".join(f"{p}着:{axis[p]}" for p in sorted(axis))
            return slots + f"／相手:{numbers(d['partners'])}"
        return f"軸:{numbers(d['axes'])}／相手:{numbers(d['partners'])}"
    raise ValueError("JRA purchase blocker: undefined betting method " + kind)


def _valid_box_lines(st, keys):
    """Never call an incomplete or inconsistent set a JRA BOX."""
    from itertools import combinations, permutations
    from math import comb
    d = st.get("definition") or {}
    h = d.get("horses")
    if not isinstance(h, list) or len(set(h)) != len(h) or len(h) < 2:
        return False
    kind = st["type"]
    arity = 3 if kind in ("三連複", "三連単") else 2
    if len(h) < arity:
        return False
    unordered = kind in ("枠連", "馬連", "ワイド", "三連複")
    if kind not in ("枠連", "馬連", "馬単", "ワイド", "三連複", "三連単"):
        return False
    # Build independently of the prestart strategy mode. Restrict Box to distinct
    # numbers: frame-box repeated-frame bets are deliberately not synthesized.
    expected = {
        bet_key({"type":kind,"selection":list(combo)})
        for pick in combinations(h, arity)
        for combo in ([pick] if unordered else permutations(pick))
    }
    return keys == expected and len(keys) == (
        comb(len(h), arity) if unordered else
        comb(len(h), arity) * (2 if arity == 2 else 6)
    )




def _strategy_lines_match_definition(st, actual_keys):
    """Independently re-expand the exact JRA purchase operation before printing it.

    The mode name alone must never authorize a whole BOX / wheel purchase.
    """
    from itertools import combinations, permutations, product
    typ, kind = st["type"], st["strategy_kind"]
    d = st.get("definition") or {}
    if kind == "box":
        return _valid_box_lines(st, actual_keys)
    try:
        raw = []
        uniq = lambda xs: list(dict.fromkeys(xs))
        if kind == "multiple_singles":
            raw = [[x] for x in d["horses"]]
        elif kind == "formation":
            raw = [list(x) for x in product(*d["slots"])]
        elif kind == "key_wheel":
            raw = [[d["key"], h] for h in d["partners"]]
        elif kind in ("key_wheel_first","key_wheel_second","key_wheel_multi"):
            for h in d["partners"]:
                if kind != "key_wheel_second":
                    raw.append([d["key"],h])
                if kind != "key_wheel_first":
                    raw.append([h,d["key"]])
        elif kind == "one_key_wheel":
            raw = [[d["key"],a,b] for a,b in combinations(uniq(d["partners"]),2)]
        elif kind == "two_key_wheel":
            raw = [list(d["axes"])+[h] for h in d["partners"]]
        elif kind in ("one_key_fixed", "one_key_multi"):
            for a,b in combinations(uniq(d["partners"]),2):
                for ordered in permutations([d["key"],a,b]):
                    if kind == "one_key_multi" or ordered[d["position"]-1] == d["key"]:
                        raw.append(list(ordered))
        elif kind in ("two_key_fixed", "two_key_multi"):
            for h in d["partners"]:
                values = [*d["axes"],h]
                if kind == "two_key_multi":
                    raw.extend([list(p) for p in permutations(values)])
                else:
                    row = [None,None,None]
                    row[d["positions"][0]-1] = d["axes"][0]
                    row[d["positions"][1]-1] = d["axes"][1]
                    row[row.index(None)] = h
                    raw.append(row)
        else:
            return False
        arity = 1 if typ in ("単勝","複勝") else 3 if typ in ("三連複","三連単") else 2
        keys = set()
        for sel in raw:
            if len(sel) != arity or not all(type(x) is int and x > 0 for x in sel):
                return False
            if typ != "枠連" and len(set(sel)) != len(sel):
                continue
            keys.add(bet_key({"type":typ, "selection":sel}))
        return keys == actual_keys and bool(keys)
    except (KeyError, TypeError, ValueError, IndexError):
        return False


PURCHASE_MODES_BY_TYPE = {
    "単勝": {"multiple_singles"},
    "複勝": {"multiple_singles"},
    "枠連": {"box","key_wheel","formation"},
    "馬連": {"box","key_wheel","formation"},
    "馬単": {"box","key_wheel_first","key_wheel_second","key_wheel_multi","formation"},
    "ワイド": {"box","key_wheel","formation"},
    "三連複": {"box","one_key_wheel","two_key_wheel","formation"},
    "三連単": {"box","one_key_fixed","two_key_fixed","one_key_multi","two_key_multi","formation"},
}



def _display_only_group_candidates(final_by_key):
    """Find safe JRA BOX/馬連流し presentations directly from sealed final tickets.

    Candidate construction changes *no bets*: accepted only when independent
    ticket expansion matches every line at one common stake.
    """
    from itertools import combinations, permutations
    from math import comb, factorial
    by_type_stake = {}
    for key, bet in final_by_key.items():
        by_type_stake.setdefault((key[0], bet["stake_yen"]), set()).add(key)
    derived = []
    for (typ, unit), available in by_type_stake.items():
        if typ in ("枠連", "馬連", "馬単", "ワイド", "三連複", "三連単"):
            arity = 3 if typ in ("三連複","三連単") else 2
            ordered = typ in ("馬単", "三連単")
            max_horses = 5 if typ == "三連単" else 8
            horses = sorted(set(h for _, selection in available for h in selection))

            def box_keys(hs):
                return {
                    bet_key({"type":typ,"selection":list(row)})
                    for picked in combinations(hs, arity)
                    for row in (permutations(picked) if ordered else (picked,))
                }

            # Enumerate actual purchased 2/3-horse edges first and extend only
            # complete cliques. NEVER use combinations(all race horses, 8):
            # that causes millions of irrelevant candidates for 20+ selected
            # horse numbers, delaying PDF CI and risk of timeout.
            seeds = set(tuple(sorted(sel)) for _,sel in available
                        if len(sel) == arity and len(set(sel)) == arity)
            visited = set()
            def explore(hs):
                if hs in visited:
                    return
                visited.add(hs)
                keys = box_keys(hs)
                if not keys.issubset(available):
                    return
                if len(keys) >= 2:
                    sid = f"DISPLAY_BOX_{typ}_{unit}_{'_'.join(map(str,hs))}"
                    derived.append({"strategy_id":sid, "type":typ,
                                    "strategy_kind":"box",
                                    "definition":{"horses":list(hs)},
                                    "lines":[{"type":k[0],"selection":list(k[1])}
                                             for k in sorted(keys)]})
                if len(hs) >= max_horses:
                    return
                for h in horses:
                    if h > hs[-1]:
                        # A new node must connect to EVERY complete edge/triple.
                        # Failed branches cannot become valid BOX supersets.
                        explore((*hs, h))
            for hs in sorted(seeds):
                explore(hs)
        if typ == "馬連":
            horses = sorted(set(h for _, selection in available for h in selection))
            for axis in horses:
                partners = sorted({
                    next(h for h in selection if h != axis)
                    for _,selection in available if axis in selection and
                    len(selection) == 2 and selection[0] != selection[1]
                })
                if len(partners) < 2:
                    continue
                keys = {bet_key({"type":"馬連","selection":[axis,p]}) for p in partners}
                if keys.issubset(available):
                    sid = f"DISPLAY_WHEEL_{typ}_{unit}_{axis}"
                    derived.append({"strategy_id":sid,"type":typ,
                                    "strategy_kind":"key_wheel",
                                    "definition":{"key":axis,"partners":partners},
                                    "lines":[{"type":"馬連","selection":[axis,p]}
                                             for p in partners]})
    return derived


def purchase_commands(prediction):
    """Prove each on-screen instruction expands to *exactly* the sealed final_bets.

    A partial box/wheel/formation is NEVER advertised as a full-form purchase.
    Remaining lines are individual purchase instructions; duplicates are forbidden.
    """
    final = prediction.get("final_bets")
    if not isinstance(final, list):
        raise ValueError("JRA purchase blocker: missing immutable final bets")
    final_by_key = {bet_key(x): x for x in final}
    if len(final_by_key) != len(final):
        raise ValueError("JRA purchase blocker: duplicate final purchase keys")
    for x in final:
        if x["type"] not in TYPE_ORDER or not isinstance(x.get("stake_yen"), int) or x["stake_yen"] <= 0:
            raise ValueError("JRA purchase blocker: incorrect final ticket amount/type")

    eligible = []
    ignored = {"single"}
    priority = {"box":0, "key_wheel":1, "key_wheel_first":1, "key_wheel_second":1,
                "key_wheel_multi":1, "one_key_wheel":1, "two_key_wheel":1,
                "one_key_fixed":1, "two_key_fixed":1, "one_key_multi":1,
                "two_key_multi":1, "formation":2, "multiple_singles":3}
    for st in (prediction.get("purchase_strategy_evaluations") or []) + _display_only_group_candidates(final_by_key):
        kind = st.get("strategy_kind")
        if kind in ignored or kind not in priority or kind not in PURCHASE_MODES_BY_TYPE.get(st.get("type"), set()):
            continue
        lines = st.get("lines") or []
        keys = {bet_key(x) for x in lines}
        if len(keys) < 2 or len(keys) != len(lines) or not keys.issubset(final_by_key):
            continue
        amounts = {final_by_key[k]["stake_yen"] for k in keys}
        if len(amounts) != 1:
            continue
        if not _strategy_lines_match_definition(st, keys):
            continue
        eligible.append((-len(keys), priority[kind], TYPE_ORDER.index(st["type"]),
                         st["strategy_id"], st, keys))
    eligible.sort(key=lambda x:x[:4])

    used = set()
    commands = []
    for _, _, _, sid, st, keys in eligible:
        if keys & used:
            continue
        try:
            specification = input_numbers(st)
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"JRA purchase blocker: invalid group definition {sid}: {e}") from e
        unit = final_by_key[next(iter(keys))]["stake_yen"]
        commands.append({"type":st["type"],"method":METHOD_NAMES[st["strategy_kind"]],
                         "numbers":specification,"tickets":len(keys),"unit_yen":unit,
                         "amount_yen":unit*len(keys),"_keys":keys,
                         "_formation_slots": [list(x) for x in st["definition"]["slots"]]
                              if st["strategy_kind"] == "formation" else None})
        used.update(keys)

    for k, line in sorted(final_by_key.items(), key=lambda x:
                          (TYPE_ORDER.index(x[0][0]), x[0][1])):
        if k not in used:
            unit = line["stake_yen"]
            commands.append({"type":line["type"],"method":"個別指定（1点）",
                             "numbers":"-".join(map(str,line["selection"])),
                             "tickets":1,"unit_yen":unit,"amount_yen":unit,"_keys":{k}})
            used.add(k)

    count = sum(x["tickets"] for x in commands)
    yen = sum(x["amount_yen"] for x in commands)
    if used != set(final_by_key) or count != len(final) or yen != sum(
            x["stake_yen"] for x in final):
        raise ValueError("JRA purchase blocker: instructions differ from immutable final_bets")
    return sorted(commands,key=lambda x:(TYPE_ORDER.index(x["type"]),
                                          -x["tickets"], x["method"],x["numbers"]))



def _format_purchase_numbers(cmd):
    """Show actual betting-screen entry, tree for an ordered/unordered formation."""
    if cmd.get("_formation_slots") is None:
        return html_module.escape(cmd["numbers"], quote=True)
    slots = cmd["_formation_slots"]
    typ = cmd["type"]
    if typ not in ("枠連", "馬連", "馬単", "ワイド", "三連複", "三連単"):
        raise ValueError("JRA purchase blocker: invalid formation type")
    if len(slots) not in (2, 3):
        raise ValueError("JRA purchase blocker: invalid formation tree depth")
    labels = (("1着", "2着", "3着") if typ in ("馬単", "三連単")
              else ("1列目", "2列目", "3列目"))
    branches = []
    for i, slot in enumerate(slots):
        branch = "└─" if i == len(slots) - 1 else "├─"
        selection = "・".join(numbers(slot).split(","))
        branches.append('<div style="margin:0;white-space:nowrap;">' +
                        html_module.escape(f"{branch} {labels[i]}：{selection}", quote=True) +
                        '</div>')
    return ('<div class="jra-formation-tree" '
            'style="font-size:10pt;line-height:1.3;white-space:nowrap;">' +
            "".join(branches) + '</div>')


def cover_conclusion(prediction, original_cover):
    """Place the final buy/no-buy decision and ticket types first; preserve all tail details."""
    final = prediction.get("final_bets")
    if not isinstance(final, list):
        raise ValueError("JRA presentation blocker: frozen final_bets missing")
    cost = prediction.get("total_stake_yen")
    if not isinstance(cost, int) or cost < 0 or cost > 6000:
        raise ValueError("JRA presentation blocker: invalid frozen purchase budget")
    bought = prediction.get("purchase_decision") == "buy"
    if bought != bool(final) or sum(x.get("stake_yen", 0) for x in final) != cost:
        raise ValueError("JRA presentation blocker: purchase decision/cost mismatch")
    if len({x["id"] for x in final}) != len(final):
        raise ValueError("JRA presentation blocker: duplicate final ticket ID")
    if len({bet_key(x) for x in final}) != len(final):
        raise ValueError("JRA presentation blocker: duplicate final ticket")
    by_type = {}
    for line in final:
        typ = line["type"]
        selection = line["selection"]
        amount = line["stake_yen"]
        if typ not in TYPE_ORDER or not isinstance(selection, list) or not selection or (
            not isinstance(amount, int) or amount <= 0
        ):
            raise ValueError("JRA presentation blocker: malformed final ticket")
        by_type.setdefault(typ, []).append(line)

    # The approved original report has an explicit race title and dated race context.
    # Keep them verbatim; only the prioritization of the front-page content changes.
    front = re.match(r'\s*(<h1>.*?</h1>)(<p>.*?</p>)', original_cover, re.S)
    if not front:
        raise ValueError("JRA presentation blocker: frozen cover heading changed")
    title, race_details = front.groups()
    esc = lambda x: html_module.escape(str(x), quote=True)
    max_items = int(__import__("os").getenv("JRA_COVER_BETS_PER_TYPE", "6"))
    if max_items < 1:
        raise ValueError("JRA presentation blocker: at least one ticket per type must be visible")
    state = "購入候補あり" if bought else "購入見送り"
    info = (f'<div class="hero"><div class="m">最終購入結論：{state}</div>'
            f'<p>採用 {len(final)}点／購入予定額 {cost:,}円／予算上限6,000円</p></div>')
    if not bought:
        details = '<p>最終採用の買い目はありません。購入見送りの詳しい理由は後半の購入監査を参照してください。</p>'
    else:
        # "BOX" / "軸流し" is printed ONLY when every generated line is
        # present in the sealed final_bets with matching unit stake. Otherwise
        # list the exact individual selections, never the enticing whole BOX.
        commands = purchase_commands(prediction)
        table = ('<table class="table dense"><thead><tr>'
                 '<th>券種</th><th>買い方</th><th>指定する馬番・枠番</th>'
                 '<th>点数×単価＝購入額</th></tr></thead><tbody>')
        for typ in TYPE_ORDER:
            typ_cmds = [x for x in commands if x["type"] == typ]
            for cmd in typ_cmds[:max_items]:
                table += ('<tr><td>'+esc(typ)+'</td><td>'+esc(cmd["method"])+'</td>'
                          '<td>'+_format_purchase_numbers(cmd)+'</td><td>'+
                          f'{cmd["tickets"]}点×{cmd["unit_yen"]:,}円＝{cmd["amount_yen"]:,}円'
                          '</td></tr>')
            hidden = typ_cmds[max_items:]
            if hidden:
                table += ('<tr><td>'+esc(typ)+'</td><td>続きは後半</td><td>'+
                          f'残り{len(hidden)}操作・{sum(x["tickets"] for x in hidden)}点。'
                          '採用買い目の全件明細を参照</td><td>'+
                          f'{sum(x["amount_yen"] for x in hidden):,}円</td></tr>')
        table += "</tbody></table>"
        details = ('<p class="tiny">各行を「券種→買い方→指定馬番→金額」の順に入力。'
                   'BOX・流し・フォーメーションは表示された購入操作が採用組番と一致する場合だけ使用。'
                   'フォーメーションは着順・列ごとのツリー表記。'
                   '一部しか再現できない場合は「個別指定（1点）」です。</p>'+table)

    portfolio = prediction.get("purchase_portfolio_selection") or {}
    prof = (portfolio.get("expected_net_profit_yen_scenarios") or {}).get("central")
    hit = (portfolio.get("hit_probability_scenarios") or {}).get("central")
    loss = (portfolio.get("loss_probability_scenarios") or {}).get("central")
    def yen(v):
        return f"{v:,.1f}円" if isinstance(v, (int, float)) else "算定対象外"
    def pct(v):
        return f"{v*100:.1f}%" if isinstance(v, (int, float)) else "算定対象外"
    indicators = ('<table class="table dense"><thead><tr>'
                  '<th>集合的中率（推定）</th><th>期待純利益（推定）</th>'
                  '<th>実損確率（推定）</th></tr></thead><tbody><tr>'
                  f'<td>{pct(hit) if bought else "算定対象外"}</td>'
                  f'<td>{yen(prof) if bought else "算定対象外"}</td>'
                  f'<td>{pct(loss) if bought else "算定対象外"}</td>'
                  '</tr></tbody></table>')
    note = ('<p class="tiny">※買い目と投資額は確定した発走前予想の表示です。実際の馬券は購入していません。'
            '確率・期待利益は未校正モデルによる推定で、的中や利益を保証しません。'
            '詳細は後半の「採用買い目」、不採用理由は「不採用買い目」、'
            '方式比較は「購入最適化監査」にあります。</p>')
    body = (title + race_details + info + '<h3>最終の買い目（購入候補）</h3>' +
            details + '<h3>購入セット全体の評価</h3>' + indicators + note)
    return '<section class="page"><div class="chapter">最終購入結論｜本日の正式予想</div>' + body + '</section>'


def move_conclusion_to_front(source, prediction):
    # Match precisely one first-page original; leave the 4 other front pages and
    # all horse / adopted / rejected / audit chapters in their approved order.
    if not source.startswith("<!doctype html>"):
        raise ValueError("JRA presentation blocker: unexpected report document")
    updated, found = COVER.subn(
        lambda m: cover_conclusion(prediction, m.group(1)), source, count=1)
    if found != 1 or COVER.search(updated):
        raise ValueError("JRA presentation blocker: ambiguous original cover")
    if updated.count("最終購入結論｜本日の正式予想") != 1:
        raise ValueError("JRA presentation blocker: front-page conclusion absent")
    if updated.count('<section class="page">') != source.count('<section class="page">'):
        raise ValueError("JRA presentation blocker: presentation altered page sections")
    return updated


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
            shown = f"{label} {detail}（採用{adopted}/{total}点）"
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
    selected_note = ("1ページ目の購入方法は、確定買い目と完全一致する買い方だけを表示。"
                     "ボックス等の一部だけ採用した場合は「個別指定」に分解します。"
                     "以下は実際に選ぶ個別組番の全件明細です。重複買い目は計上しません。")
    anchor = re.compile(r'(<section class="page"><div class="chapter">採用買い目｜1/\d+</div>)')
    converted, count = anchor.subn(
        lambda m: m.group(1) + '<p>' + html_module.escape(selected_note) + '</p>',
        converted, count=1)
    if count != 1:
        raise ValueError("JRA presentation blocker: selected-ticket chapter absent")
    converted = move_conclusion_to_front(converted, prediction)
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
