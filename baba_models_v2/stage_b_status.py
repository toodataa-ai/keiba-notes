"""Per track x surface status of 'predict the race-time going' vs the current rule (morning going persists).
States: usable (works without forecasts) / waiting_forecast (works only if the weather forecast is right) / insufficient.
Criteria follow promotion_policy.json: >=5% better log loss AND Brier, rain-transition Brier not >10% worse,
>=80 races, >=12 meeting days, >=2 years, >=6 rain-transition days. Forward test 2023-2026 (train on earlier years only)."""
import json, numpy as np, pandas as pd
import stage_b_model_v2 as M   # builds features and trains; reuse its predictions

def main():
    df = M.df
    cells = {}
    for surface in ('turf', 'dirt'):
        d = df[df.surface == surface].reset_index(drop=True); parts = []
        for y in (2023, 2024, 2025, 2026):
            tr, te = d[d.year < y], d[d.year == y].copy()
            C = np.ones((4, 4))
            for m, a in zip(tr.morning, tr.going_n): C[m, a] += 1
            C /= C.sum(1, keepdims=True); te['P_base'] = list(C[te.morning.values])
            for k in ('G2', 'G3'):
                n, c = M.SETS[[s for s in M.SETS if s.startswith(k)][0]]; te['P_' + k] = list(M.fit(tr, te, n, c))
            parts.append(te)
        t = pd.concat(parts); t = t[~t.is_ref]
        for track, g in t.groupby('track'):
            y = g.going_n.values; oh = np.eye(4)[y]
            def ll(P): return float(-np.log(P[np.arange(len(y)), y]).mean())
            def br(P, mk=None):
                b = ((P - oh) ** 2).sum(1); return float(b.mean() if mk is None else b[mk].mean())
            P = {k: np.vstack(g['P_' + k].values) for k in ('base', 'G2', 'G3')}
            tr_mk = g.trans.values
            info = {'races': int(len(g)), 'meeting_days': int(g.date.nunique()), 'years': int(g.year.nunique()),
                    'transition_races': int(tr_mk.sum()), 'transition_days': int(g[g.trans].date.nunique())}
            for k in ('base', 'G2', 'G3'):
                info[k] = {'logloss': ll(P[k]), 'brier': br(P[k]), 'brier_transition': br(P[k], tr_mk) if tr_mk.any() else None}
            def passes(k):
                b = info['base']; m = info[k]
                ok_n = info['races'] >= 80 and info['meeting_days'] >= 12 and info['years'] >= 2 and info['transition_days'] >= 6
                imp_ll = 100 * (b['logloss'] - m['logloss']) / b['logloss']; imp_br = 100 * (b['brier'] - m['brier']) / b['brier']
                tr_ok = m['brier_transition'] is not None and m['brier_transition'] <= 1.10 * b['brier_transition']
                return ok_n and imp_ll >= 5 and imp_br >= 5 and tr_ok, round(imp_ll, 1), round(imp_br, 1)
            for k in ('G2', 'G3'):
                okk, a, b = passes(k); info[k]['pass'] = bool(okk); info[k]['logloss_gain_pct'] = a; info[k]['brier_gain_pct'] = b
            info['state'] = 'usable' if info['G2']['pass'] else ('waiting_forecast' if info['G3']['pass'] else 'insufficient')
            cells.setdefault(track, {})[surface] = info
    out = {'schema_version': 1, 'as_of': '2026-11-03', 'test_years': [2023, 2024, 2025, 2026], 'cells': cells,
           'notes': ['G2=予報なし（朝の馬場・含水率・前日〜早朝の実測天気）、G3=天気が完全に当たった場合（上限）',
                     '朝の馬場状態は、その日最初のレースの馬場で代用（朝の公式発表は保存開始前のため）',
                     '予報は保存開始（2026-11-03）後、実データで測り直す']}
    json.dump(out, open('stage_b/status_v1.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ja = {'sapporo':'札幌','hakodate':'函館','fukushima':'福島','niigata':'新潟','tokyo':'東京','nakayama':'中山','chukyo':'中京','kyoto':'京都','hanshin':'阪神','kokura':'小倉'}
    for t, v in cells.items():
        print(ja[t], *(f"{s}:{v[s]['state']}(G2 ll{v[s]['G2']['logloss_gain_pct']:+} br{v[s]['G2']['brier_gain_pct']:+} / G3 ll{v[s]['G3']['logloss_gain_pct']:+} br{v[s]['G3']['brier_gain_pct']:+}; trans n{v[s]['transition_races']})" for s in ('turf','dirt')))

if __name__ == '__main__':
    main()
