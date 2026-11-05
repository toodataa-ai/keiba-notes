"""当日のレース（結果が出る前）を、シミュレータv2で見られるようにする（LAB・研究用）。
入力: Claude用の出馬表（claude_track/inputs/<日付>-<場>-11/*.json、オッズ・人気は除去済み）と、非公開の data_v2。
出力: docs/lab/sim-v2/upcoming.json（馬名・能力値・強さだけ。結果・オッズは無い）。正式予想・買い目には使わない。"""
from __future__ import annotations
import argparse, collections, glob, json, math, os
from datetime import date
from pathlib import Path
import numpy as np
from sim_v2 import features as F, strength_model as SM, export as X

ROOT = Path(__file__).resolve().parents[1]
CLASS = {"新馬": "新馬", "未勝利": "未勝利", "1勝クラス": "1勝クラス", "2勝クラス": "2勝クラス", "3勝クラス": "3勝クラス", "オープン": "オープン"}


def class_of(card):
    c = (card.get("class") or "") + " " + (card.get("race_name") or "")
    for k in ("新馬", "未勝利", "1勝クラス", "2勝クラス", "3勝クラス"):
        if k in c:
            return k
    return "オープン"


def grade_of(card):
    n = card.get("race_name") or ""
    for g, k in (("GI", "（GI）"), ("GII", "（GII）"), ("GIII", "（GIII）")):
        if k in n:
            return g
    return "L" if "（L）" in n or "リステッド" in n else None


def going_of(card):
    surf = card["surface"]
    for c in card.get("going_cells") or []:
        if surf[0] in c:
            for g in ("不良", "稍重", "重", "良"):
                if g in c:
                    return g
    return "良"


def latest_cards(dates):
    out = []
    for d in dates:
        for dirp in sorted(glob.glob(str(ROOT / "claude_track/inputs" / f"{d}-*-11"))):
            fs = sorted(glob.glob(dirp + "/*.json"))
            if fs:
                out.append(json.loads(Path(fs[-1]).read_text(encoding="utf-8")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--dates", required=True, help="YYYY-MM-DD をカンマ区切り")
    ap.add_argument("--cards", nargs="*", help="出馬表JSONを直接指定（試験用）")
    ap.add_argument("--out", default=str(ROOT / "docs/lab/sim-v2/upcoming.json"))
    a = ap.parse_args()
    dates = [d.strip() for d in a.dates.split(",") if d.strip()]
    cards = [json.loads(Path(c).read_text(encoding="utf-8")) for c in a.cards] if a.cards else latest_cards(dates)
    if not cards:
        print("no cards"); return
    M = json.loads((ROOT / "sim_v2/model_v2.json").read_text(encoding="utf-8")); model = M["model"]; T = M["tables"]
    lab = F.load_labels()
    runs, horses = F.load_runs(a.data, lab)
    first_day = min(c["date"] for c in cards)
    std = F.standards([r for r in runs if r["date"] < first_day]); F.run_figures(runs, std)
    byh = collections.defaultdict(list)
    for r in runs:
        byh[r["hid"]].append(r)
    for v in byh.values():
        v.sort(key=lambda r: r["date"])
    byname = collections.defaultdict(list)
    for hid, h in horses.items():
        if h.get("name"):
            byname[h["name"]].append(hid)
    JT = F.GroupTable(runs, lambda r: r.get("jockey_name"), k=40.0)
    sire_of = {h: v.get("sire") for h, v in horses.items()}
    firstcode = {}
    for r in sorted(runs, key=lambda r: r["date"]):
        firstcode.setdefault(r["hid"], r["code"])
    ST = F.GroupTable(runs, lambda r: (sire_of.get(r["hid"]), r["surface"]))
    SD = F.GroupTable(runs, lambda r: sire_of.get(r["hid"]), only=lambda r: firstcode.get(r["hid"]) == r["code"])
    R = X.routes(); out = []
    for c in cards:
        venue = c.get("venue"); surface = c["surface"]; dist = c["distance_m"]; d = c["date"]; going = going_of(c)
        layout = F.layout_of("（" + surface + "・" + (c.get("course_detail") or "") + "）", venue, surface, dist)
        s = std.get((venue, surface, dist, layout, F.GOING_GROUP.get(going, "良")))
        lvl = F.class_level(class_of(c), grade_of(c))
        runners = []; matched = 0
        for h in c["horses"]:
            ids = byname.get(h["name"]) or []
            hid = None
            if ids:
                # 同名がいれば、年齢が合う馬
                hid = sorted(ids, key=lambda i: abs(((date.fromisoformat(d).year - int((horses[i].get("birth") or "2000")[:4])) - (h.get("age") or 0))))[0]
                matched += 1
            hist = byh.get(hid, []) if hid else []
            rt = F.rating(hist, d, surface, dist, going)
            prior = [r for r in hist if r["date"] < d]; last = prior[-1] if prior else None
            sire = (horses.get(hid) or {}).get("sire") or h.get("sire")
            bwc = h.get("body_weight_change")
            try:
                bwc = int(str(bwc).replace("+", "")) if bwc not in (None, "", "計不") else None
            except Exception:
                bwc = None
            runners.append({"no": h["number"], "name": h["name"], "sire": sire, "sex": h.get("sex"),
                            "age_m": None, "carried": h.get("weight_kg"), "finish": None, "odds": None, "ninki": None,
                            **rt, "jockey": round(JT.ae(F.norm_name(h.get("jockey")), d), 3), "bw_diff": bwc,
                            "dist_change": round(math.log(dist / last["dist"]), 3) if last and last.get("dist") else 0.0,
                            "surf_switch": 1 if last and last["surface"] != surface else 0,
                            "sire_surf": round(ST.ae((sire, surface), d), 3), "sire_debut": round(SD.ae(sire, d), 3)})
        race = {"code": c.get("source_cname"), "date": d, "venue": venue, "venue_en": F.VENUE_EN.get(venue), "surface": surface, "dist": dist,
                "layout": layout, "going": going, "race_no": c.get("race_no"), "race_name": c.get("race_name"), "class": class_of(c), "grade": grade_of(c),
                "level": lvl, "std_time": round(s["t"], 2) if s else None, "std_l3": s.get("l3") if s else None, "runners": runners}
        z = SM.score(model, race); mean = z.mean()
        rt_ = X.route_for(R, race["venue_en"], surface, layout)
        out.append({k: race[k] for k in ("code", "date", "venue", "venue_en", "surface", "dist", "layout", "going", "race_no", "race_name", "class", "grade", "std_time", "std_l3")}
                   | {"route": rt_, "upcoming": True, "matched": matched, "runners": [X.runner_out(x, sc, mean, T) for x, sc in zip(runners, z)]})
        print(d, venue, c.get("race_name"), "馬", len(runners), "データあり", matched)
    Path(a.out).write_text(json.dumps({"generated_for": dates, "races": out}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
