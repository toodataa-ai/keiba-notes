#!/usr/bin/env python3
"""Claude's own pre-post odds capture (no ChatGPT files used).

Reads the public Sportnavi odds pages (単勝 tfw / 馬連 ur / 馬単 ut / ワイド wide / 三連複 sf) for the
main race (11R) of each race card saved by fetch_race_inputs.py, and saves them as
claude_track/odds/<race_id>/<captured_utc>.json. Never overwrites; never writes after the post time.
The Sportnavi race code is YY + venue(2) + kai(2) + nichi(2) + race(2), built from the JRA card's cname.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
UA = "keiba-notes claude-track research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
KINDS = {"tfw": "単勝", "ur": "馬連", "ut": "馬単", "wide": "ワイド", "sf": "三連複"}
ODDS_URL = "https://sports.yahoo.co.jp/keiba/race/odds/{kind}/{code}?ninki=0"
CNAME_RE = re.compile(r"pw01dde(\d{2})(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})(\d{8})")


def race_code(cname: str) -> str:
    m = CNAME_RE.search(cname or "")
    if not m:
        raise ValueError("cannot read race code from cname: %r" % cname)
    _, venue, year, kai, nichi, race, _d = m.groups()
    return year[2:] + venue + kai + nichi + race


def _text(x) -> str:
    return re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()


def odds_value(value: str):
    raw = value.strip().replace(",", "")
    if any(x in raw for x in ("****", "---", "取消", "除外", "99999.9")):
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?", raw)
    if not m:
        return None
    a = float(m.group(1)); b = float(m.group(2)) if m.group(2) else None
    if a <= 1:
        return None
    return [a, b] if b and b >= a else a


def _rows(table):
    for tr in table.select("tr"):
        yield [_text(c) for c in tr.find_all(["th", "td"], recursive=False)]


def parse_odds(kind: str, soup) -> dict:
    res = {}
    tables = soup.select("table")
    if kind == "tfw":
        if len(tables) < 1:
            return res
        for row in list(_rows(tables[0]))[1:]:
            if len(row) < 4:
                continue
            try:
                no = int(row[1])
            except ValueError:
                continue
            v = odds_value(row[3])
            if v is not None:
                res[("単勝", (no,))] = v
    elif kind in ("ur", "wide", "ut", "sf"):
        name = KINDS[kind]
        for t in tables:
            rr = list(_rows(t))
            if not rr:
                continue
            h = [int(n) for n in re.findall(r"\d+", rr[0][0])]
            if len(h) != (2 if kind == "sf" else 1):
                continue
            for row in rr[1:]:
                if len(row) < 2:
                    continue
                try:
                    horse = int(row[0])
                except ValueError:
                    continue
                sel = h + [horse]
                if kind in ("ur", "wide", "sf"):
                    sel.sort()
                v = odds_value(row[1])
                if v is not None:
                    res[(name, tuple(sel))] = v
    return res


def capture_race(doc: dict, session, now: datetime, delay: float, probe: bool = False) -> dict | None:
    from bs4 import BeautifulSoup
    if not probe and now.isoformat() >= doc["start_at"]:
        print("skip (post time passed)", doc["race_id"]); return None
    code = race_code(doc["source_cname"])
    entries, sources = [], {}
    for kind in KINDS:
        url = ODDS_URL.format(kind=kind, code=code)
        time.sleep(delay)
        r = session.get(url, timeout=30); r.raise_for_status()
        if len(r.content) < 1500:
            raise RuntimeError("empty page " + url)
        got = parse_odds(kind, BeautifulSoup(r.content, "html.parser"))
        if not got:
            raise RuntimeError("no odds parsed from " + url)
        sources[kind] = {"url": url, "sha256": hashlib.sha256(r.content).hexdigest(), "count": len(got)}
        entries += [{"type": t, "selection": list(sel), "market_odds": v} for (t, sel), v in sorted(got.items())]
    done = datetime.now(JST)
    if not probe and done.isoformat() >= doc["start_at"]:
        print("skip (post time passed during capture)", doc["race_id"]); return None
    return {"schema_version": 1, "race_id": doc["race_id"], "race_code": code, "start_at": doc["start_at"],
            "captured_at": done.isoformat(timespec="seconds"), "source": "Sportnavi public odds pages",
            "sources": sources, "entries": entries}


def latest_cards(inputs_root: Path, dates: list[str]):
    for d in sorted(inputs_root.glob("*-11")):
        if not any(d.name.startswith(x) for x in dates):
            continue
        files = sorted(d.glob("*.json"))
        if files:
            yield json.loads(files[-1].read_text(encoding="utf-8"))


def main():
    import requests
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append", help="YYYY-MM-DD (default: today JST)")
    ap.add_argument("--inputs", default="claude_track/inputs")
    ap.add_argument("--out", default="claude_track/odds")
    ap.add_argument("--delay", type=float, default=2.5)
    ap.add_argument("--probe", action="store_true", help="test only: ignore the post-time check and write nothing")
    a = ap.parse_args()
    dates = a.date or [datetime.now(JST).date().isoformat()]
    s = requests.Session(); s.headers["User-Agent"] = UA
    n = 0
    for doc in latest_cards(Path(a.inputs), dates):
        try:
            out = capture_race(doc, s, datetime.now(JST), a.delay, a.probe)
        except Exception as e:  # one race failing must not stop the others
            print("FAILED", doc.get("race_id"), e, file=sys.stderr); continue
        if not out:
            continue
        if a.probe:
            print("PROBE ok", doc["race_id"], {k: v["count"] for k, v in out["sources"].items()}); continue
        d = Path(a.out) / doc["race_id"]; d.mkdir(parents=True, exist_ok=True)
        p = d / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
        if p.exists():
            continue
        p.write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8"); n += 1
        print("saved", p, len(out["entries"]), "prices")
    print("done", n)


if __name__ == "__main__":
    main()
