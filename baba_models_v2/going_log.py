"""Research A: a daily log of 'what we knew in the morning' and 'what the going really was'.

One row per (race day, racecourse, surface):
  morning going / moisture / previous-day features, the JMA rain probabilities issued in the morning, the model outputs for the
  main race (11R) and the official going of every race of the day, plus the observed rain after the morning.
Rows are appended by the daily action; --backfill-from rebuilds rows for past days from the forecast archive (no model outputs).
Nothing here feeds a prediction.
"""
import argparse, glob, gzip, json, os, sys, time
from datetime import date, timedelta
import numpy as np, pandas as pd, requests

import going_forecast as gf
import jma_weather as jw
import stage_b_dataset as sd

LOG = 'going_log/going_log_v1.jsonl'
SUMMARY = '../docs/data/going_log_summary_v1.json'
GOING_JA = ['良', '稍重', '重', '不良']


def read_log(path=LOG):
    if not os.path.exists(path): return []
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


def write_log(rows, path=LOG):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = sorted(rows, key=lambda r: (r['date'], r['track'], r['surface']))
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')


def recent_labels(recent_dir='going_labels/recent'):
    fs = sorted(glob.glob(recent_dir + '/*.csv'))
    if not fs: return pd.DataFrame()
    e = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True).dropna(subset=['start_time'])
    e['track'] = e['track'].map(sd.TRACK_RO); e['surface'] = e['surface'].map({'芝': 'turf', 'ダート': 'dirt'})
    e['going_n'] = e['going'].map(sd.GOING); e['date'] = pd.to_datetime(e['date'])
    t = e['start_time'].str.split(':', expand=True).astype(float); e['start_h'] = t[0] + t[1] / 60
    return e.drop_duplicates(['date', 'track', 'surface', 'race_no'])


def observed_rain(track, day, start_h, sess):
    ts = jw.TRACK_STATIONS[track]; vals = {}
    for st in [ts['rain_primary']] + ([ts['rain_secondary']] if ts['rain_secondary'] else []):
        try:
            r = sess.get(jw.station_url(st, day), timeout=30, headers={'User-Agent': jw.UA}); r.raise_for_status()
            for h in jw.parse_hourly_html(r.text, station=st, d=day, source_url='log'):
                if h.precipitation_mm is not None and h.precipitation_mm == h.precipitation_mm:
                    vals.setdefault(h.hour, h.precipitation_mm)
        except Exception as e:
            print('rain fetch failed', st, day, e, file=sys.stderr)
        time.sleep(0.3)
    hh = int(np.ceil(start_h)); cols = [c for c in vals if gf.MORNING_H < c <= hh]
    return round(float(sum(vals[c] for c in cols)), 1) if cols else None


def actual_going(labels, track, day, surface):
    x = labels[(labels.track == track) & (labels.date == pd.Timestamp(day)) & (labels.surface == surface)].sort_values('race_no')
    return {int(r.race_no): int(r.going_n) for r in x.itertuples() if r.going_n == r.going_n}, {int(r.race_no): float(r.start_h) for r in x.itertuples()}


def finish(row, act, starts, sess):
    """add the outcome part to a row (idempotent)."""
    if not act: return None
    main = 11 if 11 in act else max(act)
    first = act[min(act)]
    row.update({'actual_going': {str(k): v for k, v in act.items()}, 'actual_main': act[main], 'main_race_no': main,
                'main_start_h': round(starts.get(main, 15.5), 2), 'first_race_going': first,
                'changed': bool(len(set(act.values())) > 1), 'changed_before_main': bool(act[main] != first)})
    row['rain_mm_after_morning'] = observed_rain(row['track'], date.fromisoformat(row['date']), row['main_start_h'], sess)
    row['wet'] = None if row['rain_mm_after_morning'] is None else bool(row['rain_mm_after_morning'] >= 1.0)
    return row


def rows_from_live(day, live_dir='live'):
    out = []
    for f in sorted(glob.glob(f'{live_dir}/{day.isoformat()}_*.json')):
        rec = json.load(open(f, encoding='utf-8'))
        if rec.get('status') != 'ok': continue
        for s in rec['surfaces']:
            main = next((r for r in s['races'] if r['race_no'] == 11), s['races'][-1])
            idx = [r['race_no'] for r in s['races']].index(main['race_no'])
            out.append({'date': rec['date'], 'track': rec['track'], 'surface': s['surface'], 'source': 'live', 'model': rec.get('model'),
                        'generated_at_jst': rec.get('generated_at_jst'), 'morning_going': s['morning_going'], 'moist0': s['moist0'],
                        'inputs': s.get('inputs'), 'forecast_pops': (rec.get('forecast') or {}).get('pops'),
                        'p_wet_main': (s.get('p_wet_after_morning') or [None] * 12)[idx] if s.get('p_wet_after_morning') else None,
                        'probs_main': main['probs'], 'probs_no_forecast_main': {k: v for k, v in (s.get('probs_no_forecast') or [{}] * 12)[idx].items() if k != 'race_no'} if s.get('probs_no_forecast') else None,
                        'probs_morning_persists': s.get('probs_morning_persists'), 'p_change_main': main.get('p_change_from_morning')})
    return out


def rows_from_archive(day, labels):
    """past day: forecast from the morning archive + official going; no model outputs."""
    f = None
    for g in sorted(glob.glob(f'forecast_archive/{day:%Y}/{day:%m}/{day:%Y%m%d}_*.json.gz')):
        h = int(g[-12:-10]) + int(g[-10:-8]) / 60
        if 5.5 <= h <= 9.6: f = g; break
    if not f: return []
    rec = json.load(gzip.open(f, 'rt', encoding='utf-8')); out = []
    for v in rec['forecasts'].values():
        for tr in v['tracks']:
            for s in ('turf', 'dirt'):
                act, starts = actual_going(labels, tr, day, s)
                if not act: continue
                pops = gf.parse_pops(v['data'], tr, day)
                main = 11 if 11 in act else max(act)
                out.append({'date': day.isoformat(), 'track': tr, 'surface': s, 'source': 'archive', 'model': None, 'archive_file': os.path.basename(f),
                            'morning_going': GOING_JA[act[min(act)]], 'forecast_pops': pops,
                            'p_wet_main': gf.p_wet_after_morning(pops, starts.get(main, 15.5))})
    return out


def score(rows):
    """summary numbers from rows that have both an outcome and model outputs / forecasts."""
    S = {'rows': len(rows), 'days': len({r['date'] for r in rows}), 'tracks': sorted({r['track'] for r in rows})}
    done = [r for r in rows if r.get('actual_main') is not None]
    S['with_outcome'] = len(done)
    S['changed_before_main'] = sum(1 for r in done if r['changed_before_main'])
    S['changed_any'] = sum(1 for r in done if r['changed'])
    S['wet_days'] = sum(1 for r in done if r.get('wet'))
    S['first_date'] = min((r['date'] for r in rows), default=None); S['last_date'] = max((r['date'] for r in rows), default=None)
    m = [r for r in done if r.get('probs_main') and r.get('probs_morning_persists')]
    S['scored_main'] = len(m)
    if m:
        def ll(p, a): return float(-np.log(max(1e-6, p[GOING_JA[a]])))
        S['main_logloss'] = {'final': float(np.mean([ll(r['probs_main'], r['actual_main']) for r in m])),
                             'baseline_morning_persists': float(np.mean([ll(r['probs_morning_persists'], r['actual_main']) for r in m]))}
        g2 = [r for r in m if r.get('probs_no_forecast_main')]
        if g2: S['main_logloss']['no_forecast'] = float(np.mean([ll(r['probs_no_forecast_main'], r['actual_main']) for r in g2]))
        S['main_hit'] = {'final': float(np.mean([max(r['probs_main'], key=r['probs_main'].get) == GOING_JA[r['actual_main']] for r in m])),
                         'baseline_morning_persists': float(np.mean([r['morning_going'] == GOING_JA[r['actual_main']] for r in m]))}
        ch = [r for r in m if r['changed_before_main']]
        if ch:
            S['changed_cases'] = {'n': len(ch), 'logloss_final': float(np.mean([ll(r['probs_main'], r['actual_main']) for r in ch])),
                                  'logloss_baseline': float(np.mean([ll(r['probs_morning_persists'], r['actual_main']) for r in ch]))}
    pw = [r for r in done if r.get('p_wet_main') is not None and r.get('wet') is not None]
    S['forecast_check'] = {'n': len(pw)}
    if pw:
        p = np.array([r['p_wet_main'] for r in pw]); w = np.array([float(r['wet']) for r in pw])
        S['forecast_check'].update({'wet_rate': float(w.mean()), 'brier_forecast': float(((p - w) ** 2).mean()), 'brier_climatology': float(((w.mean() - w) ** 2).mean())})
        rel = []
        for lo, hi in ((0, .1), (.1, .3), (.3, .5), (.5, .7), (.7, 1.01)):
            k = (p >= lo) & (p < hi)
            if k.sum(): rel.append({'range': f'{int(lo*100)}-{min(100,int(hi*100))}%', 'n': int(k.sum()), 'mean_p': float(p[k].mean()), 'observed': float(w[k].mean())})
        S['forecast_check']['reliability'] = rel
    return S


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None); ap.add_argument('--backfill-from', default=None)
    a = ap.parse_args(argv)
    day = date.fromisoformat(a.date) if a.date else (date.today())
    labels = recent_labels(); sess = requests.Session()
    rows = {(r['date'], r['track'], r['surface']): r for r in read_log()}
    days = []
    if a.backfill_from:
        d = date.fromisoformat(a.backfill_from)
        while d <= day: days.append(d); d += timedelta(days=1)
    else:
        days = [day]
    for d in days:
        new = rows_from_live(d)
        if not new and a.backfill_from:
            new = rows_from_archive(d, labels)
        for r in new:
            key = (r['date'], r['track'], r['surface'])
            old = rows.get(key)
            if old and old.get('source') == 'live' and r['source'] != 'live':
                continue                      # never replace a live (pre-race) row by a rebuilt one
            if old and old.get('source') == 'live':
                r = {**old}                   # keep the morning record; only the outcome is added below
            if r.get('actual_main') is None:
                act, starts = actual_going(labels, r['track'], d, r['surface'])
                r = finish(r, act, starts, sess) or r
            rows[key] = r
    write_log(list(rows.values()))
    S = score(list(rows.values()))
    os.makedirs(os.path.dirname(SUMMARY), exist_ok=True)
    json.dump(S, open(SUMMARY, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
