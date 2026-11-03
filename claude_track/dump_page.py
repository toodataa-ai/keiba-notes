"""Probe only: print the table structure of a public page (nothing saved)."""
import sys, re, requests
from bs4 import BeautifulSoup
s = requests.Session(); s.headers["User-Agent"] = "keiba-notes claude-track research/1.0 (low rate, research only)"
def show(url, links=False):
    r = s.get(url, timeout=30); print("URL", url, r.status_code, len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    for i, t in enumerate(soup.select("table")[:6]):
        print(f"--- table {i} classes={t.get('class')}")
        for tr in t.select("tr")[:6]:
            print(" | ".join(re.sub(r"\s+", " ", c.get_text(" ", strip=True))[:70] for c in tr.find_all(["th", "td"], recursive=False)))
    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    for kw in ("通算", "戦", "成績"):
        for m in list(re.finditer(kw, body))[:3]:
            print("KW", kw, body[max(0, m.start()-40):m.start()+100])
    return soup
for url in sys.argv[1:]:
    soup = show(url)
    hl = [a.get("href") for a in soup.select("a[href*='/keiba/directory/horse/']")][:3]
    print("HORSE LINKS", hl)
    if hl:
        h = hl[0] if hl[0].startswith("http") else "https://sports.yahoo.co.jp" + hl[0]
        show(h)
