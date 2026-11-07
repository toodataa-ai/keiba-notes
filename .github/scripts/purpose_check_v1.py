#!/usr/bin/env python3
"""自動処理の「目的が達成されたか」を、保存された物の有無で調べる（実行が成功したかではなく、データが実際に保存されたか）。
出力：docs/data/automation/purpose_status_v1.json
  days.<日付>.<目的> = {"done": 保存できた数, "expected": 保存されるはずの数（None＝数は決まっていない）}
expected が 0 のものは「その日は対象なし」。使用量0。馬名・買い目などの中身は読まない（ファイルがあるかだけ）。"""
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
ROOT = os.environ.get("PURPOSE_ROOT", ".")
DAYS = 8
GOING_VENUES = {"福島", "阪神"}  # 馬場の朝の予測を出す競馬場


def p(*a):
    return os.path.join(ROOT, *a)


def race_ids(date):
    """出馬表を保存したメインレース {race_id: 競馬場名}"""
    out = {}
    for d in sorted(glob.glob(p("claude_track", "inputs", f"{date}-??-11"))):
        files = sorted(glob.glob(os.path.join(d, "*.json")))
        if not files:
            continue
        try:
            venue = json.load(open(files[0], encoding="utf-8")).get("venue")
        except (ValueError, OSError):
            venue = None
        out[os.path.basename(d)] = venue
    return out


def all_dirs(date):
    return sorted(os.path.basename(d) for d in glob.glob(p("claude_track", "inputs", f"{date}-??-11")))


def has(pattern):
    return bool(glob.glob(pattern))


def archive_times(date):
    """気象庁の予報・馬場ページの保存（ファイル名＝日本時間）→ [(日付, 時分)]"""
    out = []
    y, m = date[:4], date[5:7]
    for f in glob.glob(p("baba_models_v2", "forecast_archive", y, m, "*.json.gz")):
        b = os.path.basename(f)[:13]
        if len(b) == 13 and b[8] == "_":
            out.append((f"{b[:4]}-{b[4:6]}-{b[6:8]}", int(b[9:13])))
    return out


def day_status(date):
    ids = race_ids(date)
    n = len(ids)
    nd = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
    nxt = nd.strftime("%Y-%m-%d")
    prv = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    st = {}
    pdirs = all_dirs(date)
    # 出馬表：保存できた競馬場の数（出馬表が1つも無い日は対象なし）
    st["race_cards"] = {"done": n, "expected": len(pdirs)}
    st["odds"] = {"done": sum(1 for r in ids if has(p("claude_track", "odds", r, "*.json"))), "expected": n}
    st["results"] = {"done": sum(1 for r in ids if os.path.exists(p("claude_track", "results", r + ".json"))), "expected": n}
    st["predictions"] = {"done": sum(1 for r in ids if has(p("claude_track", "predictions", r, "step1-*.json")) and has(p("claude_track", "predictions", r, "step2-*.json"))), "expected": n}
    st["claude_review"] = {"done": sum(1 for r in ids if os.path.exists(p("claude_track", "reviews", r + ".json"))), "expected": n}
    want = sum(1 for v in ids.values() if v in GOING_VENUES)
    st["going_live"] = {"done": len(glob.glob(p("baba_models_v2", "live", f"{date}_*.json"))), "expected": want}
    at = archive_times(date) + archive_times(nxt if nxt[:7] != date[:7] else date)
    am = [t for d, t in at if d == date and t < 830]
    off = [t for d, t in at if d == date and 830 <= t < 1700]
    pm = [1 for d, t in at if (d == date and t >= 1700) or (d == nxt and t < 500)]
    st["forecast_am"] = {"done": 1 if am else 0, "expected": 1}
    st["going_official"] = {"done": 1 if off else 0, "expected": 1 if n else 0}
    st["forecast_pm"] = {"done": 1 if pm else 0, "expected": 1}
    # 地方：前日の回顧（朝6:30）＝前日に固定した予想のうち、回顧が保存された数／予想の固定（朝7:30）＝その日の予想が保存されたか
    pre_prev = len(glob.glob(p("local_racing_shadow_v1", "predictions", prv, "*.json")))
    rev_prev = len(glob.glob(p("local_racing_shadow_v1", "reviews", prv, "*.json")))
    st["local_post"] = {"done": rev_prev, "expected": pre_prev}
    st["local_pre"] = {"done": len(glob.glob(p("local_racing_shadow_v1", "predictions", date, "*.json"))), "expected": None}
    return st


def build(today=None):
    today = today or datetime.now(JST).date()
    days = {}
    for k in range(DAYS):
        d = (today - timedelta(days=k)).isoformat()
        days[d] = day_status(d)
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": "保存された物（ファイル）の数。done＝保存できた数、expected＝保存されるはずの数（None＝決まっていない、0＝その日は対象なし）。", "days": days}


def main(out="docs/data/automation/purpose_status_v1.json"):
    doc = build()
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    old = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    strip = lambda s: "\n".join(l for l in s.splitlines() if '"generated_at"' not in l)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if strip(old) != strip(text):
        open(out, "w", encoding="utf-8").write(text)
        print("updated", out)
    else:
        print("no change")


if __name__ == "__main__":
    main(*sys.argv[1:2])
