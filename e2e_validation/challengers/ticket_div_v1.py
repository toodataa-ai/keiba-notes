#!/usr/bin/env python3
"""EXP-003 challenger: rebuild the purchase set so that no single horse takes too much of the budget.

Deterministic and pre-registered. Inputs are ONLY information fixed before the start:
  * the sealed purchase file (formal tickets, total budget, source STEP1 path),
  * the sealed formal STEP1 win probabilities (v3.13),
  * the pre-race odds tables already saved at prestart (e2e_validation/quote-evidence/<race>/).
No results, nothing observed after the start. Marks, STEP1 and the formal tickets are not changed
and nothing is bought: the set is a hypothetical bet scored later with the official payouts.

Method (PARAMS are fixed and pinned by git blob SHA in improvement_experiments_v1.json; any edit = a new challenger):
  1. Applies only when the formal set has at least `min_tickets` tickets.
  2. Combination probabilities from the STEP1 win probabilities with a Plackett-Luce order model.
  3. Candidates: 単勝・馬連・馬単・ワイド・三連複 in the saved odds tables (ワイド uses the lower odds).
     Keep those with modelled expected value p*odds-1 > 0, best first (ties: type order, then selection).
  4. Add 100 yen tickets while the total stays within the formal total stake, skipping any ticket that
     would put more than `cap` of that budget on one horse.
"""
from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path

CHALLENGER_ID = "v3.15+ticket_div_v1"
PARAMS = {"min_tickets": 10, "cap": 0.60, "unit_yen": 100,
          "types": ["単勝", "馬連", "馬単", "ワイド", "三連複"]}
ROOT = Path(__file__).resolve().parents[2]
KINDS = {"tfw": "単勝", "ur": "馬連", "ut": "馬単", "wide": "ワイド", "sf": "三連複"}


def load_odds(race_id: str) -> dict:
    out = {}
    for kind, typ in KINDS.items():
        path = ROOT / "e2e_validation" / "quote-evidence" / race_id / f"{kind}.json"
        if not path.exists():
            continue
        for e in json.loads(path.read_text(encoding="utf-8")).get("entries", []):
            if e.get("type") != typ:
                continue
            o = e["market_odds"]
            o = min(o) if isinstance(o, list) else o
            if isinstance(o, (int, float)) and o > 0:
                key = (typ, tuple(e["selection"]) if typ == "馬単" else tuple(sorted(e["selection"])))
                out[key] = float(o)
    return out


def order_prob(p: dict, order: tuple) -> float:
    rest, prob = 1.0, 1.0
    for h in order:
        prob *= p[h] / rest
        rest -= p[h]
    return prob


def combo_prob(p: dict, typ: str, sel: tuple) -> float:
    if typ == "単勝":
        return p[sel[0]]
    if typ == "馬単":
        return order_prob(p, sel)
    if typ == "馬連":
        return order_prob(p, sel) + order_prob(p, sel[::-1])
    if typ == "三連複":
        return sum(order_prob(p, o) for o in permutations(sel))
    if typ == "ワイド":
        a, b = sel
        return sum(sum(order_prob(p, o) for o in permutations((a, b, c))) for c in p if c not in sel)
    raise ValueError(typ)


def exposures(bets: list, budget: int) -> dict:
    ex = {}
    for b in bets:
        for h in set(b["selection"]):
            ex[h] = ex.get(h, 0) + b["stake_yen"]
    return {h: v / budget for h, v in ex.items()} if budget else {}


def predict(sealed: dict) -> dict:
    bets = [b for b in sealed.get("formal_bets") or [] if isinstance(b, dict)]
    race_id = sealed.get("source_race_id")
    if not bets or not race_id or not sealed.get("source_prediction_path"):
        raise ValueError("sealed purchase set and source STEP1 path are required")
    budget = int(sum(b["stake_yen"] for b in bets))
    base = {"challenger": CHALLENGER_ID, "formal_ticket_count": len(bets),
            "formal_max_exposure": round(max(exposures(bets, budget).values()), 4)}
    if len(bets) < PARAMS["min_tickets"]:
        return {**base, "applicable": False, "changed": False, "challenger_ticket_count": len(bets),
                "challenger_max_exposure": base["formal_max_exposure"], "bets": [], "dropped": []}
    step1 = json.loads((ROOT / sealed["source_prediction_path"]).read_text(encoding="utf-8"))["step1_ranking"]
    odds = load_odds(race_id)
    if not odds:
        raise ValueError("saved pre-race odds tables not found")
    horses = {h for key in odds for h in key[1]}
    raw = {h["horse_number"]: h["win_probability"] for h in step1 if h["horse_number"] in horses}
    total = sum(raw.values())
    p = {h: v / total for h, v in raw.items()}
    cands = []
    for (typ, sel), o in odds.items():
        if typ not in PARAMS["types"] or not set(sel) <= set(p):
            continue
        ev = combo_prob(p, typ, sel) * o - 1.0
        if ev > 0:
            cands.append((-ev, PARAMS["types"].index(typ), sel, typ, o))
    cands.sort()
    unit, cap_yen = PARAMS["unit_yen"], PARAMS["cap"] * budget
    kept, used = [], {}
    for _, _, sel, typ, o in cands:
        if sum(b["stake_yen"] for b in kept) + unit > budget:
            break
        if any(used.get(h, 0) + unit > cap_yen for h in set(sel)):
            continue
        kept.append({"type": typ, "selection": list(sel), "stake_yen": unit, "market_odds": o})
        for h in set(sel):
            used[h] = used.get(h, 0) + unit
    ex = exposures(kept, budget)
    return {**base, "applicable": True, "changed": bool(kept), "challenger_ticket_count": len(kept),
            "challenger_max_exposure": round(max(ex.values()), 4) if ex else None,
            "challenger_stake_yen": sum(b["stake_yen"] for b in kept), "formal_stake_yen": budget,
            "bets": kept, "dropped": []}
