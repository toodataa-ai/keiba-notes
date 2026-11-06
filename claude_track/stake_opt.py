"""Claude STEP2：期待利益を最大にする買い目と金額（研究用・仮想の買い目）。
入力は STEP1 の win_prob と、STEP1 を保存したあとに取れた公開オッズだけ。結果は使わない。
考え方：
  1. 確率：Claudeの勝つ確率と、単勝オッズが示す確率（控除分を補正して合計1）を、対数で重み w:(1-w) で混ぜる。
     （Claude の予想だけを信じて期待値を最大にすると、予想の誤差まで拾って過大評価しやすいため。w は実績がたまったら決め直す）
  2. 各組番の的中確率を Plackett-Luce（順位の出方）で出し、期待値 = 的中確率 × オッズ − 1 を作る（ワイドは下限オッズ）。
  3. 的中確率が min_prob 以上で、期待値が min_ev を超える組番を、期待値の高い順に 100 円ずつ積む。制約：合計 budget 以内、
     1点 ticket_cap 以内、1頭に絡む金額 horse_cap×budget 以内。期待値がプラスの組番が無ければ見送り。
決定的（同じ入力なら同じ結果）。"""
from __future__ import annotations

import json
import math
from itertools import permutations
from pathlib import Path

PARAMS = {"w": 0.5, "budget": 6000, "unit": 100, "ticket_cap": 1000, "horse_cap": 0.60, "min_ev": 0.0, "min_prob": 0.05,
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
        if ev > P["min_ev"] and pr >= P["min_prob"]:
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


# ---------------------------------------------------------------------------
# anchored_v1（2026-11-06 設計・Opus 案）：値段を基準に、自分の見方で傾ける。研究用の仮想の買い目。
#  1. 自分の勝率の「平らさ」を τ 乗で直す（τ は単勝オッズ由来の確率と散らばりが同じになる値）。
#  2. 券種ごとに、その券種自身のオッズから q = (1/オッズ)÷合計 を作る（ワイドは合計3）。
#  3. p = q × (自分の組番確率 ÷ 市場の組番確率)^w を券種ごとに割り直す。
#  4. 主力：単勝・馬連・ワイド。p>=2%・オッズ<=50・期待値>0。金額は 1/4 ケリー（100円未満切り捨て）。
#  5. 一発枠：馬単・三連複・三連単から期待値の高い順に最大3点、1点100円固定（p>=0.5%、期待値>0）。
#  6. 合計6,000円・1点1,000円・1頭に絡む額60% を守る。条件を満たす組が無ければ見送り。
A_PARAMS = {"w": 0.5, "budget": 6000, "unit": 100, "ticket_cap": 1000, "horse_cap": 0.60, "kelly": 0.25,
            "bankroll": 60000, "main_types": ["単勝", "馬連", "ワイド"], "main_min_prob": 0.02, "main_max_odds": 50.0,
            "long_types": ["馬単", "三連複", "三連単"], "long_min_prob": 0.005, "long_points": 3, "long_stake": 100}


def _entropy(p):
    return -sum(v * math.log(v) for v in p.values() if v > 0)


def sharpen(model, market):
    """自分の勝率を τ 乗して割り直し、市場と散らばり（エントロピー）をそろえる。(確率, τ) を返す。"""
    keys = [h for h in model if h in market and model[h] > 0]
    target = _entropy({h: market[h] for h in keys})

    def at(t):
        raw = {h: model[h] ** t for h in keys}
        s = sum(raw.values())
        return {h: v / s for h, v in raw.items()}
    lo, hi = 0.5, 3.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _entropy(at(mid)) > target:
            lo = mid
        else:
            hi = mid
    t = (lo + hi) / 2
    return at(t), t


def _anchored_rows(entries, types, model, market, w):
    by = {}
    for e in entries:
        typ = e.get("type")
        if typ not in types:
            continue
        o = e["market_odds"]
        o = min(o) if isinstance(o, list) else o
        if not isinstance(o, (int, float)) or o <= 1:
            continue
        sel = tuple(e["selection"]) if typ in ORDERED else tuple(sorted(e["selection"]))
        if not set(sel) <= set(model):
            continue
        by.setdefault(typ, []).append((sel, float(o)))
    rows = []
    for typ, lst in by.items():
        tot = sum(1 / o for _, o in lst)
        norm = 3 if typ == "ワイド" else 1
        part = []
        for sel, o in lst:
            q = (1 / o) / tot * norm
            ratio = combo_prob(model, typ, sel) / max(combo_prob(market, typ, sel), 1e-12)
            part.append([typ, sel, o, q, q * ratio ** w])
        s = sum(x[4] for x in part)
        for x in part:
            x[4] *= norm / s
        rows += part
    return rows


def optimize_anchored(model_win, entries, params=None):
    P = {**A_PARAMS, **(params or {})}
    market = market_win_probs(entries)
    keys = [h for h in model_win if h in market and model_win[h] > 0]
    if len(keys) < 3:
        return {"decision": "skip", "skip_reason": "単勝オッズから確率を作れない", "bets": [], "params": P}
    mod, tau = sharpen({h: model_win[h] for h in keys}, {h: market[h] for h in keys})
    mk = {h: market[h] for h in keys}
    rows = _anchored_rows(entries, set(P["main_types"]) | set(P["long_types"]), mod, mk, P["w"])
    cands = [{"type": t, "selection": list(sel), "market_odds": o, "q": round(q, 6), "p": round(p, 6),
              "expected_value": round(p * o - 1, 4)} for t, sel, o, q, p in rows]
    B, unit = P["budget"], P["unit"]
    expo, bets = {}, []

    def room(sel, y):
        for h in set(sel):
            y = min(y, int((P["horse_cap"] * B - expo.get(h, 0)) // unit) * unit)
        return y
    long_c = sorted([r for r in rows if r[0] in P["long_types"] and r[4] >= P["long_min_prob"] and r[4] * r[2] - 1 > 0],
                    key=lambda r: (-(r[4] * r[2] - 1), r[0], r[1]))[:P["long_points"]]
    for t, sel, o, q, p in long_c:
        y = room(sel, P["long_stake"])
        if y < unit:
            continue
        for h in set(sel):
            expo[h] = expo.get(h, 0) + y
        bets.append({"slot": "longshot", "type": t, "selection": list(sel), "stake_yen": y, "market_odds": o,
                     "model_prob": round(p, 5), "q": round(q, 5), "expected_value": round(p * o - 1, 4)})
    long_total = sum(b["stake_yen"] for b in bets)
    main = []
    for t, sel, o, q, p in rows:
        ev = p * o - 1
        if t in P["main_types"] and p >= P["main_min_prob"] and o <= P["main_max_odds"] and ev > 0:
            f = ev / (o - 1)
            main.append((ev, t, sel, o, q, p, min(P["ticket_cap"], P["kelly"] * P["bankroll"] * f)))
    main.sort(key=lambda x: (-x[0], TYPE_ORDER[x[1]], x[2]))
    raw_total = sum(x[6] for x in main)
    scale = min(1.0, (B - long_total) / raw_total) if raw_total else 1.0
    for ev, t, sel, o, q, p, s in main:
        y = room(sel, int(s * scale // unit) * unit)
        if y < unit:
            continue
        for h in set(sel):
            expo[h] = expo.get(h, 0) + y
        bets.append({"slot": "main", "type": t, "selection": list(sel), "stake_yen": y, "market_odds": o,
                     "model_prob": round(p, 5), "q": round(q, 5), "expected_value": round(ev, 4)})
    total = sum(b["stake_yen"] for b in bets)
    return {"decision": "buy" if bets else "skip", "skip_reason": None if bets else "市場を上回る組番なし",
            "stake_method": "anchored_v1", "tau": round(tau, 4), "w": P["w"], "bets": bets, "total_stake_yen": total,
            "expected_profit_yen": round(sum(b["stake_yen"] * b["expected_value"] for b in bets), 1),
            "max_horse_exposure_yen": max(expo.values()) if total else None,
            "candidates": cands, "params": P}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--step1", required=True, help="STEP1 の JSON（horses[].no, win_prob）")
    ap.add_argument("--odds", required=True, help="claude_track/odds/<race_id>/<日時>.json（entries）")
    ap.add_argument("--w", type=float, default=None)
    ap.add_argument("--method", choices=["blend_v0", "anchored_v1"], default="blend_v0")
    a = ap.parse_args(argv)
    s1 = json.loads(Path(a.step1).read_text(encoding="utf-8"))
    model = {int(h["no"]): float(h["win_prob"]) for h in s1["horses"]}
    tot = sum(model.values())
    model = {k: v / tot for k, v in model.items()}
    entries = json.loads(Path(a.odds).read_text(encoding="utf-8"))["entries"]
    if a.method == "anchored_v1":
        out = optimize_anchored(model, entries, {} if a.w is None else {"w": a.w})
    else:
        out = optimize(model, entries, {} if a.w is None else {"w": a.w})
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
