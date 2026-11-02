#!/usr/bin/env python3
"""Run pre-registered JRA challengers against the current formal model.

Pairs are formed on the SAME race from the SAME sealed formal prestart
prediction. A challenger here is a deterministic, SHA-pinned function of that
sealed prediction, so it can be recomputed at any time without information
leakage. A pair is PROSPECTIVE only when the race started after the
experiment was registered in Git (the code was fixed before the race);
earlier races are reported as replay_support_only and never count toward
the promotion threshold.

Never modifies formal predictions, final_bets, results or the prompt.
Never promotes automatically: the output is evidence for A/B/C manual review.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "e2e_validation/improvement_experiments_v1.json"
OUT_DIR = "e2e_validation/experiments"
STATUS = "docs/data/jra_experiment_status_v1.json"
EPS = 1e-6


def read(path):
    with (ROOT / path).open(encoding="utf-8") as f:
        return json.load(f)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def registration_commit_time(exp_id: str):
    """First commit that added this experiment id to the registry (conservative in shallow clones)."""
    try:
        out = subprocess.run(
            ["git", "log", "--format=%cI", "--reverse", "-S", f'"id": "{exp_id}"', "--", REGISTRY],
            cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out[0] if out else None


def formal_prediction(entry: dict):
    """Resolve the sealed v3.13 STEP1 prediction behind a strict E2E entry."""
    path = ROOT / entry["prediction_path"]
    pred = json.loads(path.read_text(encoding="utf-8"))
    src = pred.get("source_prediction_path")
    if src:
        raw = (ROOT / src).read_bytes()
        want = pred.get("source_prediction_sha256")
        if want and hashlib.sha256(raw).hexdigest() != want:
            raise ValueError(f"source prediction sha256 mismatch: {src}")
        return json.loads(raw), src
    return pred, entry["prediction_path"]


def same_record(a, b, tol=1e-9) -> bool:
    """Equality that ignores last-bit float noise across Python versions."""
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= tol
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same_record(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same_record(x, y, tol) for x, y in zip(a, b))
    return a == b


def top3_probs(win: dict) -> dict:
    """Exact P(horse finishes top 3) under Plackett-Luce from win probabilities."""
    keys = list(win)
    out = {k: win[k] for k in keys}
    for a in keys:
        ra = 1 - win[a]
        if ra <= 0:
            continue
        for b in keys:
            if b == a:
                continue
            pab = win[a] * win[b] / ra
            out[b] += pab
            rb = ra - win[b]
            if rb <= 0:
                continue
            for c in keys:
                if c not in (a, b):
                    out[c] += pab * win[c] / rb
    return out


def score(win: dict, honmei: int, finish: list) -> dict:
    ran = [h for h in finish if h in win]
    total = sum(win[h] for h in ran)
    p = {h: win[h] / total for h in ran}  # scratched runners removed, renormalised
    winner, top3 = finish[0], set(finish[:3])
    t3 = top3_probs(p)
    return {
        "honmei": honmei,
        "honmei_win": int(honmei == winner),
        "honmei_top3": int(honmei in top3),
        "winner_probability": round(p.get(winner, 0.0), 6),
        "win_brier": round(sum((p[h] - (h == winner)) ** 2 for h in ran), 6),
        "win_log_loss": round(-math.log(max(p.get(winner, 0.0), EPS)), 6),
        "top3_brier": round(sum((min(1.0, t3[h]) - (h in top3)) ** 2 for h in ran) / len(ran), 6),
    }


METRICS = ["honmei_win", "honmei_top3", "win_brier", "win_log_loss", "top3_brier"]


def breakdown(rows: list) -> dict:
    """Side-effect check: the same metrics split by venue, surface and prestart going."""
    out = {}
    for dim in ("venue", "surface", "going"):
        groups = {}
        for r in rows:
            groups.setdefault((r.get("segments") or {}).get(dim, "不明"), []).append(r)
        out[dim] = {k: summarize(v) for k, v in sorted(groups.items())}
    return out


def summarize(rows: list) -> dict:
    if not rows:
        return {"pairs": 0}
    out = {"pairs": len(rows)}
    for m in METRICS:
        b = sum(r["formal"][m] for r in rows) / len(rows)
        c = sum(r["challenger"][m] for r in rows) / len(rows)
        out[m] = {"formal": round(b, 4), "challenger": round(c, 4), "delta": round(c - b, 4)}
    out["challenger_better_log_loss_races"] = sum(
        r["challenger"]["win_log_loss"] < r["formal"]["win_log_loss"] for r in rows)
    return out


def run(write: bool = True) -> dict:
    registry = read(REGISTRY)
    e2e = read("docs/data/e2e_status.json")
    minimum = int((registry.get("policy") or {}).get("minimum_prospective_paired_cases", 20))
    report = {"schema_version": 1, "generated_by": "e2e_validation/experiment_runner_v1.py",
              "automatic_promotion": False, "approval": "A/B/C manual only",
              "lower_is_better": ["win_brier", "win_log_loss", "top3_brier"],
              "experiments": [], "errors": []}
    entries = [x for x in e2e.get("entries", [])
               if x.get("grade") == "prospective_strict"
               and (x.get("proof") or {}).get("read_from_proof_commit") is True]
    for exp in registry.get("experiments", []):
        if exp.get("status") not in ("collecting", "comparing", "reviewing"):
            continue
        code = ROOT / exp["code"]["path"]
        actual = git_blob_sha(code)
        if actual != exp["code"]["git_blob_sha"]:
            report["errors"].append(f"{exp['id']}: challenger code changed after registration "
                                    f"({actual} != {exp['code']['git_blob_sha']}); register a new experiment")
            continue
        module = importlib.import_module(exp["code"]["module"])
        reg_commit = registration_commit_time(exp["id"])
        effective = max(ts(exp["prospective_from"]), ts(reg_commit)) if reg_commit else ts(exp["prospective_from"])
        rows, skipped = [], []
        for entry in sorted(entries, key=lambda x: x["race_id"]):
            rid = entry["race_id"]
            try:
                formal, formal_path = formal_prediction(entry)
            except (OSError, ValueError) as err:
                skipped.append({"race_id": rid, "reason": str(err)})
                continue
            if formal.get("prompt_version") != exp["baseline"]:
                skipped.append({"race_id": rid, "reason": f"baseline is {formal.get('prompt_version')}"})
                continue
            try:
                ch = module.predict(formal)
            except ValueError as err:
                skipped.append({"race_id": rid, "reason": str(err)})
                continue
            start = formal.get("race_context", {}).get("start_at")
            grade = ("prospective_preregistered" if start and ts(start) > effective
                     else "replay_support_only")
            record = {"schema_version": 1, "experiment_id": exp["id"], "race_id": rid,
                      "grade": grade, "scheduled_start_at": start,
                      "formal_prediction_path": formal_path,
                      "formal_proof_commit": entry["proof"]["proof_commit"],
                      "challenger_code_git_blob_sha": actual, **ch}
            dest = ROOT / OUT_DIR / exp["id"] / "predictions" / f"{rid}.json"
            if dest.exists():
                old = json.loads(dest.read_text(encoding="utf-8"))
                if not same_record(old.get("runners"), record["runners"]):
                    report["errors"].append(f"{exp['id']}/{rid}: stored challenger prediction differs; refusing to overwrite")
                    continue
            elif write:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result_path = ROOT / "e2e_validation" / "results" / f"{rid}.json"
            if not result_path.exists():
                skipped.append({"race_id": rid, "reason": "official result not yet recorded"})
                continue
            finish = json.loads(result_path.read_text(encoding="utf-8")).get("finish_order") or []
            if not finish:
                skipped.append({"race_id": rid, "reason": "finish_order missing"})
                continue
            formal_win = {h["horse_number"]: h["win_probability"] for h in formal["step1_ranking"]}
            honmei = next((h["horse_number"] for h in formal["step1_ranking"] if h.get("mark") == "◎"),
                          max(formal_win, key=formal_win.get))
            ch_win = {r["horse_number"]: r["challenger_win_probability"] for r in ch["runners"]}
            ctx = formal.get("race_context") or {}
            going = ctx.get("official_going")
            rows.append({"race_id": rid, "grade": grade,
                         "segments": {
                             "venue": ctx.get("venue") or "不明",
                             "surface": "芝" if str(ctx.get("surface", "")).startswith("芝")
                             else "ダート" if str(ctx.get("surface", "")).startswith("ダ") else "不明",
                             "going": ("良" if going == "良" else "道悪（稍重〜不良）"
                                       if going in ("稍重", "重", "不良") else "不明"),
                         },
                         "challenger_summary": {k: v for k, v in ch.items()
                                                if k not in ("runners", "marks", "challenger")},
                         "formal": score(formal_win, honmei, finish),
                         "challenger": score(ch_win, ch["marks"]["◎"], finish)})
        prospective = [r for r in rows if r["grade"] == "prospective_preregistered"]
        replay = [r for r in rows if r["grade"] == "replay_support_only"]
        report["experiments"].append({
            "id": exp["id"], "title": exp["title"], "plain_summary": exp.get("plain_summary"),
            "hypothesis_ids": exp.get("hypothesis_ids", []),
            "baseline": exp["baseline"], "challenger": exp["challenger"],
            "status": exp["status"], "effective_prospective_from": effective.isoformat(),
            "registration_commit_at": reg_commit,
            "minimum_prospective_pairs": minimum,
            "remaining_prospective_pairs": max(0, minimum - len(prospective)),
            "ready_for_manual_review": len(prospective) >= minimum,
            "prospective": summarize(prospective),
            "prospective_breakdown": breakdown(prospective),
            "replay_support_only": summarize(replay),
            "replay_breakdown": breakdown(replay),
            "replay_caveat": "過去レースの再現。発走前に登録された比較ではないため採用判定の件数に数えない",
            "races": rows, "skipped": skipped,
        })
    if write:
        dest = ROOT / STATUS
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="compute only; do not write files")
    args = p.parse_args()
    import sys
    sys.path.insert(0, str(ROOT))
    report = run(write=not args.check)
    for e in report["experiments"]:
        print("EXPERIMENT", json.dumps({k: e[k] for k in ("id", "remaining_prospective_pairs")}
                                       | {"prospective": e["prospective"].get("pairs"),
                                          "replay": e["replay_support_only"].get("pairs")},
                                       ensure_ascii=False))
    if report["errors"]:
        raise SystemExit("EXPERIMENT_ERRORS: " + "; ".join(report["errors"]))


if __name__ == "__main__":
    main()
