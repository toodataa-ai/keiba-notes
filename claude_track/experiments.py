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

ROOT = Path(__file__).resolve().parents[1]
PARAMS = {"max_runs": 4, "front_max_ratio": 0.33, "closer_min_ratio": 0.67, "leader_max_ratio": 0.20,
          "high_pace_min_leaders": 4, "high_pace_min_leader_share": 0.30, "slow_pace_max_leaders": 1,
          "multipliers": {"S": {"front": 1.25, "mid": 1.00, "closer": 0.80},
                          "M": {"front": 1.10, "mid": 1.00, "closer": 0.92},
                          "H": {"front": 0.85, "mid": 1.00, "closer": 1.15}}}
NEED_PAIRS = 20
NEED_HORSES = 30


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


def run(pred_dir: Path, results_dir: Path, root: Path = ROOT) -> dict:
    pairs, exp = [], {k: {"horses": 0, "pred_wins": 0.0, "actual_wins": 0, "races": set()} for k in ("E0", "E1", "E2")}
    career_seen = 0
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
        card = load_card(step1, root)
        if card:
            ch = _norm(overlay(card["horses"], base))
            pairs.append({"race_id": rid, "base_ll": -math.log(base[winner]), "pace_ll": -math.log(ch[winner])})
            for h in card["horses"]:
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
