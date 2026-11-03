"""Probe only: print the text structure of a Sportnavi result page (nothing saved)."""
import sys, re, requests
from bs4 import BeautifulSoup
UA = "keiba-notes claude-track research/1.0 (low rate, research only)"
code = sys.argv[1]
s = requests.Session(); s.headers["User-Agent"] = UA
for url in (f"https://sports.yahoo.co.jp/keiba/race/result/{code}",):
    r = s.get(url, timeout=30); print("URL", url, r.status_code, len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    for i, t in enumerate(soup.select("table")):
        print(f"--- table {i} classes={t.get('class')}")
        for tr in t.select("tr")[:30]:
            print(" | ".join(re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"], recursive=False)))
    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    for kw in ("発走", "馬場", "天候", "払戻"):
        for m in list(re.finditer(kw, body))[:3]:
            print("KW", kw, body[max(0, m.start()-40):m.start()+80])
