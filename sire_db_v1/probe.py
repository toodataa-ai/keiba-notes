#!/usr/bin/env python3
"""試験取得のみ（保存なし）: 馬のページの血統表と出走履歴表のHTML構造を確認する。"""
import re, sys, time, requests
from bs4 import BeautifulSoup
UA = "keiba-notes research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
s = requests.Session(); s.headers["User-Agent"] = UA
for hid in sys.argv[1:]:
    r = s.get(f"https://sports.yahoo.co.jp/keiba/directory/horse/{hid}/", timeout=30); time.sleep(2)
    soup = BeautifulSoup(r.text, "html.parser")
    print("=====", hid, r.status_code)
    for t in soup.select("table"):
        rows = t.select("tr"); head = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in rows[0].find_all(["th", "td"], recursive=False)] if rows else []
        if head[:2] == ["日付", "レース"]:
            print("HISTORY rows:", len(rows) - 1, "head:", head)
            print(str(rows[1])[:1500]); print(str(rows[-1])[:600])
    n = soup.find(string=re.compile("サンデーサイレンス|ディープインパクト|キングカメハメハ|ロードカナロア"))
    if n:
        t = n.find_parent("table")
        print("PEDIGREE table found:", bool(t)); print(str(t)[:4000] if t else str(n.parent.parent)[:3000])
    pager = [a.get_text(strip=True) for a in soup.find_all("a") if re.fullmatch(r"次へ|もっと見る|\d+", a.get_text(strip=True) or "")]
    print("pager-ish links:", pager[:15])
