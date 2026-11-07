"""馬場傾向（その日の芝・ダートが、スピード寄りか・前残りか・外が伸びるか）を、結果ページから数字にする。

検証（2022〜2026・約1.5万レース、2026-11-08）：前日の傾向は翌日に続く。
  スピード（勝ち時計の速さ）… 芝 r=0.65 / ダート r=0.63（公式の馬場状態だけの予測力0.40 → 前日の傾向を足すと0.58〜0.62）
  前残り（人気より前の馬が好走）… ダート r=0.37 / 芝 r=0.20（芝の1400m以下は続かない）
  外枠有利 … 芝 r=0.21 / ダート r=0.14（予測力の上がり幅が小さく、表示のみ）
予想には使わない部分（外枠）と使う部分（スピード・前残り）を分けて出す。公開するのは集計だけ（馬名・1頭ずつの記録は出さない）。
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

SURFACES = ("芝", "ダート")
MIN_FIELD = 8          # 頭数が少ないレースは前残り・外枠の測定に使わない
MIN_DAY_RACES = 4      # 1日に最低このレース数がないと傾向とは言わない
MIN_BASE_N = 12        # 勝ち時計の基準を作るのに必要なレース数
TURF_FRONT_MIN_DIST = 1500   # 芝の短距離は前残りが続かなかったので、前残りの測定から外す

_HEAD = r"(\d+)回(\S{1,3}?)(\d+)日\s+(\d+):(\d+)发走\s+(\S.*?)\s+".replace("发","発")
_TAIL = r"天気：\s*(\S+)\s+馬場：\s*(\S+)\s+(.*?)\s+本賞金"
# 平地：「芝・右 2000m」「芝・右・内2周 3600m」「ダート・右 1200m」。障害：「障害・芝→ダート 2970m」
_HEAD_RE = re.compile(_HEAD + r"(芝|ダート)(?:・\S{0,12})?\s+(\d{3,4})m\s+" + _TAIL)
_HURDLE_RE = re.compile(_HEAD + r"(障害)(?:・\S{0,12})?\s+(\d{3,4})m\s+" + _TAIL)
MIN_PARSE_FIELD = 2      # 5頭立てなどの少頭数も「読めた」ことにする（使えるかどうかは usable で決める）
MIN_USABLE_FIELD = 6


_CORNER_TOK = re.compile(r"\(([\d,]+)\)|(\d+)")


def corner_order(cell: str) -> dict:
    """コーナー通過順位の文字列（例『2 (6,16)(1,7,11)18』）→ {馬番: 順位}。かっこの中は同じくらいの位置なので、その並びの平均の順位にする。"""
    out, i = {}, 0
    for m in _CORNER_TOK.finditer(cell.replace("=", "").replace("*", "")):
        grp = [int(x) for x in (m.group(1) or m.group(2)).split(",") if x]
        for k in grp:
            out[k] = i + (len(grp) + 1) / 2
        i += len(grp)
    return out


def _fill_from_alternates(page: dict, horses: list):
    """結果の翌朝のページは、表に『通過順位』と『人気』が入らないことがある。人気はオッズの低い順で、通過順位は『コーナー』の表の最後の行から補う。"""
    if all(h["pop"] is None for h in horses) and all(h.get("odds") for h in horses):
        rank = {h["no"]: i + 1 for i, h in enumerate(sorted(horses, key=lambda h: h["odds"]))}
        for h in horses:
            h["pop"] = rank[h["no"]]
    if any(h["pos"] for h in horses):
        return
    for tb in page.get("tables") or []:
        if tb and tb[0][:2] == ["コーナー", "通過順位"] and len(tb) > 1:
            order = corner_order(tb[-1][1])
            if len(order) >= len(horses) - 1:
                for h in horses:
                    if h["no"] in order:
                        h["pos"] = [order[h["no"]]]
            return


def clsgrp(c: str) -> str:
    for k in ("新馬", "未勝利", "1勝", "2勝", "3勝", "オープン", "G1", "G2", "G3", "リステッド", "L"):
        if k in c:
            return k
    return "他"


def agegrp(c: str) -> str:
    m = re.match(r"(\d歳以上|\d歳)", c)
    return m.group(1) if m else "他"


def parse_result_page(page: dict, code: str, date: str):
    """race_crawl.dump_page の形（text・tables）→ 1レースの辞書。読めない・障害・未確定なら None。"""
    txt = page.get("text") or ""
    m = _HEAD_RE.search(txt) or _HURDLE_RE.search(txt)
    if not m:
        return None
    kai, venue, day, _hh, _mm, name, surf, dist, _wx, going, cls = m.groups()
    table = None
    for t in page.get("tables") or []:
        if t and t[0][:3] == ["着順", "枠番", "馬番"]:
            table = t
            break
    if not table:
        return None
    horses = []
    for row in table[1:]:
        if len(row) < 8:
            continue
        try:
            fin = int(row[0])
        except ValueError:
            continue
        pos = None
        mm = re.match(r"^([\d\-]+)\s+([\d.]+)$", row[5].strip())
        if mm:
            pos = [int(x) for x in mm.group(1).split("-") if x.isdigit()] or None
        tm = re.match(r"^(?:(\d+):)?(\d+\.\d)", row[4].strip())
        sec = (int(tm.group(1) or 0) * 60 + float(tm.group(2))) if tm else None
        pop = re.match(r"^(\d+)", row[7].strip())
        od = re.search(r"\(([\d.]+)\)", row[7])
        try:
            horses.append({"fin": fin, "no": int(row[2]), "pos": pos, "sec": sec, "pop": int(pop.group(1)) if pop else None,
                           "odds": float(od.group(1)) if od else None})
        except ValueError:
            continue
    if len(horses) < MIN_PARSE_FIELD:
        return None
    _fill_from_alternates(page, horses)
    return {"code": code, "date": date, "kai": int(kai), "venue": venue, "day": int(day), "surf": surf, "dist": int(dist),
            "going": going, "cls": cls, "name": name, "n": len(horses), "horses": horses,
            "hurdle": surf == "障害" or "障害" in cls or "障害" in name}


def _mean(x):
    return sum(x) / len(x)


def time_keys(r: dict):
    """勝ち時計の基準のキー。細かい順（競馬場・芝ダ・距離・クラス・年齢 → 年齢をまとめたもの）。"""
    base = (r["venue"], r["surf"], str(r["dist"]), clsgrp(r["cls"]))
    return ["|".join(base + (agegrp(r["cls"]),)), "|".join(base + ("*",))]


def time_key(r: dict) -> str:
    return time_keys(r)[0]


def usable(r: dict) -> bool:
    return (not r["hurdle"]) and r["surf"] in SURFACES and r["n"] >= MIN_USABLE_FIELD


def winner_time(r: dict):
    w = next((h for h in r["horses"] if h["fin"] == 1), None)
    return w["sec"] if w and w["sec"] else None


def _pop_bucket(p: float) -> int:
    return min(9, int(p * 10))


def horse_rows(r: dict):
    """人気・最終コーナー位置・馬番がそろった馬の (着順位置, 人気位置, 最終コーナー位置, 馬番位置)。すべて0〜1。"""
    n = r["n"]
    if n < 2:
        return []
    out = []
    for h in r["horses"]:
        if h["pop"] is None or not h["pos"]:
            continue
        out.append(((h["fin"] - 1) / (n - 1), (h["pop"] - 1) / (n - 1), (h["pos"][-1] - 1) / (n - 1), (h["no"] - 1) / (n - 1)))
    return out


def expected_finish_table(races) -> list:
    """人気（10区分）ごとの平均着順位置。人気どおりの着順をここで決める。"""
    bk = defaultdict(list)
    for r in races:
        for f, p, _x, _g in horse_rows(r):
            bk[_pop_bucket(p)].append(f)
    return [round(_mean(bk[i]), 5) if bk[i] else 0.5 for i in range(10)]


def race_front_outer(r: dict, ef: list):
    """人気より前の馬が好走したか（front、＋ほど前残り）、人気より外の馬が好走したか（outer、＋ほど外有利）。"""
    rows = horse_rows(r)
    if len(rows) < MIN_FIELD:
        return None
    res = [(f - ef[_pop_bucket(p)], x, g) for f, p, x, g in rows]
    mx = _mean([x for _, x, _ in res])
    mg = _mean([g for _, _, g in res])
    sx = math.sqrt(_mean([(x - mx) ** 2 for _, x, _ in res]))
    sg = math.sqrt(_mean([(g - mg) ** 2 for _, _, g in res]))
    if not sx or not sg:
        return None
    # e＝着順位置−人気から期待される着順位置（小さいほど人気より好走）。x・g は小さいほど前・内。
    # 前の馬ほど好走 → e と x が同じ向きに動く（共分散＋）→ front＋（前残り）。外の馬ほど好走 → 共分散−  → outer＋（外有利）。
    return {"front": _mean([e * (x - mx) for e, x, _ in res]) / sx, "outer": -_mean([e * (g - mg) for e, _, g in res]) / sg}


def race_speed(r: dict, tbase: dict):
    """勝ち時計が、同じ競馬場・芝ダ・距離・クラスの平均より何％速いか（＋ほど高速）。"""
    t = winner_time(r)
    b = next((tbase[k] for k in time_keys(r) if k in tbase), None)
    if not t or not b:
        return None
    return -(t - b["t"]) / b["t"] * 100


def day_scores(races, base: dict):
    """races（同じ日・同じ競馬場）→ {芝/ダート: {...}}。基準 base は build_baselines の出力。"""
    out = {}
    for surf in SURFACES:
        rs = [r for r in races if usable(r) and r["surf"] == surf]
        if len(rs) < MIN_DAY_RACES:
            continue
        sp = [v for v in (race_speed(r, base["time"]) for r in rs) if v is not None]
        fo = [(r, race_front_outer(r, base["ef"])) for r in rs]
        fo = [(r, s) for r, s in fo if s]
        fr = [s["front"] for r, s in fo if surf == "ダート" or r["dist"] >= TURF_FRONT_MIN_DIST]
        ou = [s["outer"] for _, s in fo]
        sd = base["sd"][surf]
        mu = (base.get("mean") or {}).get(surf, {})
        cell = {"n_races": len(rs), "going": dict(sorted(_count([r["going"] for r in rs]).items()))}
        for key, vals in (("speed", sp), ("front", fr), ("outer", ou)):
            if len(vals) >= MIN_DAY_RACES:
                score = _mean(vals)
                z = round((score - mu.get(key, 0.0)) / sd[key], 2) if sd.get(key) else None   # 0＝ふだんどおり
                cell[key] = {"score": round(score, 4), "z": z, "n": len(vals)}
        out["turf" if surf == "芝" else "dirt"] = cell
    return out


def _count(xs):
    d = defaultdict(int)
    for x in xs:
        d[x] += 1
    return d


def label(key: str, z):
    """z（その日の傾向が、ふだんのばらつきの何倍か）→ 平易な言葉。±0.5未満は『ふつう』。"""
    if z is None or abs(z) < 0.5:
        return "ふつう"
    strong = abs(z) >= 1.0
    pos = z > 0
    names = {"speed": ("高速", "タフ"), "front": ("前残り", "差し有利"), "outer": ("外が有利", "内が有利")}[key]
    return ("かなり" if strong else "やや") + (names[0] if pos else names[1])


def build_baselines(races, built_from=None) -> dict:
    """過去のレースから基準を作る：人気ごとの平均着順位置・勝ち時計の平均・開催日ごとの傾向のばらつき（SD）。"""
    rs = [r for r in races if usable(r)]
    ef = expected_finish_table(rs)
    g = defaultdict(list)
    for r in rs:
        t = winner_time(r)
        if t:
            for k in time_keys(r):
                g[k].append(t)
    tbase = {k: {"t": round(_mean(v), 3), "n": len(v)} for k, v in g.items() if len(v) >= MIN_BASE_N}
    base = {"ef": ef, "time": tbase, "mean": {s: {} for s in SURFACES}, "sd": {s: {} for s in SURFACES}}
    days = defaultdict(list)
    for r in rs:
        days[(r["date"], r["venue"])].append(r)
    vals = {s: {"speed": [], "front": [], "outer": []} for s in SURFACES}
    # ばらつきの測定には z を使わない（SDがまだ無い）ので、score だけを集める
    tmp = {"ef": ef, "time": tbase, "sd": {s: {"speed": 1, "front": 1, "outer": 1} for s in SURFACES}}
    for (_d, _v), drs in days.items():
        ds = day_scores(drs, tmp)
        for key, surf in (("turf", "芝"), ("dirt", "ダート")):
            for m in ("speed", "front", "outer"):
                if key in ds and m in ds[key]:
                    vals[surf][m].append(ds[key][m]["score"])
    for s in SURFACES:
        for m, v in vals[s].items():
            if len(v) >= 30:
                mu = _mean(v)
                base["mean"][s][m] = round(mu, 4)
                base["sd"][s][m] = round(math.sqrt(_mean([(a - mu) ** 2 for a in v])), 4)
    base["schema"] = "baba_bias_baselines_v1"
    base["source"] = {"races": len(rs), **(built_from or {})}
    return base
