from __future__ import annotations

import argparse
import csv
import io
import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

BASE = "https://www.jra.go.jp/keiba/baba/archive/"
TRACKS = {
    "sapporo": "札幌", "hakodate": "函館", "fukushima": "福島", "niigata": "新潟",
    "tokyo": "東京", "nakayama": "中山", "chukyo": "中京", "kyoto": "京都",
    "hanshin": "阪神", "kokura": "小倉",
}
WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]
UA = "keiba-notes track-condition research/1.0"


@dataclass
class Observation:
    year: int
    track: str
    meeting: int
    source_url: str
    observed_date: str
    weekday: str
    day_number: int | None
    race_day: bool
    race_day_inferred: bool
    course: str | None
    cushion_time: str | None
    cushion_value: float | None
    moisture_time: str | None
    turf_goal: float
    turf_corner: float
    dirt_goal: float
    dirt_corner: float
    source_format: str


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("4 コーナー", "4コーナー")
    s = re.sub(r"[\t\u3000]+", " ", s)
    s = re.sub(r" +", " ", s)
    return s


def archive_url(year: int) -> str:
    return f"{BASE}{year}.html"


def discover_pdf_urls(year: int, track: str, session: requests.Session | None = None) -> list[str]:
    if track not in TRACKS:
        raise ValueError(f"unsupported track: {track}")
    session = session or requests.Session()
    r = session.get(archive_url(year), timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    needle = f"/{year}pdf/{track}"
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if needle in href.lower() and href.lower().endswith(".pdf"):
            urls.append(urljoin(r.url, href))
    return sorted(set(urls))


def meeting_from_url(url: str) -> int:
    m = re.search(r"([a-z]+)(\d{2})\.pdf(?:\?|$)", url.lower())
    if not m:
        raise ValueError(f"cannot parse meeting from URL: {url}")
    return int(m.group(2))


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _to_float(v: str) -> float:
    return float(v.strip())


def _modern_rows(text: str, *, year: int, track: str, meeting: int, source_url: str) -> list[Observation]:
    rows: list[Observation] = []
    pattern = re.compile(
        r"(?:(?:第\s*(?P<dayno>\d+)\s*日)\s+)?"
        r"(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日\s+"
        r"(?P<weekday>[月火水木金土日])曜日\s+"
        r"(?P<course>[A-D])\s+"
        r"(?P<cush_time>\d{1,2}:\d{2})\s+(?P<cush>\d+(?:\.\d+)?)\s+"
        r"(?P<moist_time>\d{1,2}:\d{2})\s+"
        r"(?P<turf_goal>\d+(?:\.\d+)?)\s+(?P<turf_corner>\d+(?:\.\d+)?)\s+"
        r"(?P<dirt_goal>\d+(?:\.\d+)?)\s+(?P<dirt_corner>\d+(?:\.\d+)?)"
    )
    for raw in norm(text).splitlines():
        line = raw.strip()
        m = pattern.search(line)
        if not m:
            continue
        dayno = int(m.group("dayno")) if m.group("dayno") else None
        obs_date = date(year, int(m.group("month")), int(m.group("day")))
        rows.append(Observation(
            year=year, track=track, meeting=meeting, source_url=source_url,
            observed_date=obs_date.isoformat(), weekday=m.group("weekday"),
            day_number=dayno, race_day=dayno is not None, race_day_inferred=False,
            course=m.group("course"), cushion_time=m.group("cush_time"),
            cushion_value=_to_float(m.group("cush")), moisture_time=m.group("moist_time"),
            turf_goal=_to_float(m.group("turf_goal")), turf_corner=_to_float(m.group("turf_corner")),
            dirt_goal=_to_float(m.group("dirt_goal")), dirt_corner=_to_float(m.group("dirt_corner")),
            source_format="modern",
        ))
    return rows


def _dates_for_header(start: date, end: date, weekdays: list[str]) -> list[date]:
    dates = []
    d = start
    while d <= end:
        if WEEKDAY_JA[d.weekday()] in weekdays:
            dates.append(d)
        d += timedelta(days=1)
    # Header order is chronological in JRA legacy tables. If a repeated weekday ever
    # appears in one range, preserve date order rather than guessing from positions.
    return dates


def _numbers_after(line: str, marker: str) -> list[float]:
    if marker not in line:
        return []
    tail = line.split(marker, 1)[1]
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", tail)]


def _legacy_rows(text: str, *, year: int, track: str, meeting: int, source_url: str) -> list[Observation]:
    text = norm(text)
    # Legacy JRA PDFs used both "...日の含水率" and "...日の気象状況" for the
    # same moisture table layout. Cross-month ranges are also supported.
    range_re = re.compile(
        r"(?P<year>\d{4})年\s*(?P<sm>\d{1,2})月\s*(?P<sd>\d{1,2})日から"
        r"(?:(?P<em>\d{1,2})月)?\s*(?P<ed>\d{1,2})日の(?:含水率|気象状況)"
    )
    matches = list(range_re.finditer(text))
    rows: list[Observation] = []
    for i, rm in enumerate(matches):
        block = text[rm.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        sm, sd = int(rm.group("sm")), int(rm.group("sd"))
        em = int(rm.group("em")) if rm.group("em") else sm
        ed = int(rm.group("ed"))
        start, end = date(year, sm, sd), date(year, em, ed)
        lines = [x.strip() for x in block.splitlines() if x.strip()]

        header = next((x for x in lines if "場所" in x and "曜日" in x), None)
        if not header:
            continue
        weekdays = re.findall(r"([月火水木金土日])曜日", header)
        dates = _dates_for_header(start, end, weekdays)
        if len(dates) != len(weekdays):
            continue

        turf_goal = turf_corner = dirt_goal = dirt_corner = None
        for line in lines:
            if "芝コース含水率" in line and "ゴール前" in line:
                turf_goal = _numbers_after(line, "ゴール前")
            elif "4コーナー" in line and turf_corner is None:
                turf_corner = _numbers_after(line, "4コーナー")
            elif "ダートコース含水率" in line and "ゴール前" in line:
                dirt_goal = _numbers_after(line, "ゴール前")
            elif "4コーナー" in line and turf_corner is not None and dirt_corner is None:
                dirt_corner = _numbers_after(line, "4コーナー")

        series = [turf_goal, turf_corner, dirt_goal, dirt_corner]
        if any(v is None or len(v) != len(dates) for v in series):
            continue
        assert turf_goal is not None and turf_corner is not None and dirt_goal is not None and dirt_corner is not None
        for idx, d in enumerate(dates):
            wd = WEEKDAY_JA[d.weekday()]
            rows.append(Observation(
                year=year, track=track, meeting=meeting, source_url=source_url,
                observed_date=d.isoformat(), weekday=wd, day_number=None,
                race_day=(wd != "金"), race_day_inferred=True,
                course=None, cushion_time=None, cushion_value=None, moisture_time=None,
                turf_goal=turf_goal[idx], turf_corner=turf_corner[idx],
                dirt_goal=dirt_goal[idx], dirt_corner=dirt_corner[idx],
                source_format="legacy",
            ))
    return rows


def parse_pdf_text(text: str, *, year: int, track: str, meeting: int, source_url: str = "fixture") -> list[Observation]:
    normalized = norm(text)
    modern = _modern_rows(normalized, year=year, track=track, meeting=meeting, source_url=source_url)
    if modern:
        return modern
    return _legacy_rows(normalized, year=year, track=track, meeting=meeting, source_url=source_url)


def collect(years: Iterable[int], track: str, session: requests.Session | None = None) -> list[Observation]:
    session = session or requests.Session()
    out: list[Observation] = []
    for year in years:
        for url in discover_pdf_urls(year, track, session):
            pdf = session.get(url, timeout=45, headers={"User-Agent": UA})
            pdf.raise_for_status()
            text = extract_pdf_text(pdf.content)
            rows = parse_pdf_text(text, year=year, track=track, meeting=meeting_from_url(url), source_url=url)
            if not rows:
                raise RuntimeError(f"parsed zero rows: {url}")
            out.extend(rows)
    # Date + meeting de-duplication is deliberate; archive PDFs can be rediscovered through aliases.
    unique = {(r.observed_date, r.meeting, r.track): r for r in out}
    return sorted(unique.values(), key=lambda r: (r.observed_date, r.meeting))


def write_csv(rows: Iterable[Observation], path: Path) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(rows[0]).keys()) if rows else [f.name for f in Observation.__dataclass_fields__.values()]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--track", choices=sorted(TRACKS), required=True)
    p.add_argument("--from-year", type=int, required=True)
    p.add_argument("--to-year", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    rows = collect(range(args.from_year, args.to_year + 1), args.track)
    write_csv(rows, args.output)
    print(f"{args.track}: {len(rows)} observations -> {args.output}")


if __name__ == "__main__":
    main()
