"""Stage B baseline: 'the going announced in the morning persists all day' vs the models.
Morning going proxy = official going of the first race of the day on that surface (race ~9:50; the official
morning notice is slightly earlier, so this is a mild advantage for the baseline). The reference race itself
is excluded from scoring. Baseline probabilities = confusion matrix of training years (Laplace-smoothed)."""
import json, numpy as np, pandas as pd
from stage_b_experiment import SETS, fit_predict, metrics

df = pd.read_csv('stage_b/stage_b_dataset.csv.gz', parse_dates=['date'])
df = df.sort_values(['track', 'date', 'surface', 'race_no']).reset_index(drop=True)
g = df.groupby(['track', 'date', 'surface'])
df['morning'] = g['going_n'].transform('first')
df['is_ref'] = g.cumcount() == 0
df['trans'] = g['going_n'].transform('nunique') > 1          # going changed during the day
names = {'F2': 'F2 +当日朝の含水率', 'F3a': 'F3a +前日〜当日早朝の実測気象（予報なしで使える）', 'F3': 'F3 +気象（前日・当日の降水/気温/湿度）'}
out = {}
rows = []
for surface in ('turf', 'dirt'):
    d = df[df.surface == surface].reset_index(drop=True)
    parts = []
    for y in (2023, 2024, 2025, 2026):
        tr, te = d[d.year < y], d[d.year == y].copy()
        C = np.ones((4, 4))
        for m, a in zip(tr.morning, tr.going_n): C[m, a] += 1
        C /= C.sum(axis=1, keepdims=True)
        te['P_base'] = list(C[te.morning.values])
        for k, nm in names.items():
            nums, cats = SETS[nm]; te['P_' + k] = list(fit_predict(tr, te, nums, cats))
        parts.append(te)
    t = pd.concat(parts); t = t[~t.is_ref]
    y = t.going_n.values
    def stack(c): return np.vstack(t[c].values)
    def adj(P): return float((np.abs(P.argmax(1) - y) <= 1).mean())
    for label, msk in (('全レース', np.ones(len(t), bool)), ('途中で馬場が変わった日', t.trans.values), ('変わらなかった日', ~t.trans.values)):
        for c in ('P_base', 'P_F2', 'P_F3a', 'P_F3'):
            P = stack(c)[msk]; yy = y[msk]
            m = metrics(yy, P); m['adjacent_acc'] = float((np.abs(P.argmax(1) - yy) <= 1).mean())
            out.setdefault(surface, {}).setdefault(label, {})[c[2:]] = m
        out[surface][label]['n'] = int(msk.sum())
        out[surface][label]['day_share'] = float(t.trans.mean()) if label == '全レース' else None
json.dump(out, open('stage_b/baseline_v1.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for s in out:
    for lab, v in out[s].items():
        print(s, lab, 'n=', v['n'])
        for k in ('base', 'F2', 'F3a', 'F3'):
            m = v[k]; print(f"  {k:5s} logloss {m['logloss']:.3f} brier {m['brier']:.3f} acc {m['acc']:.3f} adj {m['adjacent_acc']:.3f}")
