"""claude_track の予想と採点から、サイト表示用の公開JSONを作る。
出力: docs/data/predictors/claude_status_v1.json（ChatGPT 側のデータには一切触れない）
発走前の予想（印・買い目）は公開してよい。結果と採点は results があるレースだけ載せる。
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from claude_track import score_claude as sc

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))


def load_review(race_id: str) -> dict | None:
    """Claude 自身の回顧（claude_track/reviews/<race_id>.json）から、表示に使う項目だけ取り出す。"""
    f = ROOT / "claude_track/reviews" / f"{race_id}.json"
    if not f.is_file():
        return None
    try:
        r = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {"summary": r.get("summary", ""), "honmei_result": r.get("honmei_result", ""),
            "failure_types": r.get("failure_types", []), "lessons": r.get("lessons", []),
            "repeatable": r.get("repeatable"), "reviewed_at": r.get("reviewed_at")}


def build(pred_dir: Path, results_dir: Path, now: datetime | None = None) -> dict:
    scored = {e["race_id"]: e for e in sc.run(pred_dir, results_dir)["races"]}
    items = []
    for rid, slot in sc.load_race_files(pred_dir).items():
        p = dict(slot["step1"] or {})
        if not p:
            continue
        s2 = slot["step2"] or {}
        p["bets"] = s2.get("bets", []); p["total_stake_yen"] = s2.get("total_stake_yen", sum(b["stake_yen"] for b in p["bets"]))
        rf = sc.resolve_result(rid, results_dir)
        res = json.loads(rf.read_text(encoding="utf-8")) if rf else None
        marks = sorted([{"no": h["no"], "name": h.get("name", ""), "mark": h["mark"], "reason": h.get("reason", "")}
                        for h in p.get("horses", []) if h.get("mark")], key=lambda m: sc.MARKS.index(m["mark"]))
        item = {"race_id": p["race_id"], "race_name": p.get("race_name") or (res or {}).get("race_name", p["race_id"]),
                "venue": p.get("venue") or (res or {}).get("venue", ""), "date": p.get("date") or (res or {}).get("date", ""),
                "prompt_version": p.get("prompt_version"), "generated_at": p.get("generated_at"),
                "marks": marks, "bets": p.get("bets", []), "total_stake_yen": p.get("total_stake_yen"),
                "result": None, "review": load_review(rid)}
        e = scored.get(p["race_id"])
        if res and e:
            item["result"] = {"finish_top3": res["finish_order"][:3], "prospective": e["prospective"],
                              "honmei_win": e["honmei_win"], "honmei_top3": e["honmei_top3"],
                              "stake_yen": e["stake_yen"], "payout_yen": e["payout_yen"]}
        items.append(item)
    items.sort(key=lambda x: (x["date"], x["race_id"]), reverse=True)
    summary = sc.aggregate([e for e in scored.values()])
    return {"schema_version": 1, "predictor": "claude", "as_of": max([i["generated_at"] for i in items if i.get("generated_at")], default=None),
            "note": "ChatGPT の成績とは合算しません。対象は、JRAの毎開催日のメインレース（11R）です。買い目は仮想で、実際には購入しません。",
            "summary": summary, "races": items}


def main():
    out = ROOT / "docs/data/predictors/claude_status_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    d = build(ROOT / "claude_track/predictions", ROOT / "e2e_validation/results")
    out.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: races={len(d['races'])} scored={d['summary']['races']}")


if __name__ == "__main__":
    main()
