#!/usr/bin/env python3
"""その日（土曜など）の全レース（1R〜12R）の結果ページから、競馬場ごとの馬場傾向を数字にして保存する。Claudeの使用量は0。

入力：claude_track/inputs/<日付>-<競馬場コード>-11/*.json（その日の出馬表。競馬場とレースコードの元）／baselines_v1.json
出力：docs/data/baba_bias/<日付>.json（集計だけ）と、日付の一覧 index.json。馬名・1頭ずつの記録・ページの中身は保存しない。
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
import time

from baba_bias_v1 import core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = dt.timezone(dt.timedelta(hours=9))
UA = "keiba-notes baba-bias research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
RESULT_URL = "https://sports.yahoo.co.jp/keiba/race/result/{code}"
GAP = 2.0


def day_bases(date, inputs):
    """{競馬場名: レースコードの頭（年2桁＋場＋回＋日目、Rの2桁を除く）}"""
    from claude_track.fetch_odds import race_code
    out = {}
    for d in sorted(glob.glob(os.path.join(inputs, f"{date}-??-11"))):
        files = sorted(glob.glob(os.path.join(d, "*.json")))
        if not files:
            continue
        with open(files[0], encoding="utf-8") as f:
            card = json.load(f)
        out[card["venue"]] = race_code(card["source_cname"])[:-2]
    return out


def assemble(date, venue_races, base, now=None, min_read=11):
    """{競馬場: [race,...]} → 保存する辞書。min_read（12レース中11）未満しか読めなかった競馬場（結果が途中）は出さない。"""
    now = now or dt.datetime.now(JST)
    venues = {}
    for v, rs in venue_races.items():
        if len(rs) < min_read:
            continue
        sc = core.day_scores(rs, base)
        if not sc:
            continue
        for surf in sc.values():
            for m in ("speed", "front", "outer"):
                if m in surf:
                    surf[m]["label"] = core.label(m, surf[m]["z"])
        venues[v] = {"meeting": f"{rs[0]['kai']}回{v}{rs[0]['day']}日", "surfaces": sc, "races_read": len(rs)}
    return {"schema": "baba_bias_day_v1", "date": date, "generated_at": now.isoformat(timespec="seconds"),
            "baselines": base.get("source"), "venues": venues,
            "note": "speed＝勝ち時計が基準より何％速いか／front＝人気より前の馬が好走／outer＝人気より外の馬が好走。z＝ふだんのばらつきの何倍か。"}


def update_index(out_dir, date):
    p = os.path.join(out_dir, "index.json")
    idx = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"dates": []}
    idx["dates"] = sorted(set(idx["dates"]) | {date})[-60:]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
        f.write("\n")


def pending_dates(inputs, out_dir, today, days=3):
    """出馬表があり、まだ傾向を保存していない開催日（直近 days 日・古い順）。"""
    dates = sorted({os.path.basename(p)[:10] for p in glob.glob(os.path.join(inputs, "????-??-??-??-11"))})
    lo = (today - dt.timedelta(days=days)).isoformat()
    return [d for d in dates if lo <= d <= today.isoformat() and not os.path.exists(os.path.join(out_dir, f"{d}.json"))]


def process_date(session, date, base, inputs, out_dir):
    from bs4 import BeautifulSoup
    import requests
    from sire_db_v1.race_crawl import dump_page
    bases = day_bases(date, inputs)
    if not bases:
        print(f"{date}: 出馬表が無い（開催なし？）", file=sys.stderr)
        return False
    venue_races = {}
    for v, b in bases.items():
        rs = []
        for r in range(1, 13):
            code = f"{b}{r:02d}"
            url = RESULT_URL.format(code=code)
            soup = None
            for i in range(3):
                try:
                    resp = session.get(url, timeout=30)
                    time.sleep(GAP)
                    if resp.status_code == 404:
                        break
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    break
                except requests.RequestException as e:
                    print("retry", url, e, file=sys.stderr)
                    time.sleep(5 * (i + 1))
            if soup is None:
                continue
            race = core.parse_result_page(dump_page(soup, url), code, date)
            if race:
                rs.append(race)
        venue_races[v] = rs
        print(date, v, "読めたレース", len(rs), "/ 12")
    doc = assemble(date, venue_races, base)
    if not doc["venues"]:
        print(f"{date}: 結果がそろった競馬場がありません（結果が未確定？）。保存しません", file=sys.stderr)
        return False
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{date}.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    update_index(out_dir, date)
    print(json.dumps({v: {k: {m: (x[m]["score"], x[m]["label"]) for m in ("speed", "front", "outer") if m in x} for k, x in d["surfaces"].items()} for v, d in doc["venues"].items()}, ensure_ascii=False))
    return True


def main(argv=None):
    import requests
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD（日付を指定して1日だけ処理）")
    ap.add_argument("--auto", action="store_true", help="出馬表があり、まだ保存していない直近3日を自動で処理")
    ap.add_argument("--inputs", default=os.path.join(ROOT, "claude_track", "inputs"))
    ap.add_argument("--baselines", default=os.path.join(ROOT, "docs", "data", "baba_bias", "baselines_v1.json"))
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "docs", "data", "baba_bias"))
    a = ap.parse_args(argv)
    today = dt.datetime.now(JST).date()
    if a.date:
        dates = [a.date]
    elif a.auto:
        dates = pending_dates(a.inputs, a.out_dir, today)
    else:
        dates = [(today - dt.timedelta(days=1)).isoformat()]
    if not dates:
        print("処理する開催日はありません")
        return 0
    base = json.load(open(a.baselines, encoding="utf-8"))
    s = requests.Session()
    s.headers["User-Agent"] = UA
    ok = [process_date(s, d, base, a.inputs, a.out_dir) for d in dates]
    return 0 if (a.auto or all(ok)) else 1


if __name__ == "__main__":
    sys.exit(main())
