#!/usr/bin/env python3
"""Build docs/data/automation/automation_runs_v1.json: actual start/end time and result of each tracked automation.
Reads the GitHub Actions run list (authenticated via GH_TOKEN). Record-only; changes nothing else."""
import json, os, subprocess, sys
from datetime import datetime, timezone, timedelta

REPO = os.environ.get("GITHUB_REPOSITORY", "toodataa-ai/keiba-notes")
KEEP_DAYS = 14
TRACKED = [  # workflow file, label
    ("baba-forecast-archive-v1.yml", "予報・馬場ページの保存"),
    ("local-racing-shadow-postrace.yml", "地方競馬：前日の回顧"),
    ("local-racing-shadow-prerace-generic.yml", "地方競馬：予想の固定"),
    ("claude-race-data-v1.yml", "出馬表の取得"),
    ("baba-going-live-v1.yml", "馬場の朝の予測"),
    ("claude-odds-v1.yml", "Claude用のオッズ取得"),
    ("jra-improvement-experiments-v1.yml", "改善案と今の予想の採点"),
    ("jra-improvement-pipeline-v1.yml", "基準に届いたかの確認・通知"),
    ("claude-track-publish-v1.yml", "Claudeの予想の採点・公開"),
]


def gh(path):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:300])
    return json.loads(p.stdout)


def main(out):
    since = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    wfs = {}
    for fn, label in TRACKED:
        try:
            d = gh(f"repos/{REPO}/actions/workflows/{fn}/runs?per_page=60&created=%3E%3D{since}")
        except RuntimeError as e:
            print("skip", fn, e, file=sys.stderr); continue
        runs = []
        for r in d.get("workflow_runs", []):
            runs.append({"id": r["id"], "event": r["event"], "created_at": r["created_at"],
                         "started_at": r.get("run_started_at"), "ended_at": r.get("updated_at") if r["status"] == "completed" else None,
                         "status": r["status"], "conclusion": r.get("conclusion"), "attempt": r.get("run_attempt", 1)})
        wfs[fn] = {"label": label, "runs": sorted(runs, key=lambda x: x["created_at"], reverse=True)}
    doc = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "keep_days": KEEP_DAYS, "note": "GitHub Actionsの実行記録（開始・終了時刻は実際の値、UTC）。ClaudeのT2/T3・ChatGPTの手動実行は含まない。",
           "workflows": wfs}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    old = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    strip = lambda s: "\n".join(l for l in s.splitlines() if '"generated_at"' not in l)
    if strip(old) != strip(text):
        open(out, "w", encoding="utf-8").write(text)
        print("updated", out)
    else:
        print("no change")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/data/automation/automation_runs_v1.json")
