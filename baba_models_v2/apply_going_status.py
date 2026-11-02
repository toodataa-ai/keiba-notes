"""Write stage_b/status_v1.json into model_registry.json as `going_status` (additive; legacy stage_a/stage_b keys untouched)."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent
reg = json.loads((R / 'model_registry.json').read_text(encoding='utf-8'))
st = json.loads((R / 'stage_b/status_v1.json').read_text(encoding='utf-8'))
LABEL = {'usable': '使える見込み', 'waiting_forecast': '予報待ち', 'insufficient': 'まだ足りない'}
for m in reg['models']:
    c = st['cells'].get(m['track'], {}).get(m['surface'])
    if not c: continue
    m['going_status'] = {'state': c['state'], 'label': LABEL[c['state']], 'as_of': st['as_of'],
        'without_forecast': {'logloss_gain_pct': c['G2']['logloss_gain_pct'], 'brier_gain_pct': c['G2']['brier_gain_pct']},
        'perfect_forecast': {'logloss_gain_pct': c['G3']['logloss_gain_pct'], 'brier_gain_pct': c['G3']['brier_gain_pct']},
        'races': c['races'], 'transition_races': c['transition_races'], 'source': 'baba_models_v2/stage_b/status_v1.json'}
reg['updated_at'] = st['as_of'] + 'T08:00:00+09:00'
(R / 'model_registry.json').write_text(json.dumps(reg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print({k: sum(1 for m in reg['models'] if m.get('going_status', {}).get('state') == k) for k in LABEL})
