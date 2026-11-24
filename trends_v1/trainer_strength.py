#!/usr/bin/env python3
"""調教師の強さ（レースによらない絶対的な指標）。予想の補正（shared-v1.3 の mult_trainer）と同じ計算。公開するのは集計だけ。
  python3 -m trends_v1.trainer_strength --data <非公開 data_v2> --out docs/data/trainer_strength_v1.json
強さ T1＝（その調教師の3着内率を、少ない走数のときは全体の率へ縮める）−全体の3着内率。倍率＝exp(係数×T1)。標準偏差の±1.5倍で打ち切る。"""
from __future__ import annotations
import argparse, json, math, sys
from collections import defaultdict
from datetime import date, timedelta, timezone, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim_v2 import step1_factors as S
from sire_db_v1.debut_common import load_horses

MIN_RUNS_12M = 30      # 直近1年の出走がこれ以上の調教師だけ載せる


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    hs = load_horses(a.data)
    trainers, _ = S.load_race_index(Path(a.data) / "race_pages")
    today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    cnt, allc = S.trainer_counts(hs, trainers, "9999-12-31")
    since = (date.fromisoformat(today) - timedelta(days=365)).isoformat()
    n12 = defaultdict(int); last = {}
    for h in hs.values():
        for r in h.get("history") or []:
            tr = (trainers.get(r.get("code")) or {}).get(h["id"])
            if tr and r.get("date"):
                if r["date"] >= since: n12[tr] += 1
                if tr not in last or r["date"] > last[tr]: last[tr] = r["date"]
    names = {}
    for h in sorted(hs.values(), key=lambda h: h.get("fetched") or ""):
        p = h.get("profile") or {}; tid = p.get("調教師（所属）_id"); nm = p.get("調教師（所属）")
        if tid and nm: names[tid] = nm
    rows = []
    for tid, v in cnt.items():
        if n12.get(tid, 0) < MIN_RUNS_12M or tid not in names: continue
        f = S.trainer_factor(cnt, allc, tid)
        nm = names[tid]; base_nm = nm.rsplit(" (", 1)[0] if " (" in nm else nm
        loc = nm.rsplit(" (", 1)[1].rstrip(")") if " (" in nm else None
        rows.append({"id": tid, "name": base_nm, "loc": loc, "runs": v[1], "runs_12m": n12[tid], "top3": f["top3_rate_raw"], "t1": f["t1"], "mult": f["mult"], "last": last.get(tid)})
    rows.sort(key=lambda r: -r["t1"])
    out = {"version": 1, "generated": today, "since": "2018", "base_top3": round(allc[0] / allc[1], 4), "total_runs": allc[1],
           "shrink_runs": S.K_TRAINER, "coef_per_unit": S.COEF["T1"]["coef_per_unit"], "sd": S.COEF["T1"]["sd"], "cap_sd": S.CAP_SD,
           "mult_min": round(math.exp(-S.COEF["T1"]["coef_per_unit"] * S.CAP_SD * S.COEF["T1"]["sd"]), 3),
           "mult_max": round(math.exp(S.COEF["T1"]["coef_per_unit"] * S.CAP_SD * S.COEF["T1"]["sd"]), 3), "trainers": rows}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("調教師", len(rows), "全体の3着内率", out["base_top3"])
    for r in rows[:5] + rows[-3:]: print(r["name"], r["runs"], r["top3"], r["t1"], r["mult"])


if __name__ == "__main__":
    main()
