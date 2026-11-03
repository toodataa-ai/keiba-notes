"""Score claude_track predictions against the shared official results. Pure functions + a small CLI."""
from __future__ import annotations
import argparse, json, math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDERED = {"馬単", "三連単"}
MARKS = ["◎", "○", "▲", "△", "×"]
VENUE_CODES = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京", "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


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
    bets = pred.get("bets", [])
    if bets and "bets_generated_at" in pred:
        try:
            if not datetime.fromisoformat(pred["bets_generated_at"]) < datetime.fromisoformat(result["scheduled_start_at"]):
                bets = []
        except Exception:
            bets = []
    sets = [settle_bet(b, result) for b in bets]
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


def resolve_result(race_id: str, results_dir: Path):
    """Result file for a Claude race id. Accepts ChatGPT's slug (file exists) or '<date>-<venue_code>-11'."""
    direct = results_dir / f"{race_id}.json"
    if direct.exists():
        return direct
    parts = race_id.split("-")
    if len(parts) == 5 and parts[3] in VENUE_CODES:  # YYYY-MM-DD-VV-11
        date, venue = "-".join(parts[:3]), VENUE_CODES[parts[3]]
        for f in sorted(results_dir.glob(f"{date}-*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            if r.get("date") == date and r.get("venue") == venue:
                return f
    return None


def load_race_files(pred_dir: Path) -> dict:
    """{race_id: {'step1': dict, 'step2': dict|None, 'files': [...]}} using the FIRST saved file of each stage."""
    out: dict = {}
    for f in sorted(pred_dir.glob("*/*.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        stage = p.get("stage") or ("step1" if p.get("horses") else "step2")
        slot = out.setdefault(p["race_id"], {"step1": None, "step2": None, "files": []})
        slot["files"].append(str(f.relative_to(pred_dir)))
        if slot.get(stage) is None:
            slot[stage] = p
        if stage == "step1" and p.get("bets") and slot["step2"] is None:   # legacy combined file
            slot["step2"] = {"bets": p["bets"], "generated_at": p["generated_at"]}
    return out


def run(pred_dir: Path, results_dir: Path) -> dict:
    entries = []
    for rid, slot in load_race_files(pred_dir).items():
        rf = resolve_result(rid, results_dir)
        if rf is None or slot["step1"] is None:
            continue
        pred = dict(slot["step1"])
        pred["bets"] = []
        if slot["step2"]:
            pred["bets"] = slot["step2"].get("bets", [])
            pred["bets_generated_at"] = slot["step2"].get("generated_at")
        e = score_prediction(pred, json.loads(rf.read_text(encoding="utf-8")))
        e["prediction_files"] = slot["files"]; e["result_file"] = rf.name
        entries.append(e)
    return {"schema_version": 1, "predictor": "claude", "summary": aggregate(entries), "races": entries}


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
