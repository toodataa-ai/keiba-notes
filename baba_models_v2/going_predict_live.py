"""Race-day going prediction (Stage B model G2: no forecast needed).  Record-only until the user approves its use.

Inputs known by the morning of race day D:
  * the official morning going/moisture/course  (jra_going_now.parse_going_page; 'replay' mode uses history instead)
  * previous race day's official results on that surface (going_labels + recent labels), previous moisture (observations)
  * JMA observed hourly weather D-3 .. D (up to now)
Output: probabilities (良/稍重/重/不良) for each race number, per surface.  Not wired into any official prediction.
"""
import argparse, glob, json, sys, time
from datetime import date, datetime, timedelta, timezone
import numpy as np, pandas as pd
import requests

import jma_weather as jw
import going_forecast as gf
import going_unified as gu
import stage_b_dataset as sd
from stage_b_experiment import BASE, PREV, MORNING, MORNING_WX, design
from sklearn.ensemble import HistGradientBoostingClassifier

JST = timezone(timedelta(hours=9))
MOR = ['morning', 'morning_other', 'hours_since_ref']
NUMS = BASE + PREV + MORNING + MORNING_WX + ['start_h', 'race_no'] + MOR
GOING_JA = ['良', '稍重', '重', '不良']
WX_COLS = ['station', 'observed_date', 'hour', 'precipitation_mm', 'temperature_c', 'humidity_pct', 'wind_mps', 'sunshine_hours']


def training_frame(before=None):
    df = pd.read_csv('stage_b/stage_b_dataset.csv.gz', parse_dates=['date']).sort_values(['track', 'date', 'surface', 'race_no']).reset_index(drop=True)
    g = df.groupby(['track', 'date', 'surface'])
    df['morning'] = g['going_n'].transform('first')
    oth = df[g.cumcount() == 0].pivot_table(index=['track', 'date'], columns='surface', values='going_n')
    df = df.join(oth.rename(columns={'turf': 'm_turf', 'dirt': 'm_dirt'}), on=['track', 'date'])
    df['morning_other'] = np.where(df.surface == 'turf', df.m_dirt, df.m_turf)
    df['hours_since_ref'] = df.start_h - g['start_h'].transform('first')
    if before is not None:
        df = df[df.date < pd.Timestamp(before)]
    return df


def fit_models(df):
    models = {}
    for s in ('turf', 'dirt'):
        d = df[df.surface == s]
        X = design(d, NUMS, [])
        m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
                                           min_samples_leaf=30, random_state=0).fit(X, d.going_n)
        models[s] = (m, X.columns)
    return models


def predict_probs(models, rows, surface):
    m, cols = models[surface]
    X = design(rows, NUMS, [], cols)
    P = np.zeros((len(rows), 4)); pr = m.predict_proba(X)
    for j, c in enumerate(m.classes_): P[:, int(c)] = pr[:, j]
    P = np.clip(P, 1e-6, 1); return P / P.sum(1, keepdims=True)


def typical_schedule(labels, track, today):
    L = labels[(labels.track == track) & (labels.date >= pd.Timestamp(today) - pd.Timedelta(days=800)) & (labels.date < pd.Timestamp(today))]
    s = L.groupby('race_no').start_h.median()
    return {int(k): float(v) for k, v in s.items()}


def previous_day_features(labels, track, surface, day):
    L = labels[(labels.track == track) & (labels.surface == surface) & (labels.date < pd.Timestamp(day)) &
               (labels.date >= pd.Timestamp(day) - pd.Timedelta(days=4))]
    if L.empty:
        return {'last_going': np.nan, 'heavy_share': np.nan, 'gap_prev_day': np.nan}
    pdate = L.date.max(); x = L[L.date == pdate].sort_values('race_no')
    return {'last_going': float(x.going_n.iloc[-1]), 'heavy_share': float((x.going_n >= 1).mean()),
            'gap_prev_day': float((pd.Timestamp(day) - pdate).days)}


def previous_moisture(obs, track, surface, day):
    o = obs[(obs.track == track) & (obs.date < pd.Timestamp(day)) & (obs.date >= pd.Timestamp(day) - pd.Timedelta(days=5))].sort_values('date')
    if o.empty: return np.nan
    v = o['turf_m' if surface == 'turf' else 'dirt_m'].iloc[-1]
    return float(v) if v == v else np.nan


def fetch_live_weather(track, day):
    rows = []
    with requests.Session() as sess:
        for st in sorted({v for v in jw.TRACK_STATIONS[track].values() if v} | {jw.HUMIDITY_STATION[track]}):
            for k in range(4):
                d = day - timedelta(days=k)
                try:
                    r = sess.get(jw.station_url(st, d), timeout=30, headers={'User-Agent': jw.UA}); r.raise_for_status()
                    for h in jw.parse_hourly_html(r.text, station=st, d=d, source_url='live'):
                        rows.append({c: getattr(h, c) for c in WX_COLS})
                except Exception as e:
                    print('weather fetch failed', st, d, e, file=sys.stderr)
                time.sleep(0.3)
    W = pd.DataFrame(rows, columns=WX_COLS); W['date'] = pd.to_datetime(W['observed_date'])
    return W


def build_rows(track, day, surface, info, labels, obs, W, schedule):
    """info: morning (0-3), morning_other (0-3 or nan), moist0 (float or nan)."""
    nos = sorted(schedule)
    rows = pd.DataFrame({'race_no': nos, 'start_h': [schedule[n] for n in nos]})
    rows['date'] = pd.Timestamp(day); rows['track'] = track; rows['surface'] = surface
    rows['month_sin'] = np.sin(2 * np.pi * day.month / 12); rows['month_cos'] = np.cos(2 * np.pi * day.month / 12)
    for k, v in previous_day_features(labels, track, surface, day).items(): rows[k] = v
    rows['moist_prev'] = previous_moisture(obs, track, surface, day)
    rows['moist0'] = info['moist0']
    rows['morning'] = info['morning']; rows['morning_other'] = info['morning_other']
    rows['hours_since_ref'] = rows.start_h - rows.start_h.iloc[0]
    wf = sd.weather_features(track, None, W, rows[['date', 'start_h']])
    for c in wf.columns: rows[c] = wf[c].values
    return rows


def load_context():
    labels = sd.load_labels('going_labels')
    extra = sorted(glob.glob('going_labels/recent/*.csv'))
    if extra:
        e = pd.concat([pd.read_csv(f) for f in extra], ignore_index=True)
        e = e.dropna(subset=['start_time']) if 'start_time' in e.columns else e.iloc[0:0]
    else:
        e = None
    if e is not None and len(e):
        e['track'] = e['track'].map(sd.TRACK_RO); e['surface'] = e['surface'].map({'芝': 'turf', 'ダート': 'dirt'})
        e['going_n'] = e['going'].map(sd.GOING); e['date'] = pd.to_datetime(e['date'])
        t = e['start_time'].str.split(':', expand=True).astype(float); e['start_h'] = t[0] + t[1] / 60
        labels = pd.concat([labels, e], ignore_index=True).drop_duplicates(['date', 'track', 'surface', 'race_no'])
    return labels, sd.load_obs('observations')


FC_URL = 'https://www.jma.go.jp/bosai/forecast/data/forecast/{code}.json'


def fetch_forecast(track):
    """latest JMA short-range forecast for the racecourse's prefecture/region (None when it cannot be read)."""
    code = gf.AREA[track][:3] + '000'
    try:
        r = requests.get(FC_URL.format(code=code), timeout=30, headers={'User-Agent': jw.UA}); r.raise_for_status()
        return r.json()
    except Exception as e:
        print('forecast fetch failed', track, e, file=sys.stderr); return None


def baseline_matrix(df, surface):
    """P(going at a race | going of the day's first race): the 'morning persists' reference."""
    d = df[df.surface == surface]; C = np.ones((4, 4))
    for m, a in zip(d.morning, d.going_n):
        if m == m: C[int(m), int(a)] += 1
    return C / C.sum(1, keepdims=True)


def forecast_predictions(track, day, surface, rows, info, m5, base_C, pops):
    """-> (P_final, P_no_forecast_placeholder is computed by caller, p_wet array)"""
    pw = np.array([gf.p_wet_after_morning(pops, h) if pops else np.nan for h in rows.start_h])
    if pops is None or np.isnan(pw).any():
        return None, pw
    return gu.mixed(m5[surface], rows, pw), pw


def result_record(track, day, surface, info, rows, P, source, extra=None):
    races = []
    for (_, r), p in zip(rows.iterrows(), P):
        races.append({'race_no': int(r.race_no), 'start_h': round(float(r.start_h), 2),
                      'probs': {GOING_JA[i]: round(float(p[i]), 4) for i in range(4)},
                      'most_likely': GOING_JA[int(p.argmax())], 'p_change_from_morning': round(float(1 - p[int(info['morning'])]), 4)})
    rec = {'surface': surface, 'morning_going': GOING_JA[int(info['morning'])], 'moist0': info['moist0'], 'source': source, 'races': races}
    if extra:
        rec.update(extra)
    return rec


def run_live(track, day, out_dir='live'):
    from jra_going_now import parse_going_page
    labels, obs = load_context()
    tf = training_frame(before=day)
    models = fit_models(tf)
    g5 = gu.training_frame(); g5 = g5[g5.date < pd.Timestamp(day)]
    m5 = {s: gu.fit(g5[g5.surface == s], gu.NUMS5) for s in ('turf', 'dirt')}
    fc = fetch_forecast(track); pops = gf.parse_pops(fc, track, day) if fc else None
    W = fetch_live_weather(track, day)
    sched = typical_schedule(labels, track, day)
    ja = {v: k for k, v in sd.TRACK_RO.items()}[track]
    page = None
    for name in ('index.html', 'index2.html', 'index3.html'):
        r = requests.get('https://www.jra.go.jp/keiba/baba/' + name, timeout=30, headers={'User-Agent': jw.UA})
        p = parse_going_page(r.content.decode('cp932', errors='replace'))
        if p['venue'] == ja and p['date'] == day.isoformat():
            page = p; break
    rec = {'track': track, 'date': day.isoformat(), 'generated_at_jst': datetime.now(JST).isoformat(timespec='seconds'),
           'model': 'G5 (rain scenario x JMA rain probability)' if pops else 'G2 (no forecast; forecast could not be read)',
           'record_only': False, 'forecast': {'pops': pops, 'rule': 'p_wet = 1 - prod(1-p_block)^(overlap/6h), window = 08:00 .. race start'}, 'surfaces': []}
    if not page or page['turf_going'] is None:
        print('no official going page for', track, day, '- nothing saved'); return
    else:
        g = {'turf': sd.GOING[page['turf_going']], 'dirt': sd.GOING[page['dirt_going']]}
        m = {'turf': np.nanmean([page['moist_turf_goal'] or np.nan, page['moist_turf_4c'] or np.nan]),
             'dirt': np.nanmean([page['moist_dirt_goal'] or np.nan, page['moist_dirt_4c'] or np.nan])}
        rec['status'] = 'ok'; rec['official_page'] = page
        for s, o in (('turf', 'dirt'), ('dirt', 'turf')):
            info = {'morning': g[s], 'morning_other': g[o], 'moist0': float(m[s])}
            rows = build_rows(track, day, s, info, labels, obs, W, sched)
            P2 = predict_probs(models, rows, s)
            P5, pw = forecast_predictions(track, day, s, rows, info, m5, None, pops)
            Pb = baseline_matrix(tf, s)[int(info['morning'])]
            first = rows.iloc[0]
            extra = {'probs_no_forecast': [{'race_no': int(n), **{GOING_JA[i]: round(float(p[i]), 4) for i in range(4)}} for n, p in zip(rows.race_no, P2)],
                     'probs_morning_persists': {GOING_JA[i]: round(float(Pb[i]), 4) for i in range(4)},
                     'p_wet_after_morning': [round(float(x), 4) if x == x else None for x in pw],
                     'inputs': {k: (None if first.get(k) != first.get(k) else float(first.get(k))) for k in ('last_going', 'heavy_share', 'gap_prev_day', 'moist_prev', 'moist0', 'morning', 'morning_other', 'p_prev1', 'p_prev2_3', 'p_night')}}
            rec['surfaces'].append(result_record(track, day, s, info, rows, P5 if P5 is not None else P2, 'official morning page', extra))
    import os; os.makedirs(out_dir, exist_ok=True)
    f = f'{out_dir}/{day.isoformat()}_{track}.json'
    json.dump(rec, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print('saved', f, rec['status'])


def run_replay(track, day):
    """Offline check on a past day: official morning = the first race's going; weather from local history."""
    labels, obs = load_context()
    models = fit_models(training_frame(before=day))
    W = sd.load_weather('weather')
    sched = typical_schedule(labels, track, day)
    today = labels[(labels.track == track) & (labels.date == pd.Timestamp(day))]
    out = []
    first = {s: today[today.surface == s].sort_values('race_no').going_n.iloc[0] for s in ('turf', 'dirt') if (today.surface == s).any()}
    for s, o in (('turf', 'dirt'), ('dirt', 'turf')):
        if s not in first: continue
        o_g = first.get(o, np.nan)
        om = obs[(obs.track == track) & (obs.date == pd.Timestamp(day))]
        mo = float(om['turf_m' if s == 'turf' else 'dirt_m'].iloc[0]) if len(om) else np.nan
        info = {'morning': float(first[s]), 'morning_other': o_g, 'moist0': mo}
        rows = build_rows(track, day, s, info, labels, obs, W, sched)
        P = predict_probs(models, rows, s)
        act = today[today.surface == s].set_index('race_no').going_n
        for (_, r), p in zip(rows.iterrows(), P):
            a = act.get(int(r.race_no))
            out.append((s, int(r.race_no), GOING_JA[int(p.argmax())], None if a is None else GOING_JA[int(a)], round(float(1 - p[int(first[s])]), 3)))
    return out


def list_today(day, wait_minutes=0):
    """poll until the JRA pages show `day` (the morning notice appears about 09:15 JST) or the time runs out."""
    t0 = time.time()
    while True:
        found = _list_today_once(day)
        if found or time.time() - t0 >= wait_minutes * 60:
            return found
        print('JRA going page is not updated for', day, 'yet; waiting', file=sys.stderr)
        time.sleep(120)


def _list_today_once(day):
    """racecourses that hold racing on `day` according to the JRA going pages (index, index2, index3)."""
    from jra_going_now import parse_going_page
    ro = {v: k for k, v in sd.TRACK_RO.items()}; found = []
    for name in ('index.html', 'index2.html', 'index3.html'):
        try:
            r = requests.get('https://www.jra.go.jp/keiba/baba/' + name, timeout=30, headers={'User-Agent': jw.UA})
            p = parse_going_page(r.content.decode('cp932', errors='replace'))
        except Exception as e:
            print('list_today failed', name, e, file=sys.stderr); continue
        if p.get('date') == day.isoformat() and p.get('venue') in sd.TRACK_RO and sd.TRACK_RO[p['venue']] not in found:
            found.append(sd.TRACK_RO[p['venue']])
    return found


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--track', default=None); ap.add_argument('--date', default=None); ap.add_argument('--replay', default=None)
    ap.add_argument('--list-today', action='store_true'); ap.add_argument('--wait-minutes', type=int, default=0)
    a = ap.parse_args()
    if a.list_today:
        print(json.dumps(list_today(date.fromisoformat(a.date) if a.date else datetime.now(JST).date(), a.wait_minutes)))
        sys.exit(0)
    if not a.track:
        ap.error('--track is required')
    if a.replay:
        for r in run_replay(a.track, date.fromisoformat(a.replay)): print(r)
    else:
        run_live(a.track, date.fromisoformat(a.date) if a.date else datetime.now(JST).date())
