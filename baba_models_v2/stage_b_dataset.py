"""Stage B dataset: one row per race, features known by the morning of the race day.

Target  : official going of that race (0 良 / 1 稍重 / 2 重 / 3 不良), per surface.
Inputs  : previous official going, morning moisture, hourly JMA weather, course (in/out, A-D).
Race-day weather uses what actually happened (stand-in for a perfect forecast, because past
forecasts are not archived) - results are therefore an upper bound for the weather part.
"""
import argparse, glob
import numpy as np
import pandas as pd

import jma_weather as jw

TRACK_RO = {'札幌': 'sapporo', '函館': 'hakodate', '福島': 'fukushima', '新潟': 'niigata', '東京': 'tokyo',
            '中山': 'nakayama', '中京': 'chukyo', '京都': 'kyoto', '阪神': 'hanshin', '小倉': 'kokura'}
GOING = {'良': 0, '稍重': 1, '重': 2, '不良': 3}


def load_labels(d='going_labels'):
    df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(d + '/jra_going_20*.csv'))], ignore_index=True)
    df['track'] = df['track'].map(TRACK_RO)
    df['surface'] = df['surface'].map({'芝': 'turf', 'ダート': 'dirt'})
    df['going_n'] = df['going'].map(GOING)
    df['date'] = pd.to_datetime(df['date'])
    t = df['start_time'].str.split(':', expand=True).astype(float)
    df['start_h'] = t[0] + t[1] / 60
    cd = df['course_detail'].fillna('')
    df['rail'] = np.select([cd.str.contains('外内|内外'), cd.str.contains('外'), cd.str.contains('内'), cd.str.contains('直')],
                           ['both', 'out', 'in', 'straight'], default='plain')
    return df


def load_course(d='going_labels'):
    c = pd.read_csv(d + '/turf_course_by_day.csv')
    c['track'] = c['track'].map(TRACK_RO)
    return c[['year', 'track', 'kai', 'nichime', 'turf_course']]


def load_obs(d='observations'):
    o = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(d + '/*_observations.csv'))], ignore_index=True)
    o['date'] = pd.to_datetime(o['observed_date'])
    o['turf_m'] = o[['turf_goal', 'turf_corner']].mean(axis=1)
    o['dirt_m'] = o[['dirt_goal', 'dirt_corner']].mean(axis=1)
    return o[['track', 'date', 'turf_m', 'dirt_m', 'cushion_value', 'course']].rename(columns={'course': 'course_obs'})


def load_weather(d='weather'):
    w = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(d + '/jma_hourly_*.csv'))], ignore_index=True)
    w['date'] = pd.to_datetime(w['observed_date'])
    return w


def wx_series(w, station, col):
    s = w[w.station == station]
    return s.pivot_table(index='date', columns='hour', values=col, aggfunc='first')


def weather_features(track, race_days, w, starts):
    """race_days: list of dates; starts: DataFrame(date,start_h) -> per-race features."""
    ts = jw.TRACK_STATIONS[track]
    rp, rs, full, hum = ts['rain_primary'], ts['rain_secondary'], ts['full'], jw.HUMIDITY_STATION[track]
    P = wx_series(w, rp, 'precipitation_mm')
    if rs:
        P = P.combine_first(wx_series(w, rs, 'precipitation_mm'))
    T = wx_series(w, full, 'temperature_c'); W = wx_series(w, full, 'wind_mps'); S = wx_series(w, full, 'sunshine_hours')
    H = wx_series(w, hum, 'humidity_pct')
    one = pd.Timedelta(days=1)
    out = []

    def tot(x):
        return x.sum(min_count=1) if len(x) else np.nan

    for date_, h in zip(starts['date'], starts['start_h']):
        def day(M, d):
            return M.loc[d] if d in M.index else pd.Series(dtype=float)
        p0, p1, p2, p3 = day(P, date_), day(P, date_ - one), day(P, date_ - 2 * one), day(P, date_ - 3 * one)
        hh = int(np.ceil(h)) if h == h else 12          # hour index whose interval contains the start
        before = p0[[c for c in p0.index if c <= hh]].sum(min_count=1) if len(p0) else np.nan
        last3 = p0[[c for c in p0.index if hh - 3 < c <= hh]].sum(min_count=1) if len(p0) else np.nan
        night = (p1[[c for c in p1.index if c >= 19]].sum(min_count=1) if len(p1) else np.nan)
        night = np.nansum([night, p0[[c for c in p0.index if c <= 6]].sum(min_count=1) if len(p0) else np.nan]) if (len(p1) or len(p0)) else np.nan
        t0, h0, w0 = day(T, date_), day(H, date_), day(W, date_)
        out.append({
            'p_prev1': tot(p1), 'p_prev2_3': (np.nan if np.isnan(tot(p2)) and np.isnan(tot(p3)) else np.nansum([tot(p2), tot(p3)])), 'p_night': night,
            'p_day': tot(p0), 'p_before_start': before, 'p_3h_before': last3,
            't_start': t0.get(hh, np.nan), 'h_start': h0.get(hh, np.nan), 'w_start': w0.get(hh, np.nan),
            't_prev': day(T, date_ - one).mean(), 'h_prev': day(H, date_ - one).mean(),
            'sun_prev': day(S, date_ - one).sum(min_count=1), 'sun_before': day(S, date_)[[c for c in day(S, date_).index if c <= hh]].sum(min_count=1),
        })
    return pd.DataFrame(out, index=starts.index)


def build(labels_dir='going_labels', obs_dir='observations', wx_dir='weather'):
    L = load_labels(labels_dir); C = load_course(labels_dir); O = load_obs(obs_dir); W = load_weather(wx_dir)
    L['year'] = L['date'].dt.year
    L = L.merge(C, how='left', on=['year', 'track', 'kai', 'nichime'])
    L.loc[L['surface'] == 'dirt', 'turf_course'] = np.nan
    L['turf_course'] = L['turf_course'].fillna('NA')
    # morning moisture on the race day and the latest earlier measurement
    O = O.sort_values(['track', 'date'])
    L = L.merge(O.rename(columns={'turf_m': 'turf_m0', 'dirt_m': 'dirt_m0'}), how='left', on=['track', 'date'])
    prev = O.rename(columns={'date': 'date_prev', 'turf_m': 'turf_mp', 'dirt_m': 'dirt_mp'})[['track', 'date_prev', 'turf_mp', 'dirt_mp']]
    L['date_key'] = L['date']
    L = L.sort_values('date')
    prev = prev.sort_values('date_prev')
    L = pd.merge_asof(L, prev.assign(date_key=prev['date_prev'] + pd.Timedelta(days=1)).sort_values('date_key'),
                      on='date_key', by='track', direction='backward', tolerance=pd.Timedelta(days=5))
    L['moist0'] = np.where(L['surface'] == 'turf', L['turf_m0'], L['dirt_m0'])
    L['moist_prev'] = np.where(L['surface'] == 'turf', L['turf_mp'], L['dirt_mp'])
    # previous race day's last official going on the same surface
    last = (L.sort_values(['track', 'surface', 'date', 'race_no']).groupby(['track', 'surface', 'date'])
              .agg(last_going=('going_n', 'last'), heavy_share=('going_n', lambda s: (s >= 1).mean())).reset_index())
    last = last.rename(columns={'date': 'date_pd'})
    last['date_key'] = last['date_pd'] + pd.Timedelta(days=1)
    L = L.sort_values('date_key')
    last = last.sort_values('date_key')
    L = pd.merge_asof(L, last, on='date_key', by=['track', 'surface'], direction='backward', tolerance=pd.Timedelta(days=4))
    L['gap_prev_day'] = (L['date'] - L['date_pd']).dt.days
    L = L.sort_values(['date', 'track', 'race_no']).reset_index(drop=True)
    # weather
    parts = []
    for tr, g in L.groupby('track'):
        parts.append(weather_features(tr, None, W, g[['date', 'start_h']]))
    L = L.join(pd.concat(parts))
    L['month'] = L['date'].dt.month
    L['month_sin'] = np.sin(2 * np.pi * L['month'] / 12); L['month_cos'] = np.cos(2 * np.pi * L['month'] / 12)
    keep = ['date', 'year', 'track', 'surface', 'kai', 'nichime', 'race_no', 'start_h', 'rail', 'turf_course', 'distance_m',
            'going_n', 'moist0', 'moist_prev', 'last_going', 'heavy_share', 'gap_prev_day', 'cushion_value',
            'p_prev1', 'p_prev2_3', 'p_night', 'p_day', 'p_before_start', 'p_3h_before', 't_start', 'h_start', 'w_start',
            't_prev', 'h_prev', 'sun_prev', 'sun_before', 'month_sin', 'month_cos']
    return L[keep]


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='stage_b/stage_b_dataset.csv.gz')
    a = ap.parse_args()
    df = build(); df.to_csv(a.out, index=False)
    print(len(df), 'rows ->', a.out)
    print(df.isna().mean().round(3).to_string())
