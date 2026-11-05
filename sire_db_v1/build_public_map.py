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


LEVELS = [("all", "初勝利", 15), ("open", "オープン初勝利", 5), ("graded", "重賞初勝利", 3), ("g1", "G1初勝利", 1)]


def level_of(r, cls):
    """そのレースがどの格か（障害は除く）。cls は公開の馬場ラベルのクラス（オープン・3勝クラス など）。"""
    g = r.get("grade") or ""
    if g.startswith("J"):
        return None
    lv = {"all"}
    if g in ("L", "GIII", "GII", "GI", "重賞") or cls == "オープン":
        lv.add("open")
    if g in ("GIII", "GII", "GI", "重賞"):
        lv.add("graded")
    if g == "GI":
        lv.add("g1")
    return lv


def class_map():
    import csv
    from sire_db_v1 import aggregate  # noqa: F401  (同じパッケージの読み込み確認)
    vc = {"札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05", "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10"}
    out = {}
    for f in sorted(glob.glob(str(ROOT / "baba_models_v2/going_labels/jra_going_*.csv"))):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            try:
                out[r["date"][2:4] + vc[r["track"]] + f"{int(r['kai']):02d}{int(r['nichime']):02d}{int(r['race_no']):02d}"] = r.get("class", "")
            except Exception:
                pass
    return out


def summarize(p):
    ms = [x[0] for x in p]; ds = [x[1] for x in p]
    return {"winners": len(p), "mean_months": round(sum(ms) / len(ms), 2), "mean_dist": round(sum(ds) / len(ds)),
            "median_months": st.median(ms), "median_dist": st.median(ds),
            "q1_months": q(ms, .25), "q3_months": q(ms, .75), "q1_dist": q(ds, .25), "q3_dist": q(ds, .75),
            "turf_share": round(sum(x[2] for x in p) / len(p), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--out", default=str(ROOT / "docs/data/sire_firstwin_v1.json"))
    a = ap.parse_args()
    cmap = class_map()
    by = collections.defaultdict(lambda: {"n": 0, "pts": collections.defaultdict(list)})
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
            got = set()
            for r in sorted(h.get("history") or [], key=lambda r: r["date"]):
                if r.get("finish") != 1 or not r.get("dist") or r.get("surface") not in ("芝", "ダート"):
                    continue
                lv = level_of(r, cmap.get(r.get("code"), ""))
                if not lv:
                    continue
                try:
                    m = months_between(h["birth"], r["date"])
                except Exception:
                    continue
                for L in lv - got:
                    by[s]["pts"][L].append((m, r["dist"], 1 if r["surface"] == "芝" else 0))
                got |= lv
    sires = []
    for s, v in by.items():
        if len(v["pts"]["all"]) < LEVELS[0][2]:
            continue
        row = {"sire": s, "horses": v["n"], **summarize(v["pts"]["all"]), "levels": {}}
        for key, _, mn in LEVELS[1:]:
            p = v["pts"].get(key) or []
            row["levels"][key] = summarize(p) if len(p) >= mn else {"winners": len(p)}
        sires.append(row)
    sires.sort(key=lambda x: -x["winners"])
    out = {"schema": "sire_firstwin_v1", "generated_on": date.today().isoformat(),
           "source_note": "JRAのレース（2018年以降を新しい年から順に取得中）に出走した馬と、その馬の全出走履歴。初勝利＝その格で最初の1着。月齢は誕生日からの月数。障害は除く。",
           "races_fetched": races, "races_total_estimate": 30537, "horses_fetched": horses,
           "levels": [{"key": k, "label": l, "min_winners": m} for k, l, m in LEVELS],
           "min_winners": LEVELS[0][2], "sires": sires}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(sires), races, horses, {k: sum(1 for x in sires if (x["levels"].get(k) or {}).get("mean_months") is not None) for k, _, _ in LEVELS[1:]})


if __name__ == "__main__":
    main()
