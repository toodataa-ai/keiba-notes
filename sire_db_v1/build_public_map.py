"""種牡馬の初勝利マップ用の公開データを作る（集計のみ・馬名や1頭ずつの記録は出さない）。
入力: 非公開リポジトリの data_v2（--data か SIRE_DATA_DIR）。出力: docs/data/sire_firstwin_v1.json"""
from __future__ import annotations
import argparse, collections, glob, json, os, statistics as st
from datetime import date
from pathlib import Path
from sire_db_v1.aggregate import months_between

ROOT = Path(__file__).resolve().parents[1]


def q(xs, p):
    xs = sorted(xs); i = (len(xs) - 1) * p; lo = int(i); hi = min(lo + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (i - lo), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--min-winners", type=int, default=15)
    ap.add_argument("--out", default=str(ROOT / "docs/data/sire_firstwin_v1.json"))
    a = ap.parse_args()
    by = collections.defaultdict(lambda: {"n": 0, "pts": []})
    races = 0
    done = Path(a.data) / "races_done.txt"
    if done.is_file():
        races = sum(1 for _ in open(done, encoding="utf-8"))
    horses = 0
    for f in sorted(glob.glob(str(Path(a.data) / "horses_*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            h = json.loads(line); horses += 1
            s = (h.get("ped") or {}).get("sire")
            if not s or not h.get("birth"):
                continue
            by[s]["n"] += 1
            w = sorted([r for r in h.get("history") or [] if r.get("finish") == 1 and r.get("dist") and r.get("surface") in ("芝", "ダート")], key=lambda r: r["date"])
            if not w:
                continue
            try:
                m = months_between(h["birth"], w[0]["date"])
            except Exception:
                continue
            by[s]["pts"].append((m, w[0]["dist"], 1 if w[0]["surface"] == "芝" else 0))
    sires = []
    for s, v in by.items():
        p = v["pts"]
        if len(p) < a.min_winners:
            continue
        ms = [x[0] for x in p]; ds = [x[1] for x in p]
        sires.append({"sire": s, "horses": v["n"], "winners": len(p),
                      "mean_months": round(sum(ms) / len(ms), 2), "mean_dist": round(sum(ds) / len(ds)),
                      "median_months": st.median(ms), "median_dist": st.median(ds),
                      "q1_months": q(ms, .25), "q3_months": q(ms, .75), "q1_dist": q(ds, .25), "q3_dist": q(ds, .75),
                      "turf_share": round(sum(x[2] for x in p) / len(p), 3)})
    sires.sort(key=lambda x: -x["winners"])
    out = {"schema": "sire_firstwin_v1", "generated_on": date.today().isoformat(),
           "source_note": "JRAのレース（2018年以降を新しい年から順に取得中）に出走した馬と、その馬の全出走履歴。初勝利＝その馬の最初の1着。月齢は誕生日からの月数。",
           "races_fetched": races, "races_total_estimate": 30537, "horses_fetched": horses,
           "min_winners": a.min_winners, "sires": sires}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(sires), races, horses)


if __name__ == "__main__":
    main()
