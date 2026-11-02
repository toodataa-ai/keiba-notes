"""Stage B experiment: how well can the race-time going be predicted from what is known by the morning?

Forward evaluation: each test year Y (2023..2026) is predicted by a model trained on years < Y only.
Feature sets are nested so each step shows what the new information adds.
Race-day weather is the *actual* weather (stand-in for a perfect forecast) -> upper bound.
"""
import argparse, json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

CLASSES = [0, 1, 2, 3]
BASE = ['month_sin', 'month_cos']
PREV = ['last_going', 'heavy_share', 'gap_prev_day', 'moist_prev']
MORNING = ['moist0']
WX = ['p_prev1', 'p_prev2_3', 'p_night', 'p_day', 'p_before_start', 'p_3h_before', 't_start', 'h_start', 'w_start',
      't_prev', 'h_prev', 'sun_prev', 'sun_before', 'start_h', 'race_no']
MORNING_WX = ['p_prev1', 'p_prev2_3', 'p_night', 't_prev', 'h_prev', 'sun_prev']   # observed by ~6 a.m. of the race day
COURSE_CAT = ['rail', 'turf_course']
COURSE_NUM = ['distance_m']
SETS = {
    'F0 競馬場・季節だけ': (BASE, []),
    'F1 +前日の馬場（含水率・公式の馬場状態）': (BASE + PREV, []),
    'F2 +当日朝の含水率': (BASE + PREV + MORNING, []),
    'F3a +前日〜当日早朝の実測気象（予報なしで使える）': (BASE + PREV + MORNING + MORNING_WX + ['start_h', 'race_no'], []),
    'F3 +気象（前日・当日の降水/気温/湿度）': (BASE + PREV + MORNING + WX, []),
    'F4 +コース（内外・A〜D・距離）': (BASE + PREV + MORNING + WX + COURSE_NUM, COURSE_CAT),
    'W 気象のみ（含水率なし）': (BASE + PREV + WX, []),
}


def design(df, nums, cats, columns=None):
    X = df[nums + cats].copy()
    X['track'] = df['track']
    X = pd.get_dummies(X, columns=['track'] + cats, dtype=float)
    if columns is not None:
        X = X.reindex(columns=columns, fill_value=0.0)
    return X


def fit_predict(train, test, nums, cats, seed=0):
    Xtr = design(train, nums, cats)
    Xte = design(test, nums, cats, Xtr.columns)
    m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
                                       min_samples_leaf=30, random_state=seed)
    m.fit(Xtr, train['going_n'])
    P = np.zeros((len(test), 4))
    for j, c in enumerate(m.classes_):
        P[:, CLASSES.index(c)] = m.predict_proba(Xte)[:, j]
    P = np.clip(P, 1e-6, 1); return P / P.sum(axis=1, keepdims=True)


def metrics(y, P):
    y = np.asarray(y)
    ll = -np.log(P[np.arange(len(y)), y]).mean()
    oh = np.eye(4)[y]
    brier = ((P - oh) ** 2).sum(axis=1).mean()
    acc = (P.argmax(axis=1) == y).mean()
    out = {'n': int(len(y)), 'logloss': float(ll), 'brier': float(brier), 'acc': float(acc)}
    pb = P[:, 1:].sum(axis=1); yb = (y >= 1).astype(int)
    out['auc_heavy'] = float(roc_auc_score(yb, pb)) if 0 < yb.sum() < len(yb) else None
    return out


def boot_diff(day_keys, l0, l1, n=1000, seed=0):
    """block bootstrap over race days: mean(l1-l0) with 95% interval (negative = l1 better)."""
    d = pd.DataFrame({'k': day_keys, 'd': np.asarray(l1) - np.asarray(l0)}).groupby('k')['d'].agg(['sum', 'count'])
    rng = np.random.default_rng(seed); idx = np.arange(len(d)); s = d['sum'].values; c = d['count'].values
    vals = []
    for _ in range(n):
        b = rng.choice(idx, len(idx)); vals.append(s[b].sum() / c[b].sum())
    return float(s.sum() / c.sum()), float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='stage_b/stage_b_dataset.csv.gz')
    ap.add_argument('--out', default='stage_b/experiment_v1.json')
    ap.add_argument('--test-years', default='2023,2024,2025,2026')
    a = ap.parse_args(argv)
    df = pd.read_csv(a.data, parse_dates=['date'])
    years = [int(x) for x in a.test_years.split(',')]
    result = {'sets': {}, 'by_track_surface': {}, 'notes': 'forward evaluation; weather = actual (perfect-forecast stand-in)'}
    per_race = {}
    for surface in ('turf', 'dirt'):
        d = df[df.surface == surface].reset_index(drop=True)
        for name, (nums, cats) in SETS.items():
            P_all, rows = [], []
            for y in years:
                tr, te = d[d.year < y], d[d.year == y]
                P = fit_predict(tr, te, nums, cats); P_all.append(P); rows.append(te)
            te = pd.concat(rows); P = np.vstack(P_all)
            per_race[(surface, name)] = (te, P)
            result['sets'].setdefault(name, {})[surface] = metrics(te['going_n'], P)
    # gains by step (turf/dirt pooled) with day-block bootstrap
    names = list(SETS)
    steps = [('F0 競馬場・季節だけ', 'F1 +前日の馬場（含水率・公式の馬場状態）'), ('F1 +前日の馬場（含水率・公式の馬場状態）', 'F2 +当日朝の含水率'),
             ('F2 +当日朝の含水率', 'F3a +前日〜当日早朝の実測気象（予報なしで使える）'),
             ('F3a +前日〜当日早朝の実測気象（予報なしで使える）', 'F3 +気象（前日・当日の降水/気温/湿度）'),
             ('F2 +当日朝の含水率', 'F3 +気象（前日・当日の降水/気温/湿度）'), ('F3 +気象（前日・当日の降水/気温/湿度）', 'F4 +コース（内外・A〜D・距離）'),
             ('F2 +当日朝の含水率', 'W 気象のみ（含水率なし）')]
    result['steps'] = []
    for s0, s1 in steps:
        rec = {'from': s0, 'to': s1}
        for surface in ('turf', 'dirt'):
            te0, P0 = per_race[(surface, s0)]; te1, P1 = per_race[(surface, s1)]
            y = te0['going_n'].values
            l0 = -np.log(P0[np.arange(len(y)), y]); l1 = -np.log(P1[np.arange(len(y)), y])
            keys = te0['track'] + te0['date'].dt.strftime('%Y%m%d')
            m, lo, hi = boot_diff(keys.values, l0, l1)
            rec[surface] = {'logloss_change': m, 'ci95': [lo, hi], 'relative_pct': 100 * m / float(l0.mean())}
        result['steps'].append(rec)
    # per track x surface: F2 vs F3 vs F4 log loss
    for surface in ('turf', 'dirt'):
        te2, P2 = per_race[(surface, names[2])]; _, Pa = per_race[(surface, names[3])]; te3, P3 = per_race[(surface, names[4])]; te4, P4 = per_race[(surface, names[5])]
        for tr in sorted(te2['track'].unique()):
            msk = (te2['track'] == tr).values
            y = te2['going_n'].values[msk]
            if len(y) < 150: continue
            def ll(P): return float(-np.log(P[msk][np.arange(msk.sum()), y]).mean())
            result['by_track_surface'][f'{tr}/{surface}'] = {'n': int(msk.sum()), 'heavy_rate': float((y >= 1).mean()),
                                                              'F2': ll(P2), 'F3a': ll(Pa[msk]) if False else float(-np.log(Pa[msk][np.arange(msk.sum()), y]).mean()), 'F3': ll(P3), 'F4': ll(P4)}
    json.dump(result, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('== 全体（2023〜2026を未来として評価）')
    for name in names:
        r = result['sets'][name]
        print(f"{name:34s} 芝 logloss {r['turf']['logloss']:.3f} acc {r['turf']['acc']:.3f} auc {r['turf']['auc_heavy']:.3f} | ダ logloss {r['dirt']['logloss']:.3f} acc {r['dirt']['acc']:.3f} auc {r['dirt']['auc_heavy']:.3f}")
    print('== 追加の効果（logloss変化。負＝良くなった）')
    for s in result['steps']:
        print(s['from'][:2], '→', s['to'][:2], '芝', f"{s['turf']['logloss_change']:+.4f} {tuple(round(x,4) for x in s['turf']['ci95'])}", 'ダ', f"{s['dirt']['logloss_change']:+.4f} {tuple(round(x,4) for x in s['dirt']['ci95'])}")
    print('== 競馬場×芝ダ（F2→F3→F4 logloss）')
    for k, v in result['by_track_surface'].items():
        print(f"{k:14s} n={v['n']:5d} 重以上率={v['heavy_rate']:.2f}  F2 {v['F2']:.3f} F3a {v['F3a']:.3f} F3 {v['F3']:.3f} F4 {v['F4']:.3f}")


if __name__ == '__main__':
    main()
