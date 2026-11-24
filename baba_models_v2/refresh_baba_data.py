"""馬場の学習データを最新にする（週1回の自動更新用。方法は変えず、足りない最近分だけ取り直して結合し、学習用の表を作り直す）。

流れ：①気象庁の時間別データ（直近 SINCE_DAYS 日ぶんを取り直して結合）②JRA公式の含水率・クッション値・使用コース（今年ぶんを取り直して結合）
③芝のA〜D（今年ぶんを取り直して結合）④stage_b_dataset 作り直し （競馬場ごとの判定の再計算は、全競馬場共通の方式にしたため行わない）
全部できたときだけ置き換える（途中で失敗したら、作業中の変更を元に戻して失敗を記録）。記録：docs/data/derived_refresh_v1.json の baba_data。
使い方：cd baba_models_v2 && python3 refresh_baba_data.py [--today YYYY-MM-DD] [--skip-fetch]"""
from __future__ import annotations
import argparse, csv, json, subprocess, sys, tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOG = ROOT / "docs/data/derived_refresh_v1.json"
JST = timezone(timedelta(hours=9))
SINCE_DAYS = 45
MIN_ROWS = 30537            # 2026-11-03 時点の行数（これより減ったら失敗）
NO_MOISTURE_HOLD_DAYS = 45   # 直近この日数のうち、朝の含水率がまだ無いレースは表に入れない
TRACKS = ["sapporo", "hakodate", "fukushima", "niigata", "tokyo", "nakayama", "chukyo", "kyoto", "hanshin", "kokura"]


def read_csv(p: Path):
    with p.open(encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        head = next(r)
        return head, [row for row in r]


def write_csv(p: Path, head, rows):
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows)


def merge_by_date(old: Path, new: Path, date_col: str, since: str, sort_key):
    """既存CSVのうち date_col が since より前の行を残し、新しく取った分（since 以降）を足す。"""
    nh, nr = read_csv(new)
    if old.exists():
        oh, orows = read_csv(old)
        if oh != nh:
            raise RuntimeError(f"列が違う: {old.name}")
        i = oh.index(date_col)
        keep = [r for r in orows if r[i] < since]
    else:
        keep = []
    rows = keep + [r for r in nr if r[nh.index(date_col)] >= since]
    rows.sort(key=lambda r: sort_key(nh, r))
    write_csv(old, nh, rows)
    return len(keep), len(rows)


def merge_by_year(old: Path, new: Path, year_col: str, years: set, sort_key):
    """既存CSVのうち year_col が years に入らない行を残し、新しく取った分を足す。新しく取れた行が0なら失敗（取れていないのに消さない）。"""
    nh, nr = read_csv(new)
    if not nr:
        raise RuntimeError(f"新しく取れた行が0: {old.name}")
    if old.exists():
        oh, orows = read_csv(old)
        if oh != nh:
            raise RuntimeError(f"列が違う: {old.name}")
        i = oh.index(year_col)
        keep = [r for r in orows if r[i] not in years]
    else:
        keep = []
    rows = keep + nr
    rows.sort(key=lambda r: sort_key(nh, r))
    write_csv(old, nh, rows)
    return len(keep), len(rows)


def run(cmd, cwd=HERE):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])}: {(r.stderr or r.stdout)[-300:]}")
    return r.stdout


def fetch_and_merge(today: date, tmp: Path):
    since = (today - timedelta(days=SINCE_DAYS)).isoformat()
    years = {str(today.year)} | ({str(today.year - 1)} if today.month == 1 else set())
    info = {"weather_since": since, "years": sorted(years)}
    # ① 気象庁
    for t in TRACKS:
        out = tmp / f"w_{t}.csv"
        run([sys.executable, "jma_weather_racedays.py", "--track", t, "--labels-dir", "going_labels", "--since", since, "--out", str(out)])
        sj = json.loads(Path(str(out) + ".summary.json").read_text(encoding="utf-8"))
        if sj["failed"]:
            raise RuntimeError(f"気象庁の取得に失敗 {t}: {len(sj['failed'])}件")
        merge_by_date(HERE / f"weather/jma_hourly_{t}.csv", out, "observed_date", since,
                      lambda h, r: (r[h.index("station")], r[h.index("observed_date")], int(r[h.index("hour")] or 0)))
    # ② 含水率・クッション値・使用コース
    for t in TRACKS:
        out = tmp / f"o_{t}.csv"
        run([sys.executable, "jra_observations.py", "--track", t, "--from-year", min(years), "--to-year", max(years), "--output", str(out)])
        merge_by_year(HERE / f"observations/{t}_observations.csv", out, "year", years, lambda h, r: (r[h.index("observed_date")], r[h.index("meeting")]))
    # ③ 芝のA〜D
    out = tmp / "course.csv"
    run([sys.executable, "jra_course_overview.py", "--labels-dir", "going_labels", "--out", str(out), "--years", ",".join(sorted(years))])
    merge_by_year(HERE / "going_labels/turf_course_by_day.csv", out, "year", years, lambda h, r: (r[h.index("year")], r[h.index("track")], int(r[h.index("kai")] or 0), int(r[h.index("nichime")] or 0)))
    return info


def rebuild(today: date, check_recent: bool = True):
    before = None
    p = HERE / "stage_b/stage_b_dataset.csv.gz"
    import pandas as pd
    if p.exists():
        d0 = pd.read_csv(p); before = (len(d0), str(d0["date"].max()))
    run([sys.executable, "stage_b_dataset.py", "--out", "stage_b/stage_b_dataset.csv.gz"])
    d1 = pd.read_csv(p)
    # JRAの含水率のPDFは開催が終わってからしか出ない。最近のレースで朝の含水率が無い行は、まだ材料がそろっていないので学習・判定の表から外す
    # （そのまま入れると「含水率が欠けたレース」で外れが増え、馬場予測の判定が見かけ上悪くなる）。出そろった次の週に自動で入る。
    cut = (today - timedelta(days=NO_MOISTURE_HOLD_DAYS)).isoformat()
    hold = (d1["date"] >= cut) & d1["moist0"].isna()
    held = int(hold.sum())
    if held:
        d1 = d1[~hold].reset_index(drop=True)
        d1.to_csv(p, index=False)
    if len(d1) < MIN_ROWS or str(d1["date"].max()) < "2026-10-31":     # 取り込みの失敗で表が縮んだり古くなったりしていないか
        raise RuntimeError(f"作り直した表が小さい／古い: {len(d1)}行, {d1['date'].max()}")
    note = {"held_back_no_moisture": held}
    recent = d1[d1["date"] >= (today - timedelta(days=60)).isoformat()]
    if len(recent):
        note["recent_rows"] = int(len(recent))
        note["recent_weather_missing"] = round(float(recent["t_start"].isna().mean()), 3)
        note["recent_moisture_missing"] = round(float(recent["moist0"].isna().mean()), 3)
        if check_recent and note["recent_weather_missing"] > 0.2:
            raise RuntimeError(f"直近60日のレースで気象データが欠けている（{note['recent_weather_missing']:.0%}）。取り直しが足りない")
    # 競馬場ごとの「使える見込み／予報待ち」の判定は、馬場予測を全10競馬場共通の方式にした（2026-11-15）ため、使うかどうかを決めるものではなくなった。
    # 作り直さない（stage_b_status.py などは手動で実行できるまま残す）。
    return {"rows": len(d1), "through": str(d1["date"].max())[:10], "rows_before": before[0] if before else None, **note}


def record(entry):
    d = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"version": 1, "jobs": []}
    jobs = [j for j in d.get("jobs", []) if j.get("id") != "baba_data"]
    old = next((j for j in d.get("jobs", []) if j.get("id") == "baba_data"), {})
    if entry["status"] != "ok":
        entry["last_ok_at"] = old.get("at") if old.get("status") == "ok" else old.get("last_ok_at")
        entry["last_ok_data_through"] = old.get("data_through") if old.get("status") == "ok" else old.get("last_ok_data_through")
    jobs.append(entry)
    d["jobs"] = jobs
    d.setdefault("generated_at", entry["at"])
    LOG.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default="")
    ap.add_argument("--skip-fetch", action="store_true", help="取り直しをせず、いまの保存データから表と判定だけ作り直す")
    a = ap.parse_args()
    today = date.fromisoformat(a.today) if a.today else datetime.now(JST).date()
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    label = "馬場の学習データ（気象・含水率・コース）"
    try:
        info = {}
        with tempfile.TemporaryDirectory() as td:
            if not a.skip_fetch:
                info = fetch_and_merge(today, Path(td))
            res = rebuild(today, check_recent=not a.skip_fetch)
        entry = {"id": "baba_data", "label": label, "status": "ok", "at": now, "data_through": res["through"],
                 "note": f"表 {res['rows_before']}→{res['rows']}行（含水率がまだ無い直近{res.get('held_back_no_moisture')}レースは次回に回す）、直近60日{res.get('recent_rows', 0)}レースの欠け（気象 {res.get('recent_weather_missing')}・含水率 {res.get('recent_moisture_missing')}）", "outputs": ["baba_models_v2/stage_b/stage_b_dataset.csv.gz"]}
        record(entry)
        print("OK", entry["note"])
        return 0
    except Exception as e:
        subprocess.run(["git", "checkout", "--", "baba_models_v2"], cwd=ROOT)       # 途中で失敗したら、作業中の変更を元に戻す
        subprocess.run(["git", "clean", "-fdq", "baba_models_v2/weather", "baba_models_v2/observations"], cwd=ROOT)
        record({"id": "baba_data", "label": label, "status": "failed", "at": now, "error": str(e)[:300]})
        print("FAIL", str(e)[:400], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
