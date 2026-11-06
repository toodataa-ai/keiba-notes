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
    ("claude-results-v1.yml", "Claude用の結果取得"),
    ("claude-wakakoma-v1.yml", "若駒の機械採点（全レース）"),
    ("jra-improvement-experiments-v1.yml", "改善案と今の予想の採点"),
    ("jra-improvement-pipeline-v1.yml", "基準に届いたかの確認・通知"),
    ("claude-track-publish-v1.yml", "Claudeの予想の採点・公開"),
]


# 実行の出どころ：G=GitHubの定時（遅れて動いた保険を含む）／H=Haikuの起動役（D1 6:03・D2 18:03）／O=OpusのClaudeタスク（T2・T3）／手=手動・復旧・ファイル更新（push）
# 起動役とClaudeタスクは同じ権限でAPIから起動するため、「決まった時刻の窓＋決まった処理」で見分ける（窓の外の起動は手動）。
D1_SET = {"baba-forecast-archive-v1.yml", "local-racing-shadow-postrace.yml", "local-racing-shadow-prerace-generic.yml"}
T2_SET = {"claude-race-data-v1.yml", "claude-odds-v1.yml", "baba-going-live-v1.yml"}
T3_SET = {"claude-results-v1.yml", "claude-wakakoma-v1.yml", "claude-track-publish-v1.yml", "jra-improvement-experiments-v1.yml", "jra-improvement-pipeline-v1.yml"}


def origin(fn, r):
    if r["event"] == "schedule":
        return "G"
    if r["event"] != "workflow_dispatch":
        return "手"
    t = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=9)))
    m = t.hour * 60 + t.minute
    wd = t.weekday()  # 月=0 … 土=5 日=6
    if fn in D1_SET and 6 * 60 <= m < 6 * 60 + 30:
        return "H"
    if fn == "baba-forecast-archive-v1.yml" and 18 * 60 <= m < 18 * 60 + 30:
        return "H"
    if wd in (5, 6, 0) and fn in T2_SET and 9 * 60 + 10 <= m < 11 * 60 + 30:
        return "O"
    if wd in (5, 6, 0) and fn in T3_SET and 18 * 60 + 17 <= m < 21 * 60:
        return "O"
    return "手"


def gh(path):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:300])
    return json.loads(p.stdout)


def fail_kind(run_id, cache):
    """失敗した実行のうち、公開サイトへの反映確認の段階だけが失敗したものを見分ける（データの保存は成功している）。"""
    if str(run_id) in cache:
        return cache[str(run_id)]
    kind = None
    try:
        jobs = gh(f"repos/{REPO}/actions/runs/{run_id}/jobs?per_page=30").get("jobs", [])
        failed = [st["name"] for j in jobs for st in j.get("steps", []) if st.get("conclusion") == "failure"]
        if failed and all(n.startswith("Verify live published") for n in failed):
            kind = "publish_check"
    except RuntimeError as e:
        print("jobs skip", run_id, e, file=sys.stderr)
        return None
    return kind or ""


def main(out):
    since = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    wfs = {}
    cache = {}
    if os.path.exists(out):
        try:
            for w in json.load(open(out, encoding="utf-8")).get("workflows", {}).values():
                for r in w.get("runs", []):
                    if r.get("conclusion") == "failure" and "fail_kind" in r:
                        cache[str(r["id"])] = r["fail_kind"]
        except (ValueError, OSError):
            pass
    for fn, label in TRACKED:
        try:
            d = gh(f"repos/{REPO}/actions/workflows/{fn}/runs?per_page=60&created=%3E%3D{since}")
        except RuntimeError as e:
            print("skip", fn, e, file=sys.stderr); continue
        runs = []
        for r in d.get("workflow_runs", []):
            runs.append({"id": r["id"], "event": r["event"], "created_at": r["created_at"],
                         "started_at": r.get("run_started_at"), "ended_at": r.get("updated_at") if r["status"] == "completed" else None,
                         "status": r["status"], "conclusion": r.get("conclusion"), "attempt": r.get("run_attempt", 1), "by": origin(fn, r)})
            if r.get("conclusion") == "failure":
                k = fail_kind(r["id"], cache)
                if k is not None:
                    runs[-1]["fail_kind"] = k
        wfs[fn] = {"label": label, "runs": sorted(runs, key=lambda x: x["created_at"], reverse=True)}
    doc = {"schema_version": 2, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "keep_days": KEEP_DAYS, "note": "GitHub Actionsの実行記録（開始・終了時刻は実際の値、UTC）。ClaudeのT2/T3・ChatGPTの手動実行は含まない。by＝G:GitHub定時／H:Haiku起動役／O:Opusタスク／手:手動・復旧・push。",
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
