#!/usr/bin/env python3
"""Official-form race-clock parser and market-independent research signal.
All clock signals are Shadow only: NEVER alter frozen formal STEP1 or betting.
"""
import math
import re
from collections import defaultdict
from datetime import date
from statistics import median

CLOCK = re.compile(r'(?<!\d)(\d{3,4})(芝|ダート|ダ)\s+((?:\d{1,2}:)?[0-5]?\d\.\d)\s+(良|稍重|重|不良)(?=\s|$)')
RACE = re.compile(r'^\d{4}年\d{1,2}月\d{1,2}日\s+\S+\s+(.+?)\s+(?:(?:G[123]|OP|L|[123]勝ク|未勝利|新馬)\s+)?(?:\d+\s*着|中止|取消|除外)')

def seconds(value):
    m = re.fullmatch(r'(?:(\d{1,2}):)?([0-5]?\d)\.(\d)', value or '')
    return int(m[1] or 0)*60 + int(m[2]) + int(m[3])/10 if m else None

def official_clock(source, distance_m, surface, finish):
    if finish is None or not isinstance(source,str): return None
    matches = []
    for m in CLOCK.finditer(source):
        if int(m[1]) == distance_m and ('芝' if m[2]=='芝' else 'ダート') == surface:
            matches.append((m[3],m[4]))
    if len(matches)>1: raise ValueError('ambiguous race clock')
    return matches[0] if matches else None

def recover(past):
    out = dict(past)
    found = official_clock(out.get('source_excerpt'),out.get('distance_m'),out.get('surface'),out.get('finish'))
    if found:
        if out.get('time') and out['time']!=found[0]:
            raise ValueError('source clock conflicts with preserved clock')
        out['time']=found[0]
        out['going_at_run']=found[1]
        out['clock_provenance']='official_source_excerpt'
    elif out.get('time'):
        if seconds(out['time']) is None: raise ValueError('invalid previously parsed race clock')
    elif out.get('finish') is not None:
        raise ValueError('completed race is missing verifiable clock: '+str(out.get('source_excerpt','')[:120]))
    return out

def shadow_signal(runners,target_date):
    """Only same historical named event, date, venue, surface, distance and going.
    >=3 *different horses* of the target race needed. No cross-day absolute comparison.
    """
    groups=defaultdict(list)
    for horse in runners:
        for p in horse.get('past_performances',[]):
            s=seconds(p.get('time'))
            event=RACE.search(p.get('source_excerpt') or '')
            clock=official_clock(p.get('source_excerpt'),p.get('distance_m'),p.get('surface'),p.get('finish'))
            going=p.get('going_at_run') or (clock[1] if clock else None)
            if s is None or not event or not going or not p.get('date') or not p.get('course') or not p.get('distance_m'):
                continue
            if p['date']>=target_date:
                raise ValueError('future/target race result forbidden in clock signal')
            key=(p['date'],p['course'],p['distance_m'],p['surface'],going,event[1])
            groups[key].append((horse['horse_number'],s))
    signals=defaultdict(list)
    events=[]
    for key,rows in sorted(groups.items()):
        if len(rows)<3 or len({number for number,_ in rows})!=len(rows): continue
        m=median(v for _,v in rows)
        age=(date.fromisoformat(target_date)-date.fromisoformat(key[0])).days
        weight=math.exp(-max(0,age)/90)
        keytext='|'.join(map(str,key))
        events.append({'historical_event':keytext,'observed_horses':len(rows),'median_seconds':round(m,3)})
        for number,value in rows:
            diff=max(-1.5,min(1.5,(m-value)*1000/key[2]))
            signals[number].append((weight,diff,keytext))
    horses=[]
    for h in sorted(runners,key=lambda x:x['horse_number']):
        arr=signals[h['horse_number']]
        score=sum(w*v for w,v,_ in arr)/sum(w for w,_,_ in arr) if arr else None
        horses.append({'horse_number':h['horse_number'],'horse_name':h['horse_name'],
                       'immutable_mark':h['mark'],'immutable_grade':h['overall_grade'],
                       'historical_comparisons':len(arr),
                       'relative_seconds_per_1000m':round(score,4) if score is not None else None,
                       'events':[key for _,_,key in arr]})
    return {'schema_version':1,'mode':'SHADOW_ONLY','production_effect':False,
            'formal_marks_changed':False,'formal_bets_changed':False,
            'validation_status':'UNVALIDATED_NOT_FOR_PROMOTION',
            'method':'same-historical-event-median-residual-with-90-day-decay',
            'limits':'Subset of target entrants, not full race par; no calibrated weight/class or going adjustment. Never compare different event clocks.',
            'events':events,'horses':horses}
