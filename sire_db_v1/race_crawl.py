#!/usr/bin/env python3
"""レース単位の情報を、見えるものは全部取って保存する（研究用・予想には使わない）。
各レースで Sportnavi の「結果」と「出馬表」のページを取り、**表（全部）と文字（全部）をそのまま**保存する
（項目を決め打ちしない＝あとで必要になった項目を取り直さなくてよい）。リンク先（騎手・調教師・馬のID）も残す。
保存先は非公開リポジトリ（環境変数 SIRE_DATA_DIR）。公開リポジトリには置かない。
  data_v2/race_pages/<年>.jsonl  1レース1行  {code, date, fetched, pages:{result:{url,title,tables,text}, denma:{...}}}
  data_v2/race_pages_done.txt    取れたレースのコード（途中で止まっても続きから）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ["SIRE_DATA_DIR"]) if os.environ.get("SIRE_DATA_DIR") else ROOT / "sire_db_v1" / "data"
LABELS = ROOT / "baba_models_v2" / "going_labels"
UA = "keiba-notes research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
VENUE = {"札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
         "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10"}
PAGES = {"result": "https://sports.yahoo.co.jp/keiba/race/result/{code}",
         "denma": "https://sports.yahoo.co.jp/keiba/race/denma/{code}"}
GAP = 2.0
PARSE_V = 1


def _t(x) -> str:
    return re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()


def race_codes(years) -> list[tuple[str, str]]:
    out = []
    for y in years:
        p = LABELS / f"jra_going_{y}.csv"
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(encoding="utf-8")):
            v = VENUE.get(r["track"])
            if v:
                out.append((r["date"], f"{r['date'][2:4]}{v}{int(r['kai']):02d}{int(r['nichime']):02d}{int(r['race_no']):02d}"))
    out.sort(reverse=True)
    return out


def cell(c) -> str:
    """セルの文字。中のリンク（/keiba/directory/... など）は ⟨...⟩ で残す。"""
    s = _t(c)
    links = []
    for a in c.find_all("a", href=True):
        h = a["href"]
        if "/keiba/" in h and h not in links:
            links.append(h.split("?")[0])
    return s + "".join(f"⟨{h}⟩" for h in links)


def dump_page(soup, url: str) -> dict:
    """ページの表を全部（行×セル）と、見える文字を全部、そのまま取り出す。"""
    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()
    tables = []
    for t in soup.select("table"):
        rows = [[cell(c) for c in tr.find_all(["th", "td"], recursive=False)] for tr in t.select("tr")]
        rows = [r for r in rows if r]
        if rows:
            tables.append(rows)
    return {"url": url, "title": _t(soup.title) if soup.title else "", "tables": tables, "text": _t(soup)}


def main():
    import requests
    from bs4 import BeautifulSoup
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2026,2025,2024,2023,2022,2021,2020,2019,2018")
    ap.add_argument("--max-minutes", type=float, default=300)
    ap.add_argument("--max-races", type=int, default=0)
    ap.add_argument("--probe", default="", help="race code: fetch and print the structure only, save nothing")
    a = ap.parse_args()
    s = requests.Session(); s.headers["User-Agent"] = UA

    def get(u):
        for i in range(3):
            try:
                r = s.get(u, timeout=30); time.sleep(GAP)
                if r.status_code == 404:
                    return None
                r.raise_for_status(); return BeautifulSoup(r.text, "html.parser")
            except requests.RequestException as e:
                print("retry", u, e, file=sys.stderr); time.sleep(5 * (i + 1))
        return None

    def fetch(code):
        pages = {}
        for k, tpl in PAGES.items():
            u = tpl.format(code=code)
            soup = get(u)
            if soup is None:
                return None
            pages[k] = dump_page(soup, u)
        return pages

    if a.probe:
        pages = fetch(a.probe)
        for k, p in (pages or {}).items():
            print("=====", k, p["url"], "| title:", p["title"], "| text chars:", len(p["text"]), "| tables:", len(p["tables"]))
            for i, t in enumerate(p["tables"]):
                print(f"  table {i}: rows={len(t)} head={t[0][:8]}")
            for kw in ("ラップ", "ペース", "通過", "賞金", "コーナー", "天気", "馬場", "発走"):
                m = re.search(r".{0,40}" + kw + r".{0,80}", p["text"])
                print(f"  [{kw}]", m.group(0) if m else "-")
            print("  text head:", p["text"][:300])
        return

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "race_pages").mkdir(exist_ok=True)
    done_p = DATA / "race_pages_done.txt"
    done = set(done_p.read_text().split()) if done_p.exists() else set()
    todo = [(d, c) for d, c in race_codes(a.years.split(",")) if c not in done]
    print("race pages todo:", len(todo))
    t0 = time.time(); n = 0
    for d, code in todo:
        if (time.time() - t0) / 60 > a.max_minutes or (a.max_races and n >= a.max_races):
            break
        pages = fetch(code)
        if pages is None:
            continue                           # 取れなかったレースは done にしない（次回また試す）
        rec = {"code": code, "date": d, "fetched": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
               "parse_v": PARSE_V, "pages": pages}
        with (DATA / "race_pages" / f"{d[:4]}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        with done_p.open("a") as f:
            f.write(code + "\n")
        n += 1
        if n % 50 == 0:
            print(f"race pages {n} elapsed {(time.time()-t0)/60:.0f} min", flush=True)
    print(f"done: race pages +{n}, remaining races {len(todo) - n}")


if __name__ == "__main__":
    main()
