#!/usr/bin/env python3
"""Fetch raw, price-blind race data for the JRA main race (11R) so Claude can evaluate it independently.

Reads only public JRA pages (low rate, 2.5 s). The JRA card shows the current win odds and popularity
next to each horse; those are REMOVED here (price-blind). Nothing from ChatGPT's flow is used.
Output: claude_track/inputs/<date>-<venue_code>-11/<captured_utc>.json  (never overwritten; newest file is used)
"""
from __future__ import annotations

import argparse, gzip, hashlib, json, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

BASE = "https://www.jra.go.jp"
UA = "keiba-notes claude-track research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
JST = timezone(timedelta(hours=9))
VENUES = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京", "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}
CNAME_RE = re.compile(r"""['"](pw01[a-z]{3}[0-9A-Za-z]*/[0-9A-F]{2})['"]""")
DDE_RE = re.compile(r"pw01dde(\d{2})(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})(\d{8})/[0-9A-F]{2}")
ODDS_RE = re.compile(r"\d+(?:\.\d+)?\s*\(\s*\d+\s*番人気\s*\)")
BODY_RE = re.compile(r"(\d{3})kg\s*\(\s*([+\-±]?\d+)\s*\)")
CORNER_RE = re.compile(r"kg ((?:\d{1,2} ){1,4})3F")


def text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp932", errors="replace")


def past_run(cell) -> dict:
    t = text(cell)
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", t)
    d = re.search(r"(\d{3,4})(芝|ダ)", t)
    fin = re.search(r"(\d+)\s*着\s*(\d+)\s*頭", t)
    corners = CORNER_RE.search(t)
    going = re.search(r"\d{3,4}(?:芝|ダ)\s*\d+:\d+\.\d+\s*(良|稍重|重|不良)", t)
    return {"date": "%04d-%02d-%02d" % tuple(map(int, m.groups())) if m else None,
            "distance_m": int(d.group(1)) if d else None,
            "surface": ("芝" if d.group(2) == "芝" else "ダート") if d else None,
            "finish": int(fin.group(1)) if fin else None, "field_size": int(fin.group(2)) if fin else None,
            "going": going.group(1) if going else None,
            "passing_positions": [int(x) for x in corners.group(1).split()] if corners else [],
            "excerpt": t}


def parse_card(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    h1 = " ".join(text(x) for x in soup.select("h1"))
    head = soup.select_one(".race_header")
    if not head:
        raise ValueError("race header not found")
    ht = text(head)
    date = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", ht)
    tm = re.search(r"発走時刻：\s*(\d{1,2})時(\d{1,2})分", ht)
    course = head.select_one(".cell.course")
    dist = re.search(r"([\d,]+)\s*メートル", text(course)) if course else None
    detail = re.search(r"（(芝|ダート)[・\s]*([^）]*)）", text(course)) if course else None
    rnum = re.search(r"(\d+)レース", " ".join(img.get("alt", "") for img in head.select(".race_number img")))
    if not (date and tm and dist and detail and rnum):
        raise ValueError("incomplete race header")
    y, mo, d = map(int, date.groups())
    baba = [text(x) for x in soup.select(".baba")]
    horses = []
    table = soup.select_one("table")
    for tr in table.select("tr"):
        no, horse, jockey = tr.select_one("td.num"), tr.select_one("td.horse"), tr.select_one("td.jockey")
        if not (no and horse and jockey):
            continue
        ht_ = text(horse)
        name = ht_.split(" ")[0]
        body = BODY_RE.search(ht_)
        clean = ODDS_RE.sub("", ht_)           # price-blind: drop current win odds and popularity
        sire = re.search(r"父：\s*(\S+)", clean); dam = re.search(r"母：\s*(\S+)", clean)
        damsire = re.search(r"母の父：\s*([^)）]+)", clean)
        jt = text(jockey)
        sexage = re.search(r"([牡牝セ])\s*(\d+)", jt); wt = re.search(r"(\d{2}(?:\.\d)?)\s*kg", jt)
        jname = re.sub(r"^.*?kg\s*", "", jt)
        waku = tr.select_one("td.waku")
        horses.append({"number": int(text(no)), "frame": int(text(waku)) if waku and text(waku).isdigit() else None,
                       "name": name, "sex": sexage.group(1) if sexage else None, "age": int(sexage.group(2)) if sexage else None,
                       "weight_kg": float(wt.group(1)) if wt else None, "jockey": jname or None,
                       "body_weight_kg": int(body.group(1)) if body else None,
                       "body_weight_change": body.group(2) if body else None,
                       "sire": sire.group(1) if sire else None, "dam": dam.group(1) if dam else None,
                       "dam_sire": damsire.group(1).strip() if damsire else None,
                       "past": [past_run(c) for c in tr.select("td.past")]})
    if len(horses) < 5:
        raise ValueError("too few horses parsed")
    cat = head.select_one(".cell.category"); cls = head.select_one(".cell.class"); wgt = head.select_one(".cell.weight")
    return {"race_name": text(head.select_one(".race_name")), "date": f"{y:04d}-{mo:02d}-{d:02d}",
            "start_at": f"{y:04d}-{mo:02d}-{d:02d}T{int(tm.group(1)):02d}:{int(tm.group(2)):02d}:00+09:00",
            "race_no": int(rnum.group(1)), "surface": detail.group(1), "distance_m": int(dist.group(1).replace(",", "")),
            "course_detail": detail.group(2).strip(), "age_condition": text(cat) if cat else None,
            "class": text(cls) if cls else None, "weight_rule": text(wgt) if wgt else None,
            "meeting": re.search(r"\d+回\S+\d+日", ht).group(0) if re.search(r"\d+回\S+\d+日", ht) else None,
            "going_cells": baba, "field_size": len(horses), "horses": sorted(horses, key=lambda h: h["number"])}


class Client:
    def __init__(self, delay=2.5):
        import requests
        self.s = requests.Session(); self.s.headers["User-Agent"] = UA; self.delay = delay

    def post(self, cname):
        time.sleep(self.delay)
        r = self.s.post(BASE + "/JRADB/accessD.html", data={"cname": cname}, timeout=60)
        r.raise_for_status()
        return r.content


def run(dates: list[str], out_root: Path, delay: float) -> int:
    c = Client(delay)
    dli = decode(c.post("pw01dli00/F3"))
    drl = sorted({cn for cn in CNAME_RE.findall(dli) if cn.startswith("pw01drl") and any(cn[-11:-3] == d.replace("-", "") for d in dates)})
    written, done = 0, set()
    for cn in drl:
        page = decode(c.post(cn))
        for m in DDE_RE.finditer(page):
            if m.group(6) != "11" or m.group(7) not in {d.replace("-", "") for d in dates} or m.group(0) in done:
                continue
            done.add(m.group(0))
            raw = c.post(m.group(0))
            card = parse_card(decode(raw))
            now = datetime.now(JST)
            if now.isoformat() >= card["start_at"]:
                print("skip (already started)", card["race_name"]); continue
            vcode = m.group(2)
            rid = f"{card['date']}-{vcode}-11"
            doc = {"schema_version": 1, "race_id": rid, "venue": VENUES[vcode], "venue_code": vcode,
                   "source": "JRA official race card (出馬表)", "source_cname": m.group(0),
                   "source_html_sha256": hashlib.sha256(raw).hexdigest(), "captured_at": now.isoformat(timespec="seconds"),
                   "price_blind": True, "note": "現在の単勝オッズ・人気は除去済み。ChatGPTの評価は含まない。", **card}
            d = out_root / rid
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            written += 1
            print("saved", rid, card["race_name"], card["field_size"], "horses")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append", help="YYYY-MM-DD (default: today and tomorrow, JST)")
    ap.add_argument("--out", default="claude_track/inputs")
    ap.add_argument("--delay", type=float, default=2.5)
    a = ap.parse_args()
    today = datetime.now(JST).date()
    dates = a.date or [today.isoformat(), (today + timedelta(days=1)).isoformat()]
    n = run(dates, Path(a.out), a.delay)
    print("done", n)
    if n == 0:
        print("no race card saved (not published yet, or no main race on these dates)")


if __name__ == "__main__":
    main()
