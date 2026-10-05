from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

TRACKS = ("札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉")
TRACK_RE = re.compile(rf"^\d+回({'|'.join(TRACKS)})\d+日$")
TIME_RE = re.compile(r"^(\d{1,2})時(\d{2})分$")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
BASE = "https://www.jra.go.jp/keiba/calendar{year}/{year}/{month}/{mmdd}.html"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def race_name(condition: str) -> str:
    condition = normalize(condition)
    parts = re.split(r"\s(?=(?:障害)?(?:2歳|3歳|4歳))", condition, maxsplit=1)
    return parts[0].strip()


def page_url(day: datetime) -> str:
    return BASE.format(year=day.year, month=day.month, mmdd=day.strftime("%m%d"))


def parse_main_races(html: str, url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    lines = [normalize(x) for x in soup.get_text("\n", strip=True).splitlines()]
    lines = [x for x in lines if x]
    races: list[dict[str, str]] = []
    current_track: str | None = None
    i = 0
    while i < len(lines):
        m = TRACK_RE.match(lines[i])
        if m:
            current_track = m.group(1)
            i += 1
            continue
        if lines[i] == "11レース" and current_track:
            parts: list[str] = []
            post_time: str | None = None
            j = i + 1
            while j < len(lines):
                tm = TIME_RE.match(lines[j])
                if tm:
                    post_time = f"{int(tm.group(1)):02d}:{tm.group(2)}"
                    break
                if TRACK_RE.match(lines[j]) or lines[j].endswith("レース"):
                    break
                if lines[j] not in {"レース名・条件", "発走時刻", "--- | --- | ---"}:
                    parts.append(lines[j])
                j += 1
            if parts and post_time:
                races.append({
                    "track": current_track,
                    "race": race_name(" ".join(parts)),
                    "post_time": post_time,
                    "source_url": url,
                })
            i = max(j, i + 1)
            continue
        i += 1
    return races


def fetch_day(session: requests.Session, day: datetime) -> list[dict[str, str]]:
    url = page_url(day)
    r = session.get(
        url,
        timeout=25,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
            "Referer": f"https://www.jra.go.jp/keiba/calendar{day.year}/",
        },
    )
    # JRA can return 403 as well as 404 for dates that do not have a published
    # race-program page. Treat both as "no scheduled meeting on this date".
    if r.status_code in {403, 404}:
        return []
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return parse_main_races(r.text, url)


def build(days: int) -> dict:
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    session = requests.Session()
    out_days = []
    weekday = "月火水木金土日"
    for offset in range(days + 1):
        day = start + timedelta(days=offset)
        races = fetch_day(session, day)
        if races:
            out_days.append({
                "date": day.strftime("%Y-%m-%d"),
                "weekday": weekday[day.weekday()],
                "races": races,
            })
    return {
        "schema_version": 1,
        "updated_at": now.strftime("%Y-%m-%d"),
        "source": "JRA 開催日程・競馬番組",
        "policy": {
            "prediction": "当日午前（最新の出馬表・馬場情報を反映）",
            "review": "結果確定後〜当日夜",
            "scope": "JRA各開催日の11R（メインレース）",
        },
        "days": out_days,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=Path("docs/data/upcoming_schedule.json"))
    p.add_argument("--days", type=int, default=35)
    p.add_argument("--min-races", type=int, default=4)
    args = p.parse_args()
    data = build(args.days)
    count = sum(len(d["races"]) for d in data["days"])
    if count < args.min_races:
        raise SystemExit(f"too few races parsed: {count} < {args.min_races}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"schedule updated: days={len(data['days'])} races={count} -> {args.output}")


if __name__ == "__main__":
    main()
