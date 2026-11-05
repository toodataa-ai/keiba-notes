"""レースシミュレータ v2 の能力値づくり（研究用・LAB）。
入力: 非公開リポジトリの data_v2（馬ごとの全出走履歴）と、公開済みの JRA 馬場ラベル（baba_models_v2/going_labels）。
考え方:
  1走ごとに「同じ競馬場・芝ダ・距離・内外・馬場の基準タイム」との差（1000mあたり何秒速いか）＝スピード指数を出す。
  上がり3Fも同じ条件の基準との差＝瞬発力、1角の位置÷頭数＝先行力。
  あるレースの能力値は、そのレースの日より前の走りだけを、新しさ・距離の近さ・芝ダの一致で重みづけして平均する（未来の情報は使わない）。
出力（この関数群は呼び出し側が保存先を決める。生データそのものは出さない）。"""
from __future__ import annotations
import csv, glob, json, math, statistics as st, collections
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENUE_CODE = {"札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05", "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10"}
VENUE_EN = {"札幌": "sapporo", "函館": "hakodate", "福島": "fukushima", "新潟": "niigata", "東京": "tokyo", "中山": "nakayama", "中京": "chukyo", "京都": "kyoto", "阪神": "hanshin", "小倉": "kokura"}
GOING_GROUP = {"良": "良", "稍重": "稍重", "重": "重", "不良": "重"}


def layout_of(detail: str, venue: str, surface: str, dist: int) -> str:
    """公式の表記（例：（芝・右 外））から、コース型（周回／内回り／外回り／直線／外→内）を決める。"""
    d = detail or ""
    if surface == "ダート":
        return "single"
    if "直" in d:
        return "straight"
    if "外→内" in d or "内外" in d:
        return "outer_to_inner"
    two = venue in ("中山", "京都", "阪神", "新潟")
    if "外内" in d:
        return "inner" if venue == "新潟" else "outer_to_inner"
    if "外" in d:
        return "outer"
    return "inner" if two else "single"


def load_labels():
    lab = {}
    for f in sorted(glob.glob(str(ROOT / "baba_models_v2/going_labels/jra_going_*.csv"))):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            try:
                code = r["date"][2:4] + VENUE_CODE[r["track"]] + f"{int(r['kai']):02d}{int(r['nichime']):02d}{int(r['race_no']):02d}"
            except Exception:
                continue
            lab[code] = {"date": r["date"], "venue": r["track"], "surface": r["surface"], "going": r["going"], "dist": int(r["distance_m"] or 0),
                         "layout": layout_of(r.get("course_detail", ""), r["track"], r["surface"], int(r["distance_m"] or 0)),
                         "race_name": r.get("race_name", ""), "class": r.get("class", ""), "race_no": int(r["race_no"]), "start_time": r.get("start_time", "")}
    return lab


CLASS_LEVEL = {"新馬": 0.0, "未勝利": 0.0, "1勝クラス": 1.0, "2勝クラス": 2.0, "3勝クラス": 3.0, "オープン": 4.0}
GRADE_LEVEL = {"L": 4.5, "GIII": 5.0, "重賞": 5.0, "GII": 5.5, "GI": 6.0}


def class_level(cls, grade):
    """レースの格を数字に（新馬・未勝利0〜G1 6）。"""
    if grade in GRADE_LEVEL:
        return GRADE_LEVEL[grade]
    return CLASS_LEVEL.get(cls or "", None)


def margin_sec(m):
    """着差（勝ち馬との差・秒）。勝ち馬は2着との差がマイナスで入るので0にそろえる。"""
    try:
        v = float(str(m).replace("+", ""))
    except Exception:
        return None
    return max(0.0, v)


def tsec(t):
    try:
        if ":" in t:
            m, s = t.split(":"); return int(m) * 60 + float(s)
        return float(t)
    except Exception:
        return None


def load_runs(data_dir: Path, labels: dict):
    """1走1行（馬×レース）。レースの馬場・内外は公開ラベルから補う。"""
    runs = []; horses = {}; seen = set()
    for f in sorted(glob.glob(str(Path(data_dir) / "horses_*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            h = json.loads(line)
            hid = h["id"]
            ped = h.get("ped") or {}
            horses[hid] = {"name": h.get("name"), "sex": h.get("sex"), "birth": h.get("birth"), "sire": ped.get("sire"), "dam_sire": ped.get("dam_sire")}
            for r in h.get("history") or []:
                code = r.get("code"); k = (hid, code)
                if not code or k in seen or r.get("surface") not in ("芝", "ダート"):
                    continue
                seen.add(k)
                lb = labels.get(code)
                t = tsec(r.get("time") or "")
                fin = r.get("finish") if isinstance(r.get("finish"), int) else None
                pas = [int(x) for x in str(r.get("passing") or "").split("-") if x.strip().isdigit()]
                runs.append({"hid": hid, "code": code, "date": r["date"], "venue": r.get("venue"), "surface": r["surface"], "dist": r.get("dist"),
                             "heads": r.get("heads"), "finish": fin, "horse_no": int(r["horse_no"]) if str(r.get("horse_no") or "").isdigit() else None,
                             "time": t, "last3f": r.get("last3f"), "first_pos": pas[0] if pas else None, "pas": pas,
                             "carried": r.get("carried"), "odds": r.get("odds"), "ninki": r.get("ninki"), "body_weight": r.get("body_weight"),
                             "going": (lb or {}).get("going"), "layout": (lb or {}).get("layout", "single"), "race_name": (lb or {}).get("race_name") or r.get("race"),
                             "margin": margin_sec(r.get("margin")), "level": class_level((lb or {}).get("class"), r.get("grade"))})
    return runs, horses


def standards(runs):
    """条件ごとの基準タイム・基準上がり（上位半分の着順の馬の中央値）。"""
    cell = collections.defaultdict(lambda: {"t": [], "l3": []}); cell2 = collections.defaultdict(lambda: {"t": [], "l3": []})
    for r in runs:
        if not r["time"] or not r["finish"] or not r["heads"] or r["finish"] > max(3, r["heads"] // 2) or not r["going"]:
            continue
        k = (r["venue"], r["surface"], r["dist"], r["layout"], GOING_GROUP.get(r["going"], "良"))
        cell[k]["t"].append(r["time"]); cell2[k[:4]]["t"].append(r["time"])
        if r["last3f"]:
            cell[k]["l3"].append(r["last3f"]); cell2[k[:4]]["l3"].append(r["last3f"])
    # 馬場ごとの全体のずれ（1000mあたり秒）
    shift = collections.defaultdict(list)
    for k, v in cell.items():
        base = cell2.get(k[:4])
        if base and len(v["t"]) >= 8 and len(base["t"]) >= 20:
            shift[(k[1], k[4])].append((st.median(v["t"]) - st.median(base["t"])) / k[2] * 1000)
    gshift = {k: st.median(v) for k, v in shift.items() if v}
    out = {}
    for k, v in cell2.items():
        if len(v["t"]) < 8:
            continue
        for g in ("良", "稍重", "重"):
            c = cell.get(k + (g,))
            if c and len(c["t"]) >= 12:
                out[k + (g,)] = {"t": st.median(c["t"]), "l3": st.median(c["l3"]) if c["l3"] else None, "n": len(c["t"])}
            else:
                out[k + (g,)] = {"t": st.median(v["t"]) + gshift.get((k[1], g), 0.0) * k[2] / 1000, "l3": st.median(v["l3"]) if v["l3"] else None, "n": len(v["t"]), "derived": True}
    return out


def run_figures(runs, std):
    for r in runs:
        r["fig"] = r["l3fig"] = r["early"] = None
        if not r["going"]:
            continue
        s = std.get((r["venue"], r["surface"], r["dist"], r["layout"], GOING_GROUP.get(r["going"], "良")))
        if not s:
            continue
        if r["time"] and r["finish"]:
            f = (s["t"] - r["time"]) / r["dist"] * 1000
            if r["carried"]:
                f += (r["carried"] - 56) * 0.06
            r["fig"] = max(-6.0, min(4.0, f))
        if r["last3f"] and s.get("l3"):
            r["l3fig"] = max(-4.0, min(3.0, s["l3"] - r["last3f"]))
        if r["first_pos"] and r["heads"]:
            r["early"] = (r["first_pos"] - 1) / max(1, r["heads"] - 1)


def days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def rating(hist, on_date, surface, dist, going):
    """on_date より前の走りだけで能力値を出す。"""
    prior = [r for r in hist if r["date"] < on_date]
    def wsum(key, same_surface=True, dist_scale=700.0):
        num = den = 0.0
        for r in prior:
            v = r.get(key)
            if v is None:
                continue
            w = math.exp(-days(r["date"], on_date) / 300.0)
            w *= math.exp(-abs((r["dist"] or dist) - dist) / dist_scale)
            w *= 1.0 if r["surface"] == surface else (0.3 if same_surface else 0.8)
            num += w * v; den += w
        return num, den
    n_s, d_s = wsum("fig")
    prior_w, prior_mean = 0.8, -0.8
    speed = (n_s + prior_w * prior_mean) / (d_s + prior_w)
    # 良い走りに少し寄せる（能力の上限を見る）：直近8走の上位3つ
    figs = sorted([r["fig"] for r in sorted(prior, key=lambda r: r["date"])[-8:] if r.get("fig") is not None and r["surface"] == surface], reverse=True)
    peak = sum(figs[:3]) / len(figs[:3]) if figs else None
    if peak is not None:
        speed = 0.65 * speed + 0.35 * (peak * 0.8 + prior_mean * 0.2 if len(figs) < 3 else peak)
    n_k, d_k = wsum("l3fig")
    kick = (n_k + 0.8 * 0.0) / (d_k + 0.8)
    n_e, d_e = wsum("early", same_surface=False, dist_scale=1500.0)
    early = (n_e + 1.0 * 0.5) / (d_e + 1.0)
    # 道悪の得手：重・不良での指数－良での指数（縮小）
    wet = [r["fig"] for r in prior if r.get("fig") is not None and r["going"] in ("重", "不良") and r["surface"] == surface]
    dry = [r["fig"] for r in prior if r.get("fig") is not None and r["going"] == "良" and r["surface"] == surface]
    power = (sum(wet) / len(wet) - (sum(dry) / len(dry) if dry else 0)) * len(wet) / (len(wet) + 3) if wet else 0.0
    # 距離の得手：長い距離と短い距離の指数の差
    long_ = [r["fig"] for r in prior if r.get("fig") is not None and r["dist"] and r["dist"] >= 2000]
    short = [r["fig"] for r in prior if r.get("fig") is not None and r["dist"] and r["dist"] <= 1400]
    stamina = ((sum(long_) / len(long_)) - (sum(short) / len(short))) if long_ and short else 0.0
    if long_ and not short: stamina = 0.4
    if short and not long_: stamina = -0.4
    allf = [r["fig"] for r in prior if r.get("fig") is not None]
    sd = st.pstdev(allf[-10:]) if len(allf) >= 3 else 1.6
    n = len([r for r in prior if r.get("fig") is not None])
    last = sorted(prior, key=lambda r: r["date"])[-3:]
    finpct = [(r["finish"] - 1) / max(1, r["heads"] - 1) for r in last if r.get("finish") and r.get("heads")]
    marg = [min(r["margin"], 3.0) for r in last if r.get("margin") is not None]
    ninki = [math.log(r["ninki"]) for r in last if r.get("ninki")]
    lv = [r["level"] for r in last if r.get("level") is not None]
    dsl = days(last[-1]["date"], on_date) if last else None
    return {"speed": round(speed, 3), "kick": round(kick, 3), "early": round(early, 3), "power": round(power, 3),
            "stamina": round(stamina, 3), "sd": round(sd, 3), "n": n, "going_now": going,
            "peak": round(peak, 3) if peak is not None else None,
            "finpct3": round(sum(finpct) / len(finpct), 3) if finpct else None,
            "margin3": round(sum(marg) / len(marg), 3) if marg else None,
            "lninki3": round(sum(ninki) / len(ninki), 3) if ninki else None,
            "level_last": max(lv) if lv else None,
            "days_since": dsl, "runs_total": len(prior)}
