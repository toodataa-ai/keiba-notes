from __future__ import annotations

import argparse
import csv
import re
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.jra.go.jp"
ACCESS = "/JRADB/accessS.html"
BOOTSTRAP_CNAME = "pw01skl00999999/B3"
TRACK_CODES = {"tokyo": "05", "kyoto": "08"}
CONDITIONS = ("良", "稍重", "重", "不良")
UA = "keiba-notes track-condition research/1.0"


@dataclass
class RaceConditionLabel:
    track: str
    track_code: str
    year: int
    meeting: int
    day_number: int
    race_number: int
    race_date: str
    start_time: str
    surface: str
    condition: str
    weather: str | None
    result_url: str
    result_cname: str


def _soup_from_post(session: requests.Session, cname: str) -> BeautifulSoup:
    r = session.post(BASE + ACCESS, data={"cname": cname}, timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    return BeautifulSoup(r.content, "html.parser")


def bootstrap_month_checks(session: requests.Session) -> dict[str, str]:
    soup = _soup_from_post(session, BOOTSTRAP_CNAME)
    scripts = "\n".join(s.get_text(" ", strip=True) for s in soup.find_all("script"))
    checks = dict(re.findall(r'objParam\["(\d{4})"\]\s*=\s*"([0-9A-Fa-f]{2})"', scripts))
    if not checks:
        # Some renderings preserve script source in str(script) but not get_text().
        scripts = "\n".join(str(s) for s in soup.find_all("script"))
        checks = dict(re.findall(r'objParam\["(\d{4})"\]\s*=\s*"([0-9A-Fa-f]{2})"', scripts))
    if not checks:
        raise RuntimeError("JRA historical-result month check-digit map not found")
    return {k: v.upper() for k, v in checks.items()}


def _extract_cnames(soup: BeautifulSoup, prefix: str) -> list[str]:
    found: list[str] = []
    pattern = re.compile(rf'({re.escape(prefix)}[^\s"\'<>)]*/[0-9A-Fa-f]{{2}})')
    for a in soup.find_all("a"):
        raw = str(a)
        for value in pattern.findall(raw):
            if value not in found:
                found.append(value)
    return found


def parse_srl_cname(cname: str) -> dict[str, int | str]:
    m = re.fullmatch(
        r"pw01srl10(?P<track>\d{2})(?P<year>\d{4})(?P<meeting>\d{2})(?P<day>\d{2})(?P<date>\d{8})/[0-9A-Fa-f]{2}",
        cname,
    )
    if not m:
        raise ValueError(f"unrecognized srl cname: {cname}")
    return {
        "track_code": m.group("track"),
        "year": int(m.group("year")),
        "meeting": int(m.group("meeting")),
        "day_number": int(m.group("day")),
        "race_date": m.group("date"),
    }


def parse_sde_cname(cname: str) -> dict[str, int | str]:
    m = re.fullmatch(
        r"pw01sde10(?P<track>\d{2})(?P<year>\d{4})(?P<meeting>\d{2})(?P<day>\d{2})(?P<race>\d{2})(?P<date>\d{8})/[0-9A-Fa-f]{2}",
        cname,
    )
    if not m:
        raise ValueError(f"unrecognized sde cname: {cname}")
    return {
        "track_code": m.group("track"),
        "year": int(m.group("year")),
        "meeting": int(m.group("meeting")),
        "day_number": int(m.group("day")),
        "race_number": int(m.group("race")),
        "race_date": m.group("date"),
    }


def anchor_dates(observation_csv: Path) -> set[str]:
    """Return race dates with an exact official morning moisture timestamp.

    Stage B deliberately excludes grouped/legacy rows whose measurement time is
    not explicit; this avoids silently inventing an anchor timestamp.
    """
    out: set[str] = set()
    with observation_csv.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("race_day", "").lower() not in {"true", "1"}:
                continue
            if not row.get("moisture_time"):
                continue
            out.add(row["observed_date"].replace("-", ""))
    return out


def month_srls(session: requests.Session, year: int, month: int, checks: dict[str, str]) -> list[str]:
    yymm = f"{year % 100:02d}{month:02d}"
    if yymm not in checks:
        raise RuntimeError(f"JRA result-search check digit missing for {yymm}")
    cname = f"pw01skl10{year:04d}{month:02d}/{checks[yymm]}"
    soup = _soup_from_post(session, cname)
    return _extract_cnames(soup, "pw01srl")


def day_result_cnames(session: requests.Session, srl_cname: str) -> list[str]:
    soup = _soup_from_post(session, srl_cname)
    cnames = _extract_cnames(soup, "pw01sde")
    # Keep only the selected meeting day, because the page can contain navigation
    # to adjacent days/tracks as well.
    day = parse_srl_cname(srl_cname)
    filtered = []
    for cname in cnames:
        try:
            race = parse_sde_cname(cname)
        except ValueError:
            continue
        if (
            race["track_code"] == day["track_code"]
            and race["year"] == day["year"]
            and race["meeting"] == day["meeting"]
            and race["day_number"] == day["day_number"]
            and race["race_date"] == day["race_date"]
        ):
            filtered.append(cname)
    return sorted(set(filtered), key=lambda x: int(parse_sde_cname(x)["race_number"]))


def parse_result_page(html: bytes, *, track: str, cname: str) -> RaceConditionLabel | None:
    meta = parse_sde_cname(cname)
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)

    # Finalized result pages contain the race date, start time and official course
    # condition near the header. Pages not yet finalized are ignored.
    tm = re.search(r"発走時刻[：:]?\s*(\d{1,2})時\s*(\d{2})分", text)
    if not tm:
        return None
    surface_match = re.search(r"(?:天候\s*[^\s]+\s*)?(芝|ダート)\s*(良|稍重|重|不良)", text)
    if not surface_match:
        # On some pages whitespace is collapsed between labels.
        surface_match = re.search(r"(芝|ダート)(良|稍重|重|不良)", text)
    if not surface_match:
        return None
    weather_match = re.search(r"天候\s*([^\s]+)", text)

    race_date_raw = str(meta["race_date"])
    race_date = datetime.strptime(race_date_raw, "%Y%m%d").date().isoformat()
    start_time = f"{int(tm.group(1)):02d}:{int(tm.group(2)):02d}"
    surface = "turf" if surface_match.group(1) == "芝" else "dirt"
    result_url = f"{BASE}{ACCESS}?CNAME={cname}"
    return RaceConditionLabel(
        track=track,
        track_code=str(meta["track_code"]),
        year=int(meta["year"]),
        meeting=int(meta["meeting"]),
        day_number=int(meta["day_number"]),
        race_number=int(meta["race_number"]),
        race_date=race_date,
        start_time=start_time,
        surface=surface,
        condition=surface_match.group(2),
        weather=weather_match.group(1) if weather_match else None,
        result_url=result_url,
        result_cname=cname,
    )


def collect(track: str, observation_csv: Path, *, session: requests.Session | None = None) -> list[RaceConditionLabel]:
    if track not in TRACK_CODES:
        raise ValueError("result label collector currently supports tokyo/kyoto")
    session = session or requests.Session()
    anchors = anchor_dates(observation_csv)
    if not anchors:
        return []
    checks = bootstrap_month_checks(session)
    months = sorted({(int(d[:4]), int(d[4:6])) for d in anchors})
    target_code = TRACK_CODES[track]
    labels: list[RaceConditionLabel] = []

    for year, month in months:
        srls = month_srls(session, year, month, checks)
        for srl in srls:
            try:
                meta = parse_srl_cname(srl)
            except ValueError:
                continue
            if meta["track_code"] != target_code or meta["race_date"] not in anchors:
                continue
            for cname in day_result_cnames(session, srl):
                url = f"{BASE}{ACCESS}?CNAME={cname}"
                r = session.get(url, timeout=30, headers={"User-Agent": UA})
                r.raise_for_status()
                label = parse_result_page(r.content, track=track, cname=cname)
                if label is not None:
                    labels.append(label)
                time.sleep(0.03)

    unique = {(x.race_date, x.race_number, x.track): x for x in labels}
    return sorted(unique.values(), key=lambda x: (x.race_date, x.race_number))


def write_csv(rows: Iterable[RaceConditionLabel], path: Path) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(RaceConditionLabel.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(asdict(row))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--track", choices=sorted(TRACK_CODES), required=True)
    p.add_argument("--observations", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    rows = collect(args.track, args.observations)
    write_csv(rows, args.output)
    by_surface = {s: sum(r.surface == s for r in rows) for s in ("turf", "dirt")}
    days = len(set(r.race_date for r in rows))
    conditions = {c: sum(r.condition == c for r in rows) for c in CONDITIONS}
    print(f"{args.track}: labels={len(rows)} days={days} surfaces={by_surface} conditions={conditions}")


if __name__ == "__main__":
    main()
