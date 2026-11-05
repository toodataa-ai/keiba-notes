"""エンジン用のレースデータに変換する（強さ＝条件付きロジットの値、能力値の0〜100表示も付ける）。"""
from __future__ import annotations
import argparse, bisect, json, math
from pathlib import Path
import numpy as np
from sim_v2 import strength_model as SM

ROOT = Path(__file__).resolve().parents[1]
SURF = {"芝": "turf", "ダート": "dirt"}


def routes():
    cat = json.loads((ROOT / "docs/lab/race-course-catalog-v1.json").read_text(encoding="utf-8"))
    out = {}
    for v in cat["venues"]:
        for r in v["routes"]:
            var = list(r["variants"].values())[0]
            out[(v["code"], r["surface"], r["layout"])] = {"venue": v["code"], "name": v["name"], "turn": v["turn"], "surface": r["surface"], "layout": r["layout"],
                                                          "lap_m": var.get("lap_m"), "straight_m": var.get("straight_m"), "width_m": var.get("width_m"),
                                                          "elevation_m": r.get("elevation_m"), "distances_m": r["distances_m"]}
    # 外→内は、内回りの形で近似（距離は変えない）
    for (v, s, l), r in list(out.items()):
        if l == "outer_to_inner":
            inner = out.get((v, s, "inner"))
            if inner:
                r.update({k: inner[k] for k in ("lap_m", "straight_m", "width_m")})
    return out


def route_for(R, venue_en, surface, layout):
    s = SURF[surface]
    for lay in ([layout] if s == "turf" else ["single"]) + ["single", "inner", "outer"]:
        r = R.get((venue_en, s, lay))
        if r and r.get("lap_m"):
            return r
        if r and lay == "straight":
            return r
    return None


def pct_table(vals):
    v = sorted(x for x in vals if x is not None)
    return v


def pct(tab, x):
    if x is None or not tab:
        return None
    return round(100 * bisect.bisect_left(tab, x) / len(tab))


def ability_tables(races, model):
    """0〜100 の表示用の分布（全出走馬）。分位点だけを持つ（1頭ずつの値は持たない）。"""
    allr = [x for r in races for x in r["runners"]]
    def qs(vals):
        v = sorted(x for x in vals if x is not None)
        return [v[min(len(v) - 1, int(i * len(v) / 100))] for i in range(101)] if v else []
    T = {k: qs([x.get(k) for x in allr]) for k in ("speed", "kick", "power", "stamina")}
    T["peak"] = qs([x["peak"] if x.get("peak") is not None else x["speed"] for x in allr])
    T["early"] = qs([-x["early"] for x in allr]); T["sd"] = qs([-x["sd"] for x in allr])
    sc = []
    for r in races:
        z = SM.score(model, r); sc += list(z - z.mean())
    T["strength"] = qs(sc)
    T["kick_sd"] = float(np.std([x["kick"] for x in allr]) or 1)
    return T


def pctq(q, x):
    if x is None or not q:
        return None
    return int(bisect.bisect_left(q, x) * 100 / (len(q) - 1)) if len(q) > 1 else 50


def runner_out(x, s, mean, T):
    return {"no": x["no"], "name": x.get("name"), "sire": x.get("sire"), "sex": x.get("sex"), "age_m": x.get("age_m"),
            "carried": x.get("carried"), "finish": x.get("finish"), "odds": x.get("odds"), "ninki": x.get("ninki"),
            "time": x.get("time"), "last3f": x.get("last3f"), "pas": x.get("pas"),
            "strength": round(float(s), 3), "early": x["early"], "kick": round(x["kick"] / T["kick_sd"], 3), "power": x["power"], "stamina": x["stamina"],
            "sd": x["sd"], "debut": (x.get("runs_total") or 0) == 0, "runs": x.get("runs_total") or 0,
            "ability": {"総合": pctq(T["strength"], float(s - mean)), "スピード": pctq(T["peak"], x["peak"] if x.get("peak") is not None else x["speed"]),
                        "瞬発力": pctq(T["kick"], x["kick"]), "先行力": pctq(T["early"], -x["early"]), "スタミナ": pctq(T["stamina"], x["stamina"]),
                        "道悪": pctq(T["power"], x["power"]), "安定感": pctq(T["sd"], -x["sd"])}}


def convert(races, model, R, T=None):
    T = T or ability_tables(races, model)
    for r in races:
        r["_score"] = SM.score(model, r)
    out = []
    for r in races:
        rt = route_for(R, r["venue_en"], r["surface"], r["layout"])
        if not rt:
            continue
        sc = r["_score"]; mean = sc.mean()
        runners = [runner_out(x, s, mean, T) for x, s in zip(r["runners"], sc)]
        out.append({k: r[k] for k in ("code", "date", "venue", "venue_en", "surface", "dist", "layout", "going", "race_no", "race_name", "class", "grade", "std_time", "std_l3")}
                   | {"route": rt, "runners": runners})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--races", required=True); ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--select", default="")
    ap.add_argument("--save-model", help="係数と0〜100の分位表を保存（当日のレース用）")
    a = ap.parse_args()
    races = json.loads(Path(a.races).read_text(encoding="utf-8"))["races"]
    model = json.loads(Path(a.model).read_text(encoding="utf-8"))
    T = ability_tables(races, model)
    if a.save_model:
        Path(a.save_model).write_text(json.dumps({"model": {k: model[k] for k in ("feats", "mu", "sd", "beta")}, "tables": T,
                                                  "note": "能力の係数と、0〜100表示の分位表。学習は2025-07〜2026-02、検証は2026-03〜。"}, ensure_ascii=False), encoding="utf-8")
    out = convert(races, model, routes(), T)
    if a.select == "public":
        # 画面用：2026年9月以降の重賞と、各開催日の11R（土日）だけ
        out = [r for r in out if r["date"] >= "2026-09-01" and (r.get("grade") or r["race_no"] == 11)]
    Path(a.out).write_text(json.dumps({"races": out}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(len(out))


if __name__ == "__main__":
    main()
