from __future__ import annotations

import argparse
import csv
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from stage_a_baseline import build_pairs, load_csv

BASE = "https://www.data.jma.go.jp/stats/etrn/view/hourly_a1.php"
UA = "keiba-notes track-condition research/1.0"

# JMA station IDs are pinned so backtests remain reproducible.
# Tokyo Racecourse -> Fuchu AMeDAS is about 2.3 km away and has full weather elements.
# Kyoto Racecourse -> Nagaokakyo is the nearer precipitation station (~5 km);
# Kyotanabe (~9 km) supplies temperature/wind plus a second precipitation signal.
STATIONS = {
    "fuchu": {"ja": "府中", "prec_no": "44", "block_no": "1133", "elements": "full"},
    "nagaokakyo": {"ja": "長岡京", "prec_no": "61", "block_no": "1025", "elements": "rain"},
    "kyotanabe": {"ja": "京田辺", "prec_no": "61", "block_no": "0598", "elements": "full"},
}
TRACK_STATIONS = {
    "tokyo": {"rain_primary": "fuchu", "full": "fuchu", "rain_secondary": None},
    "kyoto": {"rain_primary": "nagaokakyo", "full": "kyotanabe", "rain_secondary": "kyotanabe"},
}


@dataclass
class HourlyWeather:
    station: str
    station_ja: str
    observed_date: str
    hour: int
    end_at: str
    precipitation_mm: float | None
    temperature_c: float | None
    humidity_pct: float | None
    wind_mps: float | None
    sunshine_hours: float | None
    source_url: str


def station_url(station: str, d: date) -> str:
    s = STATIONS[station]
    return (
        f"{BASE}?prec_no={s['prec_no']}&block_no={s['block_no']}"
        f"&year={d.year}&month={d.month}&day={d.day}&view="
    )


def _numeric(text: str) -> float | None:
    text = text.strip().replace("−", "-").replace("―", "-")
    if not text or "///" in text or text in {"×", "--", "-"}:
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(m.group(0)) if m else None


def _precip(text: str) -> float | None:
    text = text.strip().replace("−", "-").replace("―", "-")
    if "///" in text or text == "×":
        return None
    # JMA distinguishes '-' (no precipitation) from 0.0 (trace precipitation)
    # at staffed observatories. AMeDAS commonly reports 0.0. Both represent
    # zero measurable millimetres for this numeric feature.
    if text in {"", "--", "-"}:
        return 0.0
    return _numeric(text)


def parse_hourly_html(html: str, *, station: str, d: date, source_url: str = "fixture") -> list[HourlyWeather]:
    if station not in STATIONS:
        raise ValueError(f"unknown station: {station}")
    soup = BeautifulSoup(html, "html.parser")
    rows: list[HourlyWeather] = []
    for tr in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) < 9 or not re.fullmatch(r"\d{1,2}", cells[0].strip()):
            continue
        hour = int(cells[0])
        if not 1 <= hour <= 24:
            continue
        # hourly_a1 column order:
        # hour, precipitation, temperature, dewpoint, vapor pressure, humidity,
        # mean wind speed, wind direction, sunshine, snowfall, snow depth.
        end_at = datetime.combine(d, datetime.min.time()) + timedelta(hours=hour)
        rows.append(HourlyWeather(
            station=station,
            station_ja=STATIONS[station]["ja"],
            observed_date=d.isoformat(),
            hour=hour,
            end_at=end_at.isoformat(timespec="minutes"),
            precipitation_mm=_precip(cells[1]),
            temperature_c=_numeric(cells[2]),
            humidity_pct=_numeric(cells[5]),
            wind_mps=_numeric(cells[6]),
            sunshine_hours=_numeric(cells[8]),
            source_url=source_url,
        ))
    return rows


def fetch_day(session: requests.Session, station: str, d: date, retries: int = 3) -> list[HourlyWeather]:
    url = station_url(station, d)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=30, headers={"User-Agent": UA})
            r.raise_for_status()
            rows = parse_hourly_html(r.text, station=station, d=d, source_url=url)
            if len(rows) < 20:
                raise RuntimeError(f"only {len(rows)} hourly rows")
            return rows
        except Exception as exc:
            last = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"failed JMA fetch {station} {d}: {last}")


def needed_dates(observation_csv: Path) -> list[date]:
    rows = load_csv(observation_csv)
    pairs = build_pairs(rows, "turf")
    dates: set[date] = set()
    for p in pairs:
        start = date.fromisoformat(p.previous_date)
        end = date.fromisoformat(p.target_date)
        d = start
        while d <= end:
            dates.add(d)
            d += timedelta(days=1)
    return sorted(dates)


def collect(track: str, observation_csv: Path, max_workers: int = 5) -> list[HourlyWeather]:
    if track not in TRACK_STATIONS:
        raise ValueError("weather collector currently supports tokyo/kyoto")
    dates = needed_dates(observation_csv)
    station_names = sorted({x for x in TRACK_STATIONS[track].values() if x})
    jobs = [(station, d) for station in station_names for d in dates]
    out: list[HourlyWeather] = []

    # One Session per task avoids cross-thread mutation while keeping the code simple.
    def task(station: str, d: date):
        with requests.Session() as session:
            return fetch_day(session, station, d)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(task, station, d): (station, d) for station, d in jobs}
        for future in as_completed(futures):
            out.extend(future.result())
    return sorted(out, key=lambda x: (x.station, x.end_at))


def write_csv(rows: Iterable[HourlyWeather], path: Path) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(HourlyWeather.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--track", choices=sorted(TRACK_STATIONS), required=True)
    p.add_argument("--observations", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workers", type=int, default=5)
    args = p.parse_args()
    rows = collect(args.track, args.observations, max_workers=max(1, args.workers))
    write_csv(rows, args.output)
    stations = sorted(set(r.station for r in rows))
    days = len(set((r.station, r.observed_date) for r in rows))
    print(f"{args.track}: {len(rows)} hourly rows / {days} station-days / stations={stations}")


if __name__ == "__main__":
    main()
