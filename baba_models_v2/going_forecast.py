"""JMA forecast helpers for the race-day going prediction.

The forecast gives the probability of >= 1 mm precipitation per 6-hour block (06-12, 12-18, ...).
We use it as P(rain after the morning official announcement and before the race starts) and mix two
model outputs (rain / no rain after the morning).  The mixing rule is an approximation; its calibration is
measured later from the archived forecasts (forecast_archive/).
"""
from datetime import date, timedelta

# forecast sub-area used for each racecourse (code from JMA area.json)
AREA = {'sapporo': '016010', 'hakodate': '017010', 'fukushima': '070010', 'niigata': '150010', 'chukyo': '230010',
        'kokura': '400020', 'tokyo': '130010', 'nakayama': '120010', 'kyoto': '260010', 'hanshin': '280010'}
MORNING_H = 8.0   # official going is announced by about 08:00; rain after that is what the morning notice cannot know


def parse_pops(fc_data, track, day):
    """fc_data: JMA forecast JSON (list of reports).  -> {'06-12':p,'12-18':p,'18-24':p,'report':str} in 0..1, or None."""
    code = AREA[track]
    for rep in fc_data:                       # [0] is the short-range forecast (latest, includes today's blocks)
        for ts in rep.get('timeSeries', []):
            for a in ts.get('areas', []):
                if a.get('area', {}).get('code') != code or 'pops' not in a:
                    continue
                out = {}
                for t, p in zip(ts['timeDefines'], a['pops']):
                    if p in ('', None) or not t.startswith(day.isoformat()):
                        continue
                    hh = int(t[11:13])
                    key = {6: '06-12', 12: '12-18', 18: '18-24', 0: '00-06'}.get(hh)
                    if key:
                        out[key] = float(p) / 100.0
                if '06-12' in out or '12-18' in out:
                    out['report'] = rep.get('reportDatetime')
                    return out
    return None


def p_wet_after_morning(pops, start_h):
    """P(>= 1 mm of rain between the morning announcement and the race start), from block probabilities.
    Each block probability is spread evenly over its hours:  P(no rain in a window) = prod (1-p)^(overlap/6)."""
    if not pops:
        return None
    blocks = (('06-12', 6.0, 12.0), ('12-18', 12.0, 18.0), ('18-24', 18.0, 24.0))
    keep = 1.0
    for k, a, b in blocks:
        if k not in pops:
            continue
        lo, hi = max(a, MORNING_H), min(b, start_h)
        ov = max(0.0, hi - lo)
        if ov > 0:
            keep *= (1.0 - min(0.999, pops[k])) ** (ov / (b - a))
    return float(1.0 - keep)
