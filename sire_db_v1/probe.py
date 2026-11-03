#!/usr/bin/env python3
"""試験取得のみ（保存なし）: Sportnavi の馬のページに 生年月日・父・母・母父 が載るか、父のページはあるかを確認する。"""
import re, sys, time, requests
from bs4 import BeautifulSoup
UA = "keiba-notes research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
code = sys.argv[1]
s = requests.Session(); s.headers["User-Agent"] = UA
def get(u):
    r = s.get(u, timeout=30); print("GET", u, r.status_code, len(r.text)); time.sleep(2); return BeautifulSoup(r.text, "html.parser")
d = get(f"https://sports.yahoo.co.jp/keiba/race/denma/{code}")
links = [a["href"] for a in d.find_all("a", href=True) if "/keiba/directory/horse/" in a["href"]]
print("horse links:", len(links), links[:3])
h = get("https://sports.yahoo.co.jp" + links[0] if links[0].startswith("/") else links[0])
txt = re.sub(r"\s+", " ", h.get_text(" ", strip=True))
print("PROFILE TEXT:", txt[:1500])
print("directory links:", sorted({a["href"] for a in h.find_all("a", href=True) if "/keiba/directory/" in a["href"]})[:30])
for k in ("生年月日", "父", "母", "母の父", "調教師", "馬主"):
    print(k, "->", [m for m in re.findall(k + r"[^ ]* ?[^ ]+", txt)][:2])
# 父のページがあるか
sire = [a["href"] for a in h.find_all("a", href=True) if re.search(r"/keiba/directory/(sire|horse)/", a["href"])]
print("sire/horse links on page:", sire[:10])
