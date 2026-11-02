"""Hourly JMA weather for every race day and the 3 days before it (Stage B dataset, research only).

Per track: the rain station(s), the temperature/wind/sunshine station and the humidity observatory
listed in jma_weather.py. Output keeps only numbers (no URLs) to stay small.
Failures are recorded, not hidden; nothing is filled in.
"""
import argparse, csv, glob, json, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
import requests

import jma_weather as jw

TRACK_JA = {'札幌': 'sapporo', '函館': 'hakodate', '福島': 'fukushima', '新潟': 'niigata', '東京': 'tokyo',
            '中山': 'nakayama', '中京': 'chukyo', '京都': 'kyoto', '阪神': 'hanshin', '小倉': 'kokura'}
FIELDS = ['station', 'observed_date', 'hour', 'precipitation_mm', 'temperature_c', 'humidity_pct', 'wind_mps', 'sunshine_hours']


def stations_for(track):
    names = {v for v in jw.TRACK_STATIONS[track].values() if v}
    names.add(jw.HUMIDITY_STATION[track])
    return sorted(names)


def race_dates(labels_dir, track, back=3):
    ja = {v: k for k, v in TRACK_JA.items()}[track]
    ds = set()
    for f in sorted(glob.glob(labels_dir + '/jra_going_20*.csv')):
        for r in csv.DictReader(open(f, encoding='utf-8')):
            if r['track'] == ja:
                ds.add(date.fromisoformat(r['date']))
    return sorted({d - timedelta(k) for d in ds for k in range(back + 1)})


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--track', required=True, choices=sorted(jw.TRACK_STATIONS))
    p.add_argument('--labels-dir', default='going_labels')
    p.add_argument('--out', required=True)
    p.add_argument('--workers', type=int, default=4)
    a = p.parse_args(argv)
    dates = race_dates(a.labels_dir, a.track)
    st = stations_for(a.track)
    jobs = [(s, d) for s in st for d in dates]
    rows, failed = [], []

    def task(s, d):
        with requests.Session() as sess:
            time.sleep(0.2)
            return jw.fetch_day(sess, s, d, retries=4)

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(task, s, d): (s, d) for s, d in jobs}
        for f in as_completed(futs):
            s, d = futs[f]
            try:
                rows.extend(f.result())
            except Exception as e:
                failed.append({'station': s, 'date': d.isoformat(), 'error': str(e)[:160]})
    rows.sort(key=lambda r: (r.station, r.end_at))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh); w.writerow(FIELDS)
        for r in rows:
            w.writerow([r.station, r.observed_date, r.hour, r.precipitation_mm, r.temperature_c, r.humidity_pct, r.wind_mps, r.sunshine_hours])
    # coverage per station and year (share of non-missing hourly values)
    cov = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0]))
    for r in rows:
        c = cov[r.station][r.observed_date[:4]]
        c[0] += 1
        c[1] += r.precipitation_mm is not None; c[2] += r.temperature_c is not None
        c[3] += r.humidity_pct is not None; c[4] += r.wind_mps is not None
    summary = {'track': a.track, 'stations': st, 'dates': len(dates), 'rows': len(rows), 'failed': failed,
               'coverage_precip_temp_humid_wind': {s: {y: [round(x / c[0], 3) for x in c[1:]] for y, c in sorted(v.items())} for s, v in cov.items()}}
    json.dump(summary, open(a.out + '.summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(a.track, 'dates', len(dates), 'stations', st, 'rows', len(rows), 'failed', len(failed))


if __name__ == '__main__':
    main()
