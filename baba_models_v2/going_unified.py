"""All-racecourse going model that takes the day's weather as a *rain scenario* (rain after the morning: yes / no).

Training uses the observed precipitation between 08:00 and the race start (>= 1 mm = wet).  At prediction time the forecast
probability P(wet) (going_forecast.p_wet_after_morning) mixes the two scenario predictions:
      P(going) = P(wet) * P(going | wet) + (1 - P(wet)) * P(going | dry)
One pooled model per surface (racecourse is an input), so every racecourse gets a prediction.
"""
import json, sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

import jma_weather as jw
import stage_b_dataset as sd
from stage_b_experiment import BASE, PREV, MORNING, MORNING_WX, design, metrics

MOR = ['morning', 'morning_other', 'hours_since_ref']
NUMS0 = BASE + PREV + MORNING + MORNING_WX + ['start_h', 'race_no'] + MOR      # G2 (no weather after the morning)
NUMS5 = NUMS0 + ['wet']                                                        # G5 (+ rain scenario after the morning)


def rain_after_morning(track, W, starts, since=8.0):
    """observed precipitation (mm) between `since` (hour of day) and the race start."""
    ts = jw.TRACK_STATIONS[track]
    P = sd.wx_series(W, ts['rain_primary'], 'precipitation_mm')
    if ts['rain_secondary']:
        P = P.combine_first(sd.wx_series(W, ts['rain_secondary'], 'precipitation_mm'))
    out = []
    for d, h in zip(starts['date'], starts['start_h']):
        if d not in P.index or h != h:
            out.append(np.nan); continue
        hh = int(np.ceil(h)); row = P.loc[d]
        cols = [c for c in row.index if since < c <= hh]
        out.append(row[cols].sum(min_count=1) if cols else np.nan)
    return pd.Series(out, index=starts.index)


def add_morning_cols(df):
    df = df.sort_values(['track', 'date', 'surface', 'race_no']).reset_index(drop=True)
    g = df.groupby(['track', 'date', 'surface'])
    df['morning'] = g['going_n'].transform('first'); df['is_ref'] = g.cumcount() == 0
    df['trans'] = g['going_n'].transform('nunique') > 1
    oth = df[df.is_ref].pivot_table(index=['track', 'date'], columns='surface', values='going_n')
    df = df.join(oth.rename(columns={'turf': 'm_turf', 'dirt': 'm_dirt'}), on=['track', 'date'])
    df['morning_other'] = np.where(df.surface == 'turf', df.m_dirt, df.m_turf)
    df['hours_since_ref'] = df.start_h - g['start_h'].transform('first')
    return df


def training_frame(path='stage_b/stage_b_dataset.csv.gz', wx_dir='weather'):
    df = add_morning_cols(pd.read_csv(path, parse_dates=['date']))
    W = sd.load_weather(wx_dir)
    df['rain_mm'] = np.nan
    for tr, g in df.groupby('track'):
        df.loc[g.index, 'rain_mm'] = rain_after_morning(tr, W, g[['date', 'start_h']]).values
    df['wet'] = (df['rain_mm'] >= 1.0).astype(float)
    df.loc[df['rain_mm'].isna(), 'wet'] = 0.0
    return df


def fit(d, nums):
    X = design(d, nums, [])
    m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
                                       min_samples_leaf=30, random_state=0).fit(X, d.going_n)
    return m, X.columns


def proba(model, rows, nums):
    m, cols = model
    X = design(rows, nums, [], cols); pr = m.predict_proba(X)
    P = np.zeros((len(rows), 4))
    for j, c in enumerate(m.classes_): P[:, int(c)] = pr[:, j]
    P = np.clip(P, 1e-6, 1); return P / P.sum(1, keepdims=True)


def mixed(model, rows, p_wet):
    """rows without 'wet'; p_wet: scalar or array of P(wet)."""
    a = rows.copy(); a['wet'] = 1.0; b = rows.copy(); b['wet'] = 0.0
    p = np.asarray(p_wet, dtype=float).reshape(-1, 1) * np.ones((len(rows), 1))
    return p * proba(model, a, NUMS5) + (1 - p) * proba(model, b, NUMS5)


def backtest(out='stage_b/unified_v1.json', years=(2023, 2024, 2025, 2026)):
    df = training_frame()
    res = {}
    for surface in ('turf', 'dirt'):
        d = df[df.surface == surface].reset_index(drop=True); parts = []
        for y in years:
            tr, te = d[d.year < y], d[d.year == y].copy()
            C = np.ones((4, 4))
            for m, a in zip(tr.morning, tr.going_n): C[int(m), int(a)] += 1
            C /= C.sum(1, keepdims=True); te['P_base'] = list(C[te.morning.astype(int).values])
            m0 = fit(tr, NUMS0); te['P_G2'] = list(proba(m0, te, NUMS0))
            m5 = fit(tr, NUMS5)
            te['P_G5oracle'] = list(proba(m5, te, NUMS5))                     # forecast always right (upper bound)
            clim = float(tr.wet.mean())                                         # no forecast skill: climatology
            te['P_G5clim'] = list(mixed(m5, te, clim))
            for a_ in (0.5, 0.7):                                              # forecast skill alpha: p = a*actual + (1-a)*clim
                te[f'P_G5a{int(a_*100)}'] = list(mixed(m5, te, a_ * te.wet.values + (1 - a_) * clim))
            parts.append(te)
        t = pd.concat(parts); t = t[~t.is_ref]; y_ = t.going_n.astype(int).values
        cols = ['base', 'G2', 'G5clim', 'G5a50', 'G5a70', 'G5oracle']
        for lab, msk in (('全レース', np.ones(len(t), bool)), ('途中で馬場が変わった日', t.trans.values),
                         ('変わらなかった日', ~t.trans.values), ('雨が降った日（朝以降に1mm以上）', (t.wet == 1).values)):
            r = {'n': int(msk.sum())}
            for c in cols:
                P = np.vstack(t['P_' + c].values)[msk]; r[c] = metrics(y_[msk], P)
            res.setdefault(surface, {})[lab] = r
        for tr_ in sorted(t.track.unique()):
            mk = (t.track == tr_).values
            r = {'n': int(mk.sum())}
            for c in cols:
                P = np.vstack(t['P_' + c].values)[mk]; r[c] = float(-np.log(P[np.arange(mk.sum()), y_[mk]]).mean())
            res[surface].setdefault('競馬場別', {})[tr_] = r
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for s in res:
        for lab in ('全レース', '途中で馬場が変わった日', '雨が降った日（朝以降に1mm以上）'):
            v = res[s][lab]; print(s, lab, v['n'])
            for c in ('base', 'G2', 'G5clim', 'G5a50', 'G5a70', 'G5oracle'):
                m = v[c]; print(f"   {c:9s} ll {m['logloss']:.3f} brier {m['brier']:.3f} acc {m['acc']:.3f}")
    return res


if __name__ == '__main__':
    backtest()
