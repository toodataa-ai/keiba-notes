#!/usr/bin/env python3
"""Claude's own official-result capture (no ChatGPT files used).

For each saved race card (claude_track/inputs/<race_id>/*.json) whose race has finished, reads the public Sportnavi
result page (着順 + 払戻金, which mirrors the JRA official result) and saves claude_track/results/<race_id>.json in the
same shape score_claude.py reads. Never overwrites. Saves only when the 払戻 table is present (= result is confirmed).
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
UA = "keiba-notes claude-track research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
RESULT_URL = "https://sports.yahoo.co.jp/keiba/race/result/{code}"
BET_NAMES = {"単勝": "単勝", "複勝": "複勝", "枠連": "枠連", "馬連": "馬連", "ワイド": "ワイド", "馬単": "馬単", "3連複": "三連複", "3連単": "三連単", "三連複": "三連複", "三連単": "三連単"}
MIN_AFTER_START = timedelta(minutes=25)


def _text(x) -> str:
    return re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()


def yen(v: str):
    m = re.fullmatch(r"([\d,]+)円", v.strip())
    return int(m.group(1).replace(",", "")) if m else None


def parse_result(soup) -> dict:
    """-> {finish_order, finish_top3, payouts, going, weather}. Raises ValueError when the page is incomplete."""
    tables = soup.select("table")
    pay: dict = {}
    order_rows = []
    for t in tables:
        rows = [[_text(c) for c in tr.find_all(["th", "td"], recursive=False)] for tr in t.select("tr")]
        if not rows:
            continue
        head = rows[0]
        if "払戻金" in head:
            cur = None
            for r in rows[1:]:
                if len(r) >= 4 and r[0] in BET_NAMES:
                    cur = BET_NAMES[r[0]]; combo, amt = r[1], r[2]
                elif len(r) >= 3 and cur and yen(r[1]) is not None:
                    combo, amt = r[0], r[1]
                else:
                    continue
                v = yen(amt)
                if v is not None:
                    pay.setdefault(cur, {})[combo] = v
        elif head[:3] == ["着順", "枠番", "馬番"]:
            order_rows = rows[1:]
    order, top3 = [], []
    for r in order_rows:
        if len(r) >= 4 and r[0].isdigit() and r[2].isdigit():
            order.append(int(r[2]))
            if int(r[0]) <= 3:
                top3.append({"pos": int(r[0]), "no": int(r[2]), "horse": re.sub(r"\s+(牡|牝|セ).*$", "", r[3])})
    if not order:
        raise ValueError("no finishing order")
    if "単勝" not in pay or "三連単" not in pay:
        raise ValueError("payout table incomplete (result not confirmed yet?)")
    body = _text(soup)
    g = re.search(r"馬場：\s*(\S+)", body); w = re.search(r"天気：\s*(\S+)", body)
    return {"finish_order": order, "finish_top3": top3, "payouts": pay,
            "going": g.group(1) if g else None, "weather": w.group(1) if w else None}


def race_code(cname: str) -> str:
    from claude_track.fetch_odds import race_code as rc
    return rc(cname)


def build_doc(card: dict, code: str, parsed: dict, digest: str, now: datetime) -> dict:
    return {"schema_version": 1, "race_id": card["race_id"], "date": card["date"], "venue": card["venue"],
            "race_name": card.get("race_name"), "source": "Sportnavi result page (mirrors JRA official result and payouts)",
            "official_url": RESULT_URL.format(code=code), "page_sha256": digest,
            "captured_at": now.isoformat(timespec="seconds"), "scheduled_start_at": card["start_at"],
            "official_going": parsed["going"], "weather": parsed["weather"],
            "finish_order": parsed["finish_order"], "finish_top3": parsed["finish_top3"],
            "official_payouts_yen_per_100": parsed["payouts"]}


def latest_cards(inputs_root: Path, dates: list[str]):
    for d in sorted(inputs_root.glob("*-11")):
        if not any(d.name.startswith(x) for x in dates):
            continue
        files = sorted(d.glob("*.json"))
        if files:
            yield json.loads(files[-1].read_text(encoding="utf-8"))


def main():
    import requests
    from bs4 import BeautifulSoup
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append", help="YYYY-MM-DD (default: today and yesterday JST)")
    ap.add_argument("--inputs", default="claude_track/inputs")
    ap.add_argument("--out", default="claude_track/results")
    ap.add_argument("--probe-code", help="test only: parse any past race (nothing saved)")
    a = ap.parse_args()
    s = requests.Session(); s.headers["User-Agent"] = UA
    now = datetime.now(JST)
    if a.probe_code:
        r = s.get(RESULT_URL.format(code=a.probe_code), timeout=30); r.raise_for_status()
        p = parse_result(BeautifulSoup(r.content, "html.parser"))
        print(json.dumps(p, ensure_ascii=False)); return
    dates = a.date or [now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for card in latest_cards(Path(a.inputs), dates):
        dest = out / f"{card['race_id']}.json"
        if dest.exists():
            print("have", card["race_id"]); continue
        if now < datetime.fromisoformat(card["start_at"]) + MIN_AFTER_START:
            print("too early", card["race_id"]); continue
        try:
            code = race_code(card["source_cname"])
            r = s.get(RESULT_URL.format(code=code), timeout=30); r.raise_for_status()
            parsed = parse_result(BeautifulSoup(r.content, "html.parser"))
        except Exception as e:
            print("NOT YET/FAILED", card["race_id"], e, file=sys.stderr); failed += 1; continue
        doc = build_doc(card, code, parsed, hashlib.sha256(r.content).hexdigest(), now)
        dest.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("saved", card["race_id"], doc["finish_order"][:3])
    sys.exit(0)


if __name__ == "__main__":
    main()
