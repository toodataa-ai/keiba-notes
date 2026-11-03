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


def build(pred_dir: Path, results_dir: Path, now: datetime | None = None) -> dict:
    scored = {e["race_id"]: e for e in sc.run(pred_dir, results_dir)["races"]}
    items, seen = [], set()
    for f in sorted(pred_dir.glob("*/*.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        if p["race_id"] in seen:  # 最初に保存した版だけが正
            continue
        seen.add(p["race_id"])
        rf = results_dir / f"{p['race_id']}.json"
        res = json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else None
        marks = sorted([{"no": h["no"], "name": h.get("name", ""), "mark": h["mark"], "reason": h.get("reason", "")}
                        for h in p.get("horses", []) if h.get("mark")], key=lambda m: sc.MARKS.index(m["mark"]))
        item = {"race_id": p["race_id"], "race_name": p.get("race_name") or (res or {}).get("race_name", p["race_id"]),
                "venue": p.get("venue") or (res or {}).get("venue", ""), "date": p.get("date") or (res or {}).get("date", ""),
                "prompt_version": p.get("prompt_version"), "generated_at": p.get("generated_at"),
                "marks": marks, "bets": p.get("bets", []), "total_stake_yen": p.get("total_stake_yen"),
                "result": None}
        e = scored.get(p["race_id"])
        if res and e:
            item["result"] = {"finish_top3": res["finish_order"][:3], "prospective": e["prospective"],
                              "honmei_win": e["honmei_win"], "honmei_top3": e["honmei_top3"],
                              "stake_yen": e["stake_yen"], "payout_yen": e["payout_yen"]}
        items.append(item)
    items.sort(key=lambda x: (x["date"], x["race_id"]), reverse=True)
    summary = sc.aggregate([e for e in scored.values()])
    return {"schema_version": 1, "predictor": "claude", "as_of": (now or datetime.now(JST)).isoformat(timespec="seconds"),
            "note": "ChatGPT の成績とは合算しません。対象は ChatGPT と同じレースだけ。買い目は仮想で、実際には購入しません。",
            "summary": summary, "races": items}


def main():
    out = ROOT / "docs/data/predictors/claude_status_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    d = build(ROOT / "claude_track/predictions", ROOT / "e2e_validation/results")
    out.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: races={len(d['races'])} scored={d['summary']['races']}")


if __name__ == "__main__":
    main()
