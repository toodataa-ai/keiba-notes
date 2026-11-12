"""保存済みのレースのページ（非公開リポジトリ data_v2/race_pages）から、1頭1行の表を作る。
公開側の集計だけがこの表から作られる（馬名など1頭ごとの記録は公開しない）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

VENUE_BY_CODE = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
                 "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}
HEADER = re.compile(
    r"(\d+)回(\S+?)(\d+)日 (\d+):(\d+)発走 (.+?) (芝|ダート|障害)・?(右|左|直線)?(?:・(内|外|内2周|外2周|内外|外内))?\s*(\d+)m "
    r"天気： (\S+) 馬場： (\S+) (.+?) 本賞金")
PASS = re.compile(r"^(\d{1,2}(?:-\d{1,2})*)\s+(\d+\.\d)$")
ODDS = re.compile(r"^(\d+)\s*\(\s*([\d.]+)\s*\)$")


def klass(s: str) -> str:
    if "新馬" in s:
        return "新馬"
    if "未勝利" in s:
        return "未勝利"
    if re.search(r"1勝|500万", s):
        return "1勝"
    if re.search(r"2勝|1000万", s):
        return "2勝"
    if re.search(r"3勝|1600万", s):
        return "3勝"
    return "OP・重賞"


def time_sec(s: str):
    m = re.match(r"(\d+):(\d+\.\d)", s or "")
    return int(m.group(1)) * 60 + float(m.group(2)) if m else None


def link(cell: str, kind: str):
    m = re.search(rf"/keiba/directory/{kind}/(\d+)", cell)
    return m.group(1) if m else None


def strip_links(cell: str) -> str:
    return re.sub(r"⟨[^⟩]*⟩", "", cell).strip()


def parse_race(rec: dict):
    """1レース分の記録 -> (レース情報, [馬ごとの行])。読めなければ None"""
    res = rec["pages"]["result"]
    m = HEADER.search(res["text"])
    if not m:
        return None
    kai, _venue, nichi, hh, mm, name, surface, turn, inout, dist, weather, going, cls = m.groups()
    code = rec["code"]
    race = {
        "code": code, "date": rec["date"], "year": int(rec["date"][:4]),
        "venue": VENUE_BY_CODE.get(code[2:4]), "kai": int(kai), "nichi": int(nichi), "no": int(code[8:10]),
        "name": name, "surface": surface, "turn": turn, "inout": inout, "dist": int(dist),
        "weather": weather, "going": going, "klass": klass(cls), "hour": int(hh),
    }
    table = next((t for t in res["tables"] if t and t[0] and t[0][0] == "着順"), None)
    if table is None:
        return None
    head = table[0]

    def col(prefix):
        return next((i for i, h in enumerate(head) if h.startswith(prefix)), None)
    ci = {k: col(k) for k in ("着順", "枠番", "馬番", "馬名", "タイム", "通過順位", "騎手名", "人気", "調教師")}
    rows = []
    for r in table[1:]:
        if len(r) < len(head):
            continue
        fin_s = r[ci["着順"]].strip()
        finish = int(fin_s) if fin_s.isdigit() else None
        pas, last3 = None, None
        pm = PASS.match(strip_links(r[ci["通過順位"]])) if ci["通過順位"] is not None else None
        if pm:
            pas = [int(x) for x in pm.group(1).split("-")]
            last3 = float(pm.group(2))
        elif ci["通過順位"] is not None:
            m2 = re.search(r"(\d+\.\d)$", strip_links(r[ci["通過順位"]]))
            last3 = float(m2.group(1)) if m2 else None
        om = ODDS.match(strip_links(r[ci["人気"]])) if ci["人気"] is not None else None
        jc, tc = r[ci["騎手名"]], r[ci["調教師"]]
        jname = re.sub(r"\s*\d+(\.\d+)?$", "", strip_links(jc)).strip()
        wm = re.search(r"([牡牝せん騸])(\d+)/(\d+)\(([+-]?\d+)\)", r[ci["馬名"]])
        rows.append({
            "finish": finish, "frame": int(r[ci["枠番"]]) if r[ci["枠番"]].isdigit() else None,
            "no": int(r[ci["馬番"]]) if r[ci["馬番"]].isdigit() else None,
            "time": time_sec(r[ci["タイム"]]), "pass": pas, "last3": last3,
            "jockey": link(jc, "jockey"), "jockey_name": jname, "trainer": link(tc, "trainer"),
            "trainer_name": strip_links(tc),
            "pop": int(om.group(1)) if om else None, "odds": float(om.group(2)) if om else None,
            "sex": wm.group(1) if wm else None, "age": int(wm.group(2)) if wm else None,
            "horse": link(r[ci["馬名"]], "horse"),
            "weight": int(wm.group(3)) if wm else None, "wdiff": int(wm.group(4)) if wm else None,
        })
    race["n"] = len(rows)
    return race, rows


def iter_races(data_dir: Path, years=None):
    for p in sorted((Path(data_dir) / "race_pages").glob("*.jsonl")):
        if years and p.stem not in years:
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                out = parse_race(json.loads(line))
                if out:
                    yield out
