"""Claude の定時タスク（T2 予想・T3 回顧）が終わりに自分で残す実行記録。GitHub Actions の記録（automation_runs_v1.json）には
Claude のセッションは載らないため、別ファイル docs/data/automation/claude_task_runs_v1.json に追記する（直近14日分だけ残す）。
使い方: python3 -m claude_track.record_run --task T2 --status ok --note "3レース保存" --started-at <ISO>"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/data/automation/claude_task_runs_v1.json"
JST = timezone(timedelta(hours=9))
TASKS = {"T2": "Claude：印と買い目の保存", "T3": "Claude：回顧と週次比較"}


def add(doc: dict, task: str, status: str, note: str, started_at: str | None, now: datetime) -> dict:
    assert task in TASKS and status in ("ok", "fail", "skipped")
    runs = doc.get("runs", [])
    runs.append({"task": task, "date": now.strftime("%Y-%m-%d"), "started_at": started_at or now.isoformat(timespec="seconds"),
                 "ended_at": now.isoformat(timespec="seconds"), "status": status, "note": note[:200]})
    cutoff = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    return {"schema_version": 1, "tasks": TASKS, "runs": [r for r in runs if r["date"] >= cutoff]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=list(TASKS))
    ap.add_argument("--status", required=True, choices=["ok", "fail", "skipped"])
    ap.add_argument("--note", default="")
    ap.add_argument("--started-at")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = json.loads(a.out.read_text(encoding="utf-8")) if a.out.exists() else {}
    doc = add(doc, a.task, a.status, a.note, a.started_at, datetime.now(JST))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("recorded", a.task, a.status)


if __name__ == "__main__":
    main()
