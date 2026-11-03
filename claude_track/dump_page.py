"""Probe only: print the table structure of a public page (nothing saved)."""
import sys, re, requests
from bs4 import BeautifulSoup
s = requests.Session(); s.headers["User-Agent"] = "keiba-notes claude-track research/1.0 (low rate, research only)"
for url in sys.argv[1:]:
    r = s.get(url, timeout=30); print("URL", url, r.status_code, len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    for i, t in enumerate(soup.select("table")):
        print(f"--- table {i} classes={t.get('class')}")
        for tr in t.select("tr")[:6]:
            print(" | ".join(re.sub(r"\s+", " ", c.get_text(" ", strip=True))[:70] for c in tr.find_all(["th", "td"], recursive=False)))
    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)); print("BODY", body[:500])
