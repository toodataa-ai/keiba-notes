#!/usr/bin/env python3
"""Probe: find this week's JRA race-card (出馬表) pages for the main races and save the raw HTML.

Research-only, low rate (2.5 s), robots.txt of www.jra.go.jp allows everything. Reads only public pages.
Nothing from ChatGPT's flow (no marks, no odds). Output goes to claude_track/inputs/probe/.
"""
import argparse, gzip, hashlib, json, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

BASE = "https://www.jra.go.jp"
UA = "keiba-notes claude-track research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
CNAME_RE = re.compile(r"""['"](pw01[a-z]{3}[0-9A-Za-z]*/[0-9A-F]{2})['"]""")
DDE_RE = re.compile(r"pw01dde(\d{2})(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})(\d{8})/[0-9A-F]{2}")
JST = timezone(timedelta(hours=9))


class C:
    def __init__(self, delay=2.5):
        self.s = requests.Session(); self.s.headers["User-Agent"] = UA; self.delay = delay; self.n = 0

    def post(self, path, cname):
        time.sleep(self.delay)
        r = self.s.post(BASE + path, data={"cname": cname}, timeout=60)
        self.n += 1
        r.encoding = "cp932" if "charset=Shift_JIS" in r.text[:2000] or r.apparent_encoding in ("SHIFT_JIS", "CP932") else r.encoding
        return r

    def get(self, url):
        time.sleep(self.delay)
        r = self.s.get(url, timeout=60); self.n += 1
        return r


def save(out: Path, name: str, raw: bytes):
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.html.gz").write_bytes(gzip.compress(raw))
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="claude_track/inputs/probe")
    ap.add_argument("--max-pages", type=int, default=40)
    a = ap.parse_args(); out = Path(a.out); c = C(); log = {"started_at": datetime.now(JST).isoformat(), "steps": []}
    seeds = [("/JRADB/accessD.html", "pw01dli00/F3")]
    seen, queue, found_dde = set(), list(seeds), {}
    top = c.get(BASE + "/keiba/")
    log["steps"].append({"top_status": top.status_code, "bytes": len(top.content)})
    save(out, "top_keiba", top.content)
    for cn in CNAME_RE.findall(top.text):
        if cn.startswith(("pw01dli", "pw01drl", "pw01dde")) and ("/JRADB/accessD.html", cn) not in queue:
            queue.append(("/JRADB/accessD.html", cn))
    while queue and len(seen) < a.max_pages:
        path, cn = queue.pop(0)
        if cn in seen:
            continue
        seen.add(cn)
        try:
            r = c.post(path, cn)
        except requests.RequestException as e:
            log["steps"].append({"cname": cn, "error": str(e)}); continue
        sha = save(out, "page_" + re.sub(r"[^0-9A-Za-z]", "_", cn), r.content)
        links = sorted(set(CNAME_RE.findall(r.text)))
        log["steps"].append({"cname": cn, "status": r.status_code, "bytes": len(r.content), "sha256": sha, "links": len(links)})
        for m in DDE_RE.finditer(r.text):
            found_dde[m.group(0)] = {"venue_code": m.group(2), "year": m.group(3), "kai": m.group(4), "nichi": m.group(5), "race_no": m.group(6), "date": m.group(7)}
        for l in links:
            if l.startswith(("pw01drl", "pw01dli", "pw01dde")) and l not in seen:
                queue.append(("/JRADB/accessD.html", l))
    log["race_cards_found"] = found_dde
    for cn, meta in sorted(found_dde.items()):
        if meta["race_no"] != "11" or cn in seen:
            continue
        seen.add(cn)
        r = c.post("/JRADB/accessD.html", cn)
        sha = save(out, "card_" + re.sub(r"[^0-9A-Za-z]", "_", cn), r.content)
        log["steps"].append({"card": cn, "status": r.status_code, "bytes": len(r.content), "sha256": sha})
    log["finished_at"] = datetime.now(JST).isoformat(); log["requests"] = c.n
    (out / "probe_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("probe done: pages", len(seen), "race cards found", len(found_dde))


if __name__ == "__main__":
    main()
