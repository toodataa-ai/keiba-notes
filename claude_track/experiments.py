"""Claude-track experiments (research only; never changes Claude's saved predictions, never buys).

 1. pace_v1 overlay on CLAUDE's own STEP1 win probabilities (same fixed rule as ChatGPT-side EXP-001):
    baseline = Claude's probabilities, challenger = overlay; both scored on the same official winner.
 2. field experience (E0/E1/E2) diagnostics: for horses whose JRA career summary was on the card,
    compare Claude's predicted win probability with actual wins per regime.
Inputs: claude_track/predictions (first STEP1 file per race), the price-blind card JSON named in step1.input_file,
and the shared official results.  Output: docs/data/predictors/claude_experiments_v1.json
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from statistics import mean

from claude_track import score_claude as sc
from e2e_validation import portfolio_eval_v1 as pe
from e2e_validation.challengers import ticket_div_v1 as td   # fixed rule from EXP-003 (unchanged file, reused as-is)

ROOT = Path(__file__).resolve().parents[1]
PARAMS = {"max_runs": 4, "front_max_ratio": 0.33, "closer_min_ratio": 0.67, "leader_max_ratio": 0.20,
          "high_pace_min_leaders": 4, "high_pace_min_leader_share": 0.30, "slow_pace_max_leaders": 1,
          "multipliers": {"S": {"front": 1.25, "mid": 1.00, "closer": 0.80},
                          "M": {"front": 1.10, "mid": 1.00, "closer": 0.92},
                          "H": {"front": 0.85, "mid": 1.00, "closer": 1.15}}}
NEED_PAIRS = 20
NEED_HORSES = 30
NEED_FIRST_DIST = 100   # 初めての距離（2歳戦の距離延長）の馬が、この頭数たまったら判定（過去データでは差が小さいため、偶然と区別できる数を要求）


def first_distance_group(card: dict, h: dict):
    """2歳戦で、前走までの出走歴がすべて分かる馬を『初めての距離・延長』『同じ距離を走ったことがある』『初出走』に分ける。
    出走歴が全部分からない（starts_before_race より past が少ない）馬は判定できないので None。"""
    if not str(card.get("age_condition") or "").startswith("2歳"):
        return None
    n, past, d = h.get("starts_before_race"), h.get("past") or [], card.get("distance_m")
    if n is None or not d or len(past) < n:
        return None
    if n == 0:
        return "debut"
    ds = [p.get("distance_m") for p in past]
    if any(x is None for x in ds):
        return None
    if d in ds:
        return "known"
    return "extension" if d > max(ds) else "shorten"


def early_ratio(run: dict):
    pos, n = run.get("passing_positions") or [], run.get("field_size")
    if not pos or not n or n < 2 or not 1 <= pos[0] <= n:
        return None
    return (pos[0] - 1) / (n - 1)


def style(horse: dict):
    r = [x for x in (early_ratio(p) for p in (horse.get("past") or [])[:PARAMS["max_runs"]]) if x is not None]
    if not r:
        return "unknown", None
    m = mean(r)
    return ("front" if m <= PARAMS["front_max_ratio"] else "closer" if m >= PARAMS["closer_min_ratio"] else "mid"), m


def overlay(card_horses: list[dict], probs: dict[int, float]) -> dict[int, float]:
    info = {h["number"]: style(h) for h in card_horses}
    n = len(probs)
    leaders = sum(1 for _, m in info.values() if m is not None and m <= PARAMS["leader_max_ratio"])
    pace = ("H" if leaders >= max(PARAMS["high_pace_min_leaders"], PARAMS["high_pace_min_leader_share"] * n)
            else "S" if leaders <= PARAMS["slow_pace_max_leaders"] else "M")
    mult = PARAMS["multipliers"][pace]
    raw = {k: v * mult.get(info.get(k, ("unknown", None))[0], 1.0) for k, v in probs.items()}
    s = sum(raw.values())
    return {k: v / s for k, v in raw.items()}


def _norm(probs):
    s = sum(probs.values()); return {k: max(v / s, 1e-6) for k, v in probs.items()}


def regime(starts):
    return None if starts is None else "E0" if starts == 0 else "E1" if starts <= 3 else "E2"


def load_card(step1: dict, root: Path):
    f = step1.get("input_file")
    if not f:
        return None
    p = root / f
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None



# ---- going overlay (same fixed rule as ChatGPT-side EXP-002, applied to Claude's STEP1) ----
GOING = {"wet_goings": ["稍重", "重", "不良"], "k_wet_race": 0.8, "k_dry_race": 0.4, "min_multiplier": 0.80, "max_multiplier": 1.25}


def going_overlay(card: dict, probs: dict[int, float], going: str):
    """Returns (new probs, adjusted_runner_count) or None when going/surface are unknown."""
    surface = {"ダート": "ダート", "芝": "芝"}.get(card.get("surface"))
    if going not in ("良", *GOING["wet_goings"]) or not surface:
        return None
    race_wet = going in GOING["wet_goings"]
    k = GOING["k_wet_race"] if race_wet else GOING["k_dry_race"]
    by_no = {h["number"]: h for h in card["horses"]}
    raw, adj = {}, 0
    for no, p in probs.items():
        runs = [r for r in (by_no.get(no, {}).get("past") or [])
                if r.get("surface") == surface and r.get("going") and r.get("finish") and (r.get("field_size") or 0) >= 2
                and 1 <= r["finish"] <= r["field_size"]]
        score = lambda r: 1 - (r["finish"] - 1) / (r["field_size"] - 1)
        wet = [score(r) for r in runs if r["going"] in GOING["wet_goings"]]
        dry = [score(r) for r in runs if r["going"] not in GOING["wet_goings"]]
        mult = 1.0
        if wet and dry:
            same, other = (wet, dry) if race_wet else (dry, wet)
            diff = mean(same) - mean(other)
            mult = min(GOING["max_multiplier"], max(GOING["min_multiplier"], math.exp(k * diff))); adj += 1
        raw[no] = p * mult
    t = sum(raw.values())
    return {k_: v / t for k_, v in raw.items()}, adj


# ---- purchase set: Claude's own STEP2 vs the mechanical rule (EXP-003 rule) on the SAME STEP1 probabilities and odds ----
def mechanical_set(probs: dict[int, float], odds: dict, budget: int) -> list[dict]:
    horses = {h for key in odds for h in key[1]}
    raw = {h: v for h, v in probs.items() if h in horses}
    t = sum(raw.values()); p = {h: v / t for h, v in raw.items()}
    cands = []
    for (typ, sel), o in odds.items():
        if typ not in td.PARAMS["types"] or not set(sel) <= set(p):
            continue
        ev = td.combo_prob(p, typ, sel) * o - 1.0
        if ev > 0:
            cands.append((-ev, td.PARAMS["types"].index(typ), sel, typ, o))
    cands.sort()
    unit, cap_yen = td.PARAMS["unit_yen"], td.PARAMS["cap"] * budget
    kept, used = [], {}
    for _, _, sel, typ, o in cands:
        if sum(b["stake_yen"] for b in kept) + unit > budget:
            break
        if any(used.get(h, 0) + unit > cap_yen for h in set(sel)):
            continue
        kept.append({"type": typ, "selection": list(sel), "stake_yen": unit, "market_odds": o})
        for h in set(sel):
            used[h] = used.get(h, 0) + unit
    return kept


def odds_table(path: Path) -> dict:
    out = {}
    for e in json.loads(path.read_text(encoding="utf-8")).get("entries", []):
        typ = e.get("type")
        if typ not in td.PARAMS["types"]:
            continue
        o = e["market_odds"]; o = min(o) if isinstance(o, list) else o
        if isinstance(o, (int, float)) and o > 0:
            out[(typ, tuple(e["selection"]) if typ == "馬単" else tuple(sorted(e["selection"])))] = float(o)
    return out


def captured_going(race_id: str, root: Path):
    d = root / "claude_track/odds" / race_id
    for f in sorted(d.glob("*.json"), reverse=True) if d.exists() else []:
        g = json.loads(f.read_text(encoding="utf-8")).get("going")
        if g:
            return g
    return None


def _port_summary(rows):
    if not rows:
        return None
    def side(k):
        st = sum(r[k]["stake_yen"] for r in rows); py = sum(r[k]["payout_yen"] for r in rows)
        return {"stake_yen": st, "payout_yen": py, "roi": round(py / st, 4) if st else None, "hit_races": sum(r[k]["hit"] for r in rows)}
    return {"claude_own": side("claude"), "mechanical_rule": side("mechanical")}


def run(pred_dir: Path, results_dir: Path, root: Path = ROOT) -> dict:
    pairs, going_pairs, port_rows = [], [], []
    exp = {k: {"horses": 0, "pred_wins": 0.0, "actual_wins": 0, "races": set()} for k in ("E0", "E1", "E2")}
    career_seen = 0
    fd = {k: {"horses": 0, "pred": 0.0, "var": 0.0, "wins": 0, "races": set()} for k in ("extension", "shorten", "known", "debut")}
    for rid, slot in sc.load_race_files(pred_dir).items():
        rf = sc.resolve_result(rid, results_dir)
        if rf is None or slot["step1"] is None:
            continue
        step1, result = slot["step1"], json.loads(rf.read_text(encoding="utf-8"))
        if not sc.is_prospective(step1, result):
            continue
        horses = step1.get("horses", [])
        probs = {h["no"]: h["win_prob"] for h in horses if h.get("win_prob") is not None}
        winner = result["finish_order"][0]
        if len(probs) != len(horses) or winner not in probs:
            continue
        base = _norm(probs)
        s2 = slot.get("step2")
        if s2 and s2.get("bets") and s2.get("odds_source") and (root / s2["odds_source"]).exists():
            budget = int(sum(b["stake_yen"] for b in s2["bets"]))
            mech = mechanical_set(base, odds_table(root / s2["odds_source"]), budget)
            if mech and result.get("official_payouts_yen_per_100"):
                pay = result["official_payouts_yen_per_100"]
                port_rows.append({"race_id": rid, "claude": pe.settle(s2["bets"], pay), "mechanical": pe.settle(mech, pay),
                                  "claude_tickets": len(s2["bets"]), "mechanical_tickets": len(mech)})
        card = load_card(step1, root)
        if card:
            gv = captured_going(rid, root)
            go = going_overlay(card, base, gv) if gv else None
            if go:
                gp = _norm(go[0]); going_pairs.append({"race_id": rid, "base_ll": -math.log(base[winner]), "going_ll": -math.log(gp[winner]), "adjusted": go[1], "going": gv})
            ch = _norm(overlay(card["horses"], base))
            pairs.append({"race_id": rid, "base_ll": -math.log(base[winner]), "pace_ll": -math.log(ch[winner])})
            for h in card["horses"]:
                fg = first_distance_group(card, h)
                if fg and h["number"] in base:
                    q = base[h["number"]]; e = fd[fg]
                    e["horses"] += 1; e["pred"] += q; e["var"] += q * (1 - q)
                    e["wins"] += 1 if h["number"] == winner else 0; e["races"].add(rid)
                g = regime(h.get("starts_before_race"))
                if g and h["number"] in base:
                    career_seen += 1
                    e = exp[g]; e["horses"] += 1; e["pred_wins"] += base[h["number"]]
                    e["actual_wins"] += 1 if h["number"] == winner else 0; e["races"].add(rid)
    n = len(pairs)
    deltas = [p["pace_ll"] - p["base_ll"] for p in pairs]
    out = {"schema_version": 1, "predictor": "claude", "research_only": True,
           "pace": {"id": "claude+pace_v1", "pairs": n, "need_pairs": NEED_PAIRS,
                    "mean_log_loss_base": mean(p["base_ll"] for p in pairs) if n else None,
                    "mean_log_loss_pace": mean(p["pace_ll"] for p in pairs) if n else None,
                    "races_improved": sum(1 for d in deltas if d < 0), "races_worse": sum(1 for d in deltas if d > 0),
                    "state": "collecting" if n < NEED_PAIRS else "ready_for_decision"},
           "going": {"id": "claude+going_v1", "pairs": len(going_pairs), "need_pairs": NEED_PAIRS,
                     "adjusted_runners": sum(p["adjusted"] for p in going_pairs),
                     "mean_log_loss_base": mean(p["base_ll"] for p in going_pairs) if going_pairs else None,
                     "mean_log_loss_going": mean(p["going_ll"] for p in going_pairs) if going_pairs else None,
                     "races_improved": sum(1 for p in going_pairs if p["going_ll"] < p["base_ll"]),
                     "races_worse": sum(1 for p in going_pairs if p["going_ll"] > p["base_ll"]),
                     "state": "collecting" if len(going_pairs) < NEED_PAIRS else "ready_for_decision"},
           "portfolio": {"id": "claude+ticket_div_rule", "pairs": len(port_rows), "need_pairs": NEED_PAIRS,
                         "summary": _port_summary(port_rows),
                         "state": "collecting" if len(port_rows) < NEED_PAIRS else "ready_for_decision"},
           "first_distance": {"need_horses": NEED_FIRST_DIST, "target": "extension",
                              "state": "collecting" if fd["extension"]["horses"] < NEED_FIRST_DIST else "ready_for_review",
                              "groups": {k: {"horses": v["horses"], "races": len(v["races"]), "predicted_wins": round(v["pred"], 3), "actual_wins": v["wins"],
                                             "ratio": (round(v["wins"] / v["pred"], 3) if v["pred"] > 0 else None),
                                             "ratio_95": ([round(max(0.0, (v["wins"] - 1.96 * math.sqrt(v["var"])) / v["pred"]), 3), round((v["wins"] + 1.96 * math.sqrt(v["var"])) / v["pred"], 3)] if v["pred"] > 0 and v["var"] > 0 else None)}
                                         for k, v in fd.items()}},
           "experience": {"career_data_available": career_seen > 0, "need_horses": NEED_HORSES,
                          "regimes": {k: {"horses": v["horses"], "races": len(v["races"]),
                                          "predicted_wins": round(v["pred_wins"], 3), "actual_wins": v["actual_wins"],
                                          "state": "collecting" if v["horses"] < NEED_HORSES else "ready_for_review"}
                                      for k, v in exp.items()}}}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", type=Path, default=ROOT / "claude_track/predictions")
    ap.add_argument("--results", type=Path, default=ROOT / "e2e_validation/results")
    ap.add_argument("--out", type=Path, default=ROOT / "docs/data/predictors/claude_experiments_v1.json")
    a = ap.parse_args(argv)
    res = run(a.predictions, a.results)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("claude experiments: pace pairs", res["pace"]["pairs"], "career data", res["experience"]["career_data_available"])


if __name__ == "__main__":
    main()
