"""One-off probe: where does JRA publish the CURRENT (morning) going / moisture?  Saves raw HTML + link lists."""
import gzip, json, re, sys, time
from pathlib import Path
import requests
UA = {"User-Agent": "keiba-notes track-condition research/1.0"}
URLS = ["https://www.jra.go.jp/keiba/baba/", "https://www.jra.go.jp/keiba/baba/archive/",
        "https://www.jra.go.jp/keiba/baba/dirt/", "https://www.jra.go.jp/keiba/", "https://www.jra.go.jp/keiba/thisweek/",
        "https://www.jra.go.jp/JRADB/accessS.html"]
out = Path("baba_models_v2/probe"); out.mkdir(exist_ok=True)
log = []
for u in URLS:
    try:
        r = requests.get(u, headers=UA, timeout=30)
        html = r.content.decode("cp932", errors="replace")
        name = re.sub(r"\W+", "_", u)[-60:]
        (out / f"{name}.html.gz").write_bytes(gzip.compress(html.encode()))
        links = sorted(set(re.findall(r"""(?:href=["']|doAction\(['"][^'"]*['"],\s*['"])([^"')]+)""", html)))
        log.append({"url": u, "status": r.status_code, "len": len(html), "links": [l for l in links if re.search(r"baba|JRADB|moist|going|cushion|condition", l)][:80]})
    except Exception as e:
        log.append({"url": u, "error": str(e)})
    time.sleep(2.5)
(out / "probe_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(log, ensure_ascii=False, indent=1)[:6000])
