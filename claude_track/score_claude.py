"""Score claude_track predictions against the shared official results. Pure functions + a small CLI."""
from __future__ import annotations
import argparse, json, math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDERED = {"馬単", "三連単"}
MARKS = ["◎", "○", "▲", "△", "×"]


def bet_key(btype: str, selection: list[int]) -> str:
    sel = list(selection) if btype in ORDERED else sorted(selection)
    return "-".join(str(x) for x in sel)


def settle_bet(bet: dict, result: dict) -> dict:
    pay = (result.get("official_payouts_yen_per_100") or {}).get(bet["type"], {})
    per100 = pay.get(bet_key(bet["type"], bet["selection"]))
    stake = int(bet["stake_yen"])
    payout = int(per100 * stake / 100) if per100 else 0
    return {"type": bet["type"], "selection": bet["selection"], "stake_yen": stake, "hit": bool(per100), "payout_yen": payout}


def is_prospective(pred: dict, result: dict) -> bool:
    try:
        gen = datetime.fromisoformat(pred["generated_at"])
        start = datetime.fromisoformat(result["scheduled_start_at"])
        return gen < start and not pred.get("odds_seen_before_step1", False) is True
    except Exception:
        return False


def score_prediction(pred: dict, result: dict) -> dict:
    order = result["finish_order"]
    top3 = order[:3]
    horses = pred.get("horses", [])
    out = {"race_id": pred["race_id"], "prospective": is_prospective(pred, result)}
    marked = {h["no"]: h.get("mark") for h in horses if h.get("mark")}
    honmei = next((n for n, m in marked.items() if m == "◎"), None)
    out["honmei_no"] = honmei
    out["honmei_win"] = honmei == order[0] if honmei else None
    out["honmei_top3"] = honmei in top3 if honmei else None
    out["marked_in_top3"] = sum(1 for n, m in marked.items() if m in ("◎", "○", "▲") and n in top3)
    probs = {h["no"]: h.get("win_prob") for h in horses if h.get("win_prob") is not None}
    if probs and len(probs) == len(horses) and order[0] in probs:
        s = sum(probs.values())
        p = {n: max(v / s, 1e-6) for n, v in probs.items()}
        out["log_loss"] = -math.log(p[order[0]])
        out["brier"] = sum((p[n] - (1.0 if n == order[0] else 0.0)) ** 2 for n in p)
    else:
        out["log_loss"] = out["brier"] = None
    sets = [settle_bet(b, result) for b in pred.get("bets", [])]
    out["bets"] = sets
    out["stake_yen"] = sum(b["stake_yen"] for b in sets)
    out["payout_yen"] = sum(b["payout_yen"] for b in sets)
    return out


def aggregate(entries: list[dict]) -> dict:
    ent = [e for e in entries if e["prospective"]]
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None
    stake = sum(e["stake_yen"] for e in ent); pay = sum(e["payout_yen"] for e in ent)
    by_type: dict[str, dict] = {}
    for e in ent:
        for b in e["bets"]:
            t = by_type.setdefault(b["type"], {"bets": 0, "hits": 0, "stake_yen": 0, "payout_yen": 0})
            t["bets"] += 1; t["hits"] += int(b["hit"]); t["stake_yen"] += b["stake_yen"]; t["payout_yen"] += b["payout_yen"]
    return {"races": len(ent), "excluded_not_prospective": len(entries) - len(ent),
            "honmei_win_rate": mean([None if e["honmei_win"] is None else float(e["honmei_win"]) for e in ent]),
            "honmei_top3_rate": mean([None if e["honmei_top3"] is None else float(e["honmei_top3"]) for e in ent]),
            "avg_marked_in_top3": mean([e["marked_in_top3"] for e in ent]),
            "log_loss": mean([e["log_loss"] for e in ent]), "brier": mean([e["brier"] for e in ent]),
            "stake_yen": stake, "payout_yen": pay, "roi": (pay / stake) if stake else None, "by_bet_type": by_type}


def run(pred_dir: Path, results_dir: Path) -> dict:
    entries = []
    for f in sorted(pred_dir.glob("*/*.json")):
        pred = json.loads(f.read_text(encoding="utf-8"))
        rf = results_dir / f"{pred['race_id']}.json"
        if not rf.exists():
            continue
        e = score_prediction(pred, json.loads(rf.read_text(encoding="utf-8")))
        e["prediction_file"] = str(f.relative_to(pred_dir)); entries.append(e)
    # only the first saved file per race counts (later ones are corrections)
    seen, first = set(), []
    for e in entries:
        if e["race_id"] in seen: continue
        seen.add(e["race_id"]); first.append(e)
    return {"schema_version": 1, "predictor": "claude", "summary": aggregate(first), "races": first}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", type=Path, default=ROOT / "claude_track/predictions")
    ap.add_argument("--results", type=Path, default=ROOT / "e2e_validation/results")
    ap.add_argument("--out", type=Path, default=ROOT / "claude_track/status_v1.json")
    a = ap.parse_args(argv)
    res = run(a.predictions, a.results)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    s = res["summary"]; print(f"claude_track: races={s['races']} excluded={s['excluded_not_prospective']} roi={s['roi']}")


if __name__ == "__main__":
    main()
