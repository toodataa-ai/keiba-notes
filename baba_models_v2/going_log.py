"""Research A: a daily log of 'what we knew in the morning' and 'what the going really was'.

One row per (race day, racecourse, surface):
  morning going / moisture / previous-day features, the JMA rain probabilities issued in the morning, the model outputs for the
  main race (11R) and the official going of every race of the day, plus the observed rain after the morning.
Outcomes come from the Claude result files (the main race's official going). --backfill-from rebuilds rows for past days from the forecast archive (no model outputs).
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


VENUE_CODE = {'01': 'sapporo', '02': 'hakodate', '03': 'fukushima', '04': 'niigata', '05': 'tokyo',
              '06': 'nakayama', '07': 'chukyo', '08': 'kyoto', '09': 'hanshin', '10': 'kokura'}


def main_outcomes(day, root='../claude_track'):
    """official going of each racecourse's main race (11R) from the Claude result files (+ the race card for the surface)."""
    out = {}
    for f in sorted(glob.glob(f'{root}/results/{day.isoformat()}-*-11.json')):
        res = json.load(open(f, encoding='utf-8'))
        g = res.get('official_going')
        if g not in GOING_JA: continue
        code = os.path.basename(f).split('-')[3]
        track = VENUE_CODE.get(code)
        cards = sorted(glob.glob(f"{root}/inputs/{res['race_id']}/*.json"))
        if not track or not cards: continue
        card = json.load(open(cards[-1], encoding='utf-8'))
        surface = {'芝': 'turf', 'ダ': 'dirt', 'ダート': 'dirt'}.get(card.get('surface'))
        if not surface: continue
        st = card.get('start_at') or res.get('scheduled_start_at') or ''
        start_h = (int(st[11:13]) + int(st[14:16]) / 60) if len(st) >= 16 else 15.5
        out[track] = {'surface': surface, 'going': GOING_JA.index(g), 'start_h': start_h, 'race_id': res['race_id'], 'distance_m': card.get('distance_m')}
    return out


def finish(row, outcome, sess):
    """add the outcome part to a row (idempotent). Only the main race's own surface has an outcome."""
    if not outcome or outcome['surface'] != row['surface']: return None
    first = GOING_JA.index(row['morning_going']) if row.get('morning_going') in GOING_JA else None
    row.update({'actual_main': outcome['going'], 'main_race_id': outcome['race_id'], 'main_start_h': round(outcome['start_h'], 2),
                'main_distance_m': outcome.get('distance_m'), 'morning_going_n': first,
                'changed_before_main': None if first is None else bool(outcome['going'] != first)})
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


def rows_from_archive(day, outcomes):
    """past day: JMA forecast from the morning archive + the official morning going/moisture from the first archive file
    that already shows that day.  No model outputs.  Only the main race's surface (the one with an outcome)."""
    from jra_going_now import parse_going_page
    files = sorted(glob.glob(f'forecast_archive/{day:%Y}/{day:%m}/{day:%Y%m%d}_*.json.gz'))
    fc = None; page = {}
    for g in files:
        h = int(g[-12:-10]) + int(g[-10:-8]) / 60
        rec = json.load(gzip.open(g, 'rt', encoding='utf-8'))
        if fc is None and 5.0 <= h <= 9.6: fc = (g, rec['forecasts'])
        for v in rec.get('jra', {}).values():
            p = parse_going_page(v['html'])
            if p.get('date') == day.isoformat() and p.get('venue') in sd.TRACK_RO and sd.TRACK_RO[p['venue']] not in page:
                page[sd.TRACK_RO[p['venue']]] = (p, os.path.basename(g))
    out = []
    for tr, o in outcomes.items():
        if fc is None or tr not in page: continue
        p, pf = page[tr]; mg = p.get('turf_going' if o['surface'] == 'turf' else 'dirt_going')
        if mg not in GOING_JA: continue
        fcs = [v for v in fc[1].values() if tr in v['tracks']]
        pops = gf.parse_pops(fcs[0]['data'], tr, day) if fcs else None
        m = np.nanmean([p.get('moist_turf_goal') or np.nan, p.get('moist_turf_4c') or np.nan] if o['surface'] == 'turf' else [p.get('moist_dirt_goal') or np.nan, p.get('moist_dirt_4c') or np.nan])
        out.append({'date': day.isoformat(), 'track': tr, 'surface': o['surface'], 'source': 'archive', 'model': None, 'forecast_file': os.path.basename(fc[0]),
                    'going_page_file': pf, 'morning_going': mg, 'moist0': None if m != m else round(float(m), 2), 'forecast_pops': pops,
                    'p_wet_main': gf.p_wet_after_morning(pops, o['start_h'])})
    return out


def score(rows):
    """summary numbers from rows that have both an outcome and model outputs / forecasts."""
    S = {'rows': len(rows), 'days': len({r['date'] for r in rows}), 'tracks': sorted({r['track'] for r in rows})}
    done = [r for r in rows if r.get('actual_main') is not None]
    S['with_outcome'] = len(done)
    S['changed_before_main'] = sum(1 for r in done if r.get('changed_before_main'))
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
        ch = [r for r in m if r.get('changed_before_main')]
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
    ap.add_argument('--last-days', type=int, default=1, help='also process the N-1 days before --date (GitHub schedules run late, often on the next JST day)')
    a = ap.parse_args(argv)
    day = date.fromisoformat(a.date) if a.date else (date.today())
    sess = requests.Session()
    rows = {(r['date'], r['track'], r['surface']): r for r in read_log()}
    days = []
    if a.backfill_from:
        d = date.fromisoformat(a.backfill_from)
        while d <= day: days.append(d); d += timedelta(days=1)
    else:
        days = [day - timedelta(days=k) for k in range(max(1, a.last_days) - 1, -1, -1)]
    for d in days:
        outcomes = main_outcomes(d)
        new = rows_from_live(d)
        if a.backfill_from:                       # fill what the live file lacks (older files had no forecast) and add the other racecourses
            arch = {(r['track'], r['surface']): r for r in rows_from_archive(d, outcomes)}
            for r in new:
                ar = arch.pop((r['track'], r['surface']), None)
                if ar and r.get('forecast_pops') is None:
                    r['forecast_pops'] = ar['forecast_pops']; r['p_wet_main'] = ar['p_wet_main']; r['forecast_file'] = ar['forecast_file']
            new = new + list(arch.values())
        for r in new:
            key = (r['date'], r['track'], r['surface'])
            old = rows.get(key)
            if old and old.get('source') == 'live' and r['source'] != 'live':
                continue                      # never replace a live (pre-race) row by a rebuilt one
            if old and old.get('source') == 'live':
                r = {**old}                   # keep the morning record; only the outcome is added below
            if r.get('actual_main') is None:
                r = finish(r, outcomes.get(r['track']), sess) or r
            rows[key] = r
    write_log(list(rows.values()))
    S = score(list(rows.values()))
    os.makedirs(os.path.dirname(SUMMARY), exist_ok=True)
    json.dump(S, open(SUMMARY, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
