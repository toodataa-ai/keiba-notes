"""Claude STEP2：期待利益を最大にする買い目と金額（研究用・仮想の買い目）。
入力は STEP1 の win_prob と、STEP1 を保存したあとに取れた公開オッズだけ。結果は使わない。
考え方：
  1. 確率：Claudeの勝つ確率と、単勝オッズが示す確率（控除分を補正して合計1）を、対数で重み w:(1-w) で混ぜる。
     （Claude の予想だけを信じて期待値を最大にすると、予想の誤差まで拾って過大評価しやすいため。w は実績がたまったら決め直す）
  2. 各組番の的中確率を Plackett-Luce（順位の出方）で出し、期待値 = 的中確率 × オッズ − 1 を作る（ワイドは下限オッズ）。
  3. 期待値が min_ev を超える組番を、期待値の高い順に 100 円ずつ積む。制約：合計 budget 以内、
     1点 ticket_cap 以内、1頭に絡む金額 horse_cap×budget 以内。期待値がプラスの組番が無ければ見送り。
決定的（同じ入力なら同じ結果）。"""
from __future__ import annotations

import json
import math
from itertools import permutations
from pathlib import Path

PARAMS = {"w": 0.5, "budget": 3000, "unit": 100, "ticket_cap": 1000, "horse_cap": 0.60, "min_ev": 0.0,
          "types": ["単勝", "馬連", "馬単", "ワイド", "三連複", "三連単"]}
TYPE_ORDER = {t: i for i, t in enumerate(PARAMS["types"])}
ORDERED = {"馬単", "三連単"}


def order_prob(p, order):
    rest, prob = 1.0, 1.0
    for h in order:
        if rest <= 1e-12:
            return 0.0
        prob *= p[h] / rest
        rest -= p[h]
    return prob


def combo_prob(p, typ, sel):
    if typ == "単勝":
        return p[sel[0]]
    if typ == "馬単":
        return order_prob(p, sel)
    if typ == "三連単":
        return order_prob(p, sel)
    if typ == "馬連":
        return order_prob(p, sel) + order_prob(p, sel[::-1])
    if typ == "三連複":
        return sum(order_prob(p, o) for o in permutations(sel))
    if typ == "ワイド":
        a, b = sel
        return sum(sum(order_prob(p, o) for o in permutations((a, b, c))) for c in p if c not in sel)
    raise ValueError(typ)


def market_win_probs(entries):
    inv = {}
    for e in entries:
        if e.get("type") == "単勝":
            o = e["market_odds"]
            o = min(o) if isinstance(o, list) else o
            if isinstance(o, (int, float)) and o > 0:
                inv[e["selection"][0]] = 1.0 / o
    s = sum(inv.values())
    return {h: v / s for h, v in inv.items()} if s else {}


def blend(model, market, w):
    keys = [h for h in model if h in market and model[h] > 0 and market[h] > 0]
    if not keys:
        return {}
    raw = {h: math.exp(w * math.log(model[h]) + (1 - w) * math.log(market[h])) for h in keys}
    s = sum(raw.values())
    return {h: v / s for h, v in raw.items()}


def optimize(model_win, entries, params=None):
    P = {**PARAMS, **(params or {})}
    market = market_win_probs(entries)
    p = blend(model_win, market, P["w"])
    if len(p) < 3:
        return {"decision": "skip", "skip_reason": "単勝オッズから確率を作れない", "bets": [], "params": P}
    cands = []
    for e in entries:
        typ = e.get("type")
        if typ not in P["types"]:
            continue
        sel = tuple(e["selection"]) if typ in ORDERED else tuple(sorted(e["selection"]))
        if not set(sel) <= set(p):
            continue
        o = e["market_odds"]
        o = min(o) if isinstance(o, list) else o
        if not isinstance(o, (int, float)) or o <= 0:
            continue
        pr = combo_prob(p, typ, sel)
        ev = pr * o - 1.0
        if ev > P["min_ev"]:
            cands.append((-ev, TYPE_ORDER[typ], sel, typ, float(o), pr))
    cands.sort()
    unit, B = P["unit"], P["budget"]
    stake, expo, total = {}, {}, 0
    for _, _, sel, typ, o, pr in cands:
        while total + unit <= B and stake.get((typ, sel), 0) + unit <= P["ticket_cap"] \
                and all(expo.get(h, 0) + unit <= P["horse_cap"] * B for h in set(sel)):
            stake[(typ, sel)] = stake.get((typ, sel), 0) + unit
            for h in set(sel):
                expo[h] = expo.get(h, 0) + unit
            total += unit
    meta = {(c[3], c[2]): (c[4], c[5], -c[0]) for c in cands}
    bets = [{"type": t, "selection": list(s), "stake_yen": y, "market_odds": meta[(t, s)][0],
             "model_prob": round(meta[(t, s)][1], 5), "expected_value": round(meta[(t, s)][2], 4)}
            for (t, s), y in sorted(stake.items(), key=lambda kv: (-meta[kv[0]][2], TYPE_ORDER[kv[0][0]], kv[0][1]))]
    exp_profit = sum(b["stake_yen"] * b["expected_value"] for b in bets)
    return {"decision": "buy" if bets else "skip", "skip_reason": None if bets else "期待値がプラスの組番が無い",
            "bets": bets, "total_stake_yen": total, "expected_profit_yen": round(exp_profit, 1),
            "max_horse_exposure": round(max(expo.values()) / total, 4) if total else None, "params": P}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--step1", required=True, help="STEP1 の JSON（horses[].no, win_prob）")
    ap.add_argument("--odds", required=True, help="claude_track/odds/<race_id>/<日時>.json（entries）")
    ap.add_argument("--w", type=float, default=PARAMS["w"])
    a = ap.parse_args(argv)
    s1 = json.loads(Path(a.step1).read_text(encoding="utf-8"))
    model = {int(h["no"]): float(h["win_prob"]) for h in s1["horses"]}
    tot = sum(model.values())
    model = {k: v / tot for k, v in model.items()}
    entries = json.loads(Path(a.odds).read_text(encoding="utf-8"))["entries"]
    print(json.dumps(optimize(model, entries, {"w": a.w}), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
