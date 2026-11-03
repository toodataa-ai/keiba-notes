#!/usr/bin/env python3
"""Pair evaluation for purchase-set (portfolio) experiments (kind == "portfolio").

Both the formal set and the challenger set are settled here with the SAME official
payouts (results/<race>.json: official_payouts_yen_per_100), so the comparison does
not depend on stored settlement text. Research only; never changes formal bets.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

ORDERED = {"馬単", "三連単"}


def bet_key(btype: str, selection: list) -> str:
    sel = list(selection) if btype in ORDERED else sorted(selection)
    return "-".join(str(x) for x in sel)


def settle(bets: list, payouts: dict) -> dict:
    stake = payout = 0
    for b in bets:
        stake += int(b["stake_yen"])
        per100 = (payouts.get(b["type"]) or {}).get(bet_key(b["type"], b["selection"]))
        if per100:
            payout += int(per100 * int(b["stake_yen"]) / 100)
    return {"stake_yen": stake, "payout_yen": payout, "net_yen": payout - stake, "hit": int(payout > 0)}


def sealed_purchase(root: Path, race_id: str):
    files = sorted(glob.glob(str(root / "e2e_validation" / "predictions" / race_id / "v3.1[56]*-sealed.json")))
    return (json.loads(Path(files[-1]).read_text(encoding="utf-8")), files[-1]) if files else (None, None)


def summarize(rows: list) -> dict:
    if not rows:
        return {"pairs": 0}

    def agg(side):
        s = sum(r[side]["stake_yen"] for r in rows)
        p = sum(r[side]["payout_yen"] for r in rows)
        return {"stake_yen": s, "payout_yen": p, "net_yen": p - s, "roi": round(p / s, 4) if s else None,
                "hit_races": sum(r[side]["hit"] for r in rows),
                "loss_races": sum(1 for r in rows if r[side]["net_yen"] < 0),
                "avg_max_exposure": round(sum(r[side]["max_exposure"] or 0 for r in rows) / len(rows), 4)}

    def roi_of(rs, side):
        s = sum(r[side]["stake_yen"] for r in rs)
        return (sum(r[side]["payout_yen"] for r in rs) / s) if s else None

    f, c = agg("formal"), agg("challenger")
    top = max(rows, key=lambda r: abs(r["challenger"]["net_yen"] - r["formal"]["net_yen"]))
    rest = [r for r in rows if r is not top]
    rf, rc = roi_of(rest, "formal"), roi_of(rest, "challenger")
    return {"pairs": len(rows), "formal": f, "challenger": c,
            "roi_delta": round(c["roi"] - f["roi"], 4) if f["roi"] is not None and c["roi"] is not None else None,
            "roi_delta_without_biggest_gap_race": round(rc - rf, 4) if rf is not None and rc is not None else None,
            "biggest_gap_race": top["race_id"],
            "challenger_better_net_races": sum(1 for r in rows if r["challenger"]["net_yen"] > r["formal"]["net_yen"]),
            "challenger_worse_net_races": sum(1 for r in rows if r["challenger"]["net_yen"] < r["formal"]["net_yen"])}


def evaluate(root: Path, exp: dict, module, entries: list, effective, ts, reg_commit, minimum: int, write: bool, out_dir: str):
    rows, skipped, not_applicable = [], [], []
    for entry in sorted(entries, key=lambda x: x["race_id"]):
        rid = entry["race_id"]
        sealed, path = sealed_purchase(root, rid)
        if not sealed:
            skipped.append({"race_id": rid, "reason": "sealed purchase file not found"})
            continue
        try:
            ch = module.predict(sealed)
        except ValueError as err:
            skipped.append({"race_id": rid, "reason": str(err)})
            continue
        start = (sealed.get("race_context") or {}).get("start_at")
        grade = "prospective_preregistered" if start and ts(start) > effective else "replay_support_only"
        record = {"schema_version": 1, "experiment_id": exp["id"], "race_id": rid, "grade": grade,
                  "scheduled_start_at": start, "sealed_purchase_path": str(Path(path).relative_to(root)), **ch}
        dest = root / out_dir / exp["id"] / "predictions" / f"{rid}.json"
        if dest.exists():
            if json.loads(dest.read_text(encoding="utf-8")).get("bets") != record["bets"]:
                skipped.append({"race_id": rid, "reason": "stored challenger set differs; refusing to overwrite"})
                continue
        elif write:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not ch["applicable"] or not ch["changed"]:
            not_applicable.append(rid)
            continue
        rp = root / "e2e_validation" / "results" / f"{rid}.json"
        if not rp.exists():
            skipped.append({"race_id": rid, "reason": "official result not yet recorded"})
            continue
        payouts = json.loads(rp.read_text(encoding="utf-8")).get("official_payouts_yen_per_100")
        if not payouts:
            skipped.append({"race_id": rid, "reason": "official payouts missing"})
            continue
        f = settle(sealed["formal_bets"], payouts)
        c = settle(ch["bets"], payouts)
        f["max_exposure"], c["max_exposure"] = ch["formal_max_exposure"], ch["challenger_max_exposure"]
        rows.append({"race_id": rid, "grade": grade, "formal": f, "challenger": c})
    pro = [r for r in rows if r["grade"] == "prospective_preregistered"]
    rep = [r for r in rows if r["grade"] == "replay_support_only"]
    return {
        "id": exp["id"], "kind": "portfolio", "title": exp["title"], "plain_summary": exp.get("plain_summary"),
        "hypothesis_ids": exp.get("hypothesis_ids", []), "baseline": exp["baseline"], "challenger": exp["challenger"],
        "status": exp["status"], "effective_prospective_from": effective.isoformat(), "registration_commit_at": reg_commit,
        "minimum_prospective_pairs": minimum, "remaining_prospective_pairs": max(0, minimum - len(pro)),
        "ready_for_manual_review": len(pro) >= minimum,
        "prospective": summarize(pro), "prospective_breakdown": {},
        "replay_support_only": summarize(rep), "replay_breakdown": {},
        "replay_caveat": "過去レースの再現。発走前に登録された比較ではないため採用判定の件数に数えない",
        "not_applicable_races": not_applicable, "races": rows, "skipped": skipped,
    }
