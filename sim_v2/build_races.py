"""シミュレータ v2 用のレース一覧を作る（研究用）。
--cutoff より前の走りだけで基準タイムを作り、各レースの出走馬の能力値は「そのレースの日より前」の走りだけで計算する。
出力は2種類：
  --out-backtest  検証用（多数のレース。非公開の作業用ファイル。公開しない）
  --out-public    LAB の画面用（選んだレースだけ。馬名・能力値・結果。生の出走履歴は含めない）"""
from __future__ import annotations
import argparse, collections, json, math, os, statistics as st
from datetime import date
from pathlib import Path
from sim_v2 import features as F

GRADES = {"GI": 1, "GII": 2, "GIII": 3}


def months(birth, d):
    b = date.fromisoformat(birth); x = date.fromisoformat(d)
    return (x.year - b.year) * 12 + x.month - b.month - (1 if x.day < b.day else 0)


def change(hist, lb):
    """前走からの変化：距離の延長・短縮、芝ダの替わり。"""
    prior = [r for r in hist if r["date"] < lb["date"]]
    if not prior:
        return {"dist_change": 0.0, "surf_switch": 0}
    last = prior[-1]
    return {"dist_change": round(math.log(lb["dist"] / last["dist"]), 3) if last.get("dist") else 0.0,
            "surf_switch": 1 if last["surface"] != lb["surface"] else 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--cutoff", default="2025-07-01")
    ap.add_argument("--until", default="2026-12-31")
    ap.add_argument("--out-backtest", required=True)
    ap.add_argument("--out-public")
    ap.add_argument("--out-standards")
    a = ap.parse_args()
    lab = F.load_labels()
    runs, horses = F.load_runs(a.data, lab)
    train = [r for r in runs if r["date"] < a.cutoff]
    std = F.standards(train)
    F.run_figures(runs, std)
    JT = F.JockeyTable(runs)
    sire_of = {h: v.get("sire") for h, v in horses.items()}
    # 父×芝ダの勝ちやすさ（全走）と、父の初出走での勝ちやすさ
    first = {}
    for r in sorted(runs, key=lambda r: r["date"]):
        first.setdefault(r["hid"], r["code"])
    ST = F.GroupTable(runs, lambda r: (sire_of.get(r["hid"]), r["surface"]))
    SD = F.GroupTable(runs, lambda r: sire_of.get(r["hid"]), only=lambda r: first.get(r["hid"]) == r["code"])
    byh = collections.defaultdict(list)
    for r in runs:
        byh[r["hid"]].append(r)
    for v in byh.values():
        v.sort(key=lambda r: r["date"])
    byrace = collections.defaultdict(list)
    for r in runs:
        if a.cutoff <= r["date"] <= a.until:
            byrace[r["code"]].append(r)
    out = []
    for code, rs in sorted(byrace.items()):
        lb = lab.get(code)
        if not lb or not rs[0]["heads"] or len(rs) < rs[0]["heads"] or len(rs) < 5:
            continue
        if lb["dist"] not in range(1000, 3700) or lb["surface"] not in ("芝", "ダート"):
            continue
        key = (lb["venue"], lb["surface"], lb["dist"], lb["layout"], F.GOING_GROUP.get(lb["going"], "良"))
        s = std.get(key)
        runners = []
        for r in rs:
            if r["finish"] is None or r["horse_no"] is None:
                continue
            rt = F.rating(byh[r["hid"]], lb["date"], lb["surface"], lb["dist"], lb["going"])
            h = horses.get(r["hid"], {})
            runners.append({"no": r["horse_no"], "name": h.get("name"), "sire": h.get("sire"), "sex": h.get("sex"),
                            "age_m": months(h["birth"], lb["date"]) if h.get("birth") else None,
                            "carried": r["carried"], "bw": r["body_weight"], "finish": r["finish"], "odds": r["odds"], "ninki": r["ninki"],
                            "time": r["time"], "last3f": r["last3f"], "pas": r["pas"], **rt,
                            "jockey": round(JT.ae(r.get("jockey_id"), lb["date"]), 3), "sire_surf": round(ST.ae((h.get("sire"), lb["surface"]), lb["date"]), 3), "sire_debut": round(SD.ae(h.get("sire"), lb["date"]), 3), "bw_diff": r.get("bw_diff"), **change(byh[r["hid"]], lb)})
        if len(runners) < 5:
            continue
        grade = None
        for r in rs:
            pass
        out.append({"code": code, "date": lb["date"], "venue": lb["venue"], "venue_en": F.VENUE_EN[lb["venue"]], "surface": lb["surface"], "dist": lb["dist"],
                    "layout": lb["layout"], "going": lb["going"], "race_no": lb["race_no"], "race_name": lb["race_name"], "class": lb["class"], "level": rs[0].get("level"), "grade": next((g for g, v in F.GRADE_LEVEL.items() if v == rs[0].get("level")), None),
                    "std_time": round(s["t"], 2) if s else None, "std_l3": s.get("l3") if s else None, "heads": len(runners), "runners": sorted(runners, key=lambda x: x["no"])})
    Path(a.out_backtest).write_text(json.dumps({"cutoff": a.cutoff, "races": out}, ensure_ascii=False), encoding="utf-8")
    print("races", len(out))
    if a.out_standards:
        rows = [{"venue": k[0], "surface": k[1], "dist": k[2], "layout": k[3], "going": k[4], "t": round(v["t"], 2), "l3": v.get("l3"), "n": v["n"]} for k, v in std.items()]
        Path(a.out_standards).write_text(json.dumps({"note": "条件ごとの基準タイム（上位半分の着順の馬の中央値・秒）。研究用。", "cutoff": a.cutoff, "rows": rows}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
