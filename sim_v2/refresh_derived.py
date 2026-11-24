"""各ページ・予想で使う数字（非公開データから作る集計）を、最新のデータで作り直す。

作り直すもの：調教師の強さ／競馬場の傾向／騎手・調教師の条件別成績／種牡馬の初勝利マップ／STEP1 の係数（調教師・上がり順位）と要素の強さ。
どれも「同じ方法を、最新のデータでやり直す」だけで、方法・判断基準は変えない。
安全のため：①1つが失敗しても他は続ける ②出力は一度ほかの場所に作り、JSONとして読めて中身が妥当なときだけ置き換える
③STEP1の係数は、前回から大きく動いたとき（符号が変わる・5割以上変わる）は置き換えず「要確認」と記録する。
記録：docs/data/derived_refresh_v1.json（いつ・どのデータまで・何が更新されたか／されなかったか）。
使い方：python3 -m sim_v2.refresh_derived --data <非公開 data_v2> [--only trainer_strength,...] [--dry]"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
LOG = ROOT / "docs/data/derived_refresh_v1.json"
COEF_PATH = ROOT / "sim_v2/step1_factor_coef.json"
MAX_COEF_CHANGE = 0.5   # 前回からこれ以上（割合）動いたら自動では置き換えない


def run(cmd, env=None):
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[-400:])
    return r.stdout


def data_through(data: Path) -> str:
    """取得済みのレース結果の一番新しい日付"""
    best = ""
    for f in sorted((data / "race_pages").glob("*.jsonl"))[-2:]:
        for line in f.open(encoding="utf-8"):
            try:
                d = json.loads(line).get("date") or ""
            except Exception:
                continue
            if d > best:
                best = d
    return best


def valid_json(p: Path, must_have=()) -> dict:
    d = json.loads(p.read_text(encoding="utf-8"))
    for k in must_have:
        if k not in d:
            raise RuntimeError(f"出力に {k} が無い")
    return d


def install(tmp: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tmp, dest)


def job_simple(module, out_rel, must, min_items=None, items_key=None):
    def f(data, work):
        tmp = work / Path(out_rel).name
        if module == "sire_db_v1.build_public_map":
            run([sys.executable, "-m", module, "--data", str(data), "--out", str(tmp)])
        else:
            run([sys.executable, "-m", module, "--data", str(data), "--out", str(tmp)])
        d = valid_json(tmp, must)
        if items_key and min_items and len(d.get(items_key) or []) < min_items:
            raise RuntimeError(f"{items_key} が少なすぎる（{len(d.get(items_key) or [])}件）")
        install(tmp, ROOT / out_rel)
        return {"outputs": [out_rel]}
    return f


def job_step1(data, work):
    races = work / "races.json"
    run([sys.executable, "-m", "sim_v2.build_races", "--data", str(data), "--cutoff", "2022-07-01", "--until", "2099-12-31",
         "--with-hid", "--out-backtest", str(races)])
    new = work / "coef.json"
    run([sys.executable, "-m", "sim_v2.step1_fit", "--pages", str(data / "race_pages"), "--data", str(data), "--races", str(races),
         "--laps-cache", str(work / "laps.json"), "--trainers-cache", str(work / "trainers.json"), "--out", str(new)])
    c = valid_json(new, ("T1", "K2", "items", "races_train", "races_test"))
    old = json.loads(COEF_PATH.read_text(encoding="utf-8")) if COEF_PATH.exists() else None
    note = ""
    if old:
        for k in ("T1", "K2"):
            a, b = old[k]["coef_per_unit"], c[k]["coef_per_unit"]
            if a * b <= 0 or abs(b - a) / abs(a) > MAX_COEF_CHANGE:
                raise RuntimeError(f"{k} の係数が前回から大きく動いた（{a} → {b}）。自動では置き換えず、確認が必要")
        note = "T1 {} → {}、K2 {} → {}".format(old["T1"]["coef_per_unit"], c["T1"]["coef_per_unit"], old["K2"]["coef_per_unit"], c["K2"]["coef_per_unit"])
    c["fitted_at"] = datetime.now(JST).strftime("%Y-%m-%d")
    c["data_through"] = data_through(data)
    COEF_PATH.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    run([sys.executable, "-m", "sim_v2.build_strength_public"])
    return {"outputs": ["sim_v2/step1_factor_coef.json", "docs/data/step1_factor_strength_v1.json"], "note": note}


JOBS = [
    # id, 表示名, 実行
    ("trainer_strength", "調教師の強さ（人の成績ページ・STEP1）",
     job_simple("trends_v1.trainer_strength", "docs/data/trainer_strength_v1.json", ("trainers", "base_top3"), 100, "trainers")),
    ("track_trends", "競馬場の傾向", job_simple("trends_v1.track", "docs/data/track_trends_v1.json", ("generated", "races"))),
    ("people_trends", "騎手・調教師の条件別成績", job_simple("trends_v1.people", "docs/data/people_trends_v1.json", ("generated",))),
    ("sire_map", "種牡馬の初勝利マップ", job_simple("sire_db_v1.build_public_map", "docs/data/sire_firstwin_v1.json", ())),
    ("step1_coef", "STEP1の係数（調教師・上がり順位）と要素の強さ", job_step1),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"), required=not os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--only", default="")
    ap.add_argument("--dry", action="store_true", help="記録だけ作る（置き換えはするが git は触らない）")
    a = ap.parse_args()
    data = Path(a.data)
    only = {x for x in a.only.split(",") if x}
    prev = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"jobs": []}
    prev_jobs = {j["id"]: j for j in prev.get("jobs", [])}
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    through = data_through(data)
    jobs = []
    for jid, label, fn in JOBS:
        if only and jid not in only:
            if jid in prev_jobs:
                jobs.append(prev_jobs[jid])
            continue
        work = Path(tempfile.mkdtemp(prefix=f"refresh_{jid}_"))
        try:
            res = fn(data, work)
            jobs.append({"id": jid, "label": label, "status": "ok", "at": now, "data_through": through, **res})
            print("OK  ", jid, res.get("note", ""), flush=True)
        except Exception as e:
            old = prev_jobs.get(jid, {})
            jobs.append({"id": jid, "label": label, "status": "failed", "at": now, "error": str(e)[:300],
                         "last_ok_at": old.get("at") if old.get("status") == "ok" else old.get("last_ok_at"),
                         "last_ok_data_through": old.get("data_through") if old.get("status") == "ok" else old.get("last_ok_data_through")})
            print("FAIL", jid, str(e)[:300], file=sys.stderr, flush=True)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    out = {"version": 1, "generated_at": now, "data_through": through, "jobs": jobs}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [j["id"] for j in jobs if j["status"] != "ok"]
    print("done:", len(jobs) - len(bad), "ok /", len(bad), "failed", bad)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
