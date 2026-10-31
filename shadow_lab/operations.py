"""Bridge ordinary morning/evening/research workflows to isolated experiments.

Missing full forecasts never become synthetic historical forecasts. This adapter
uses the existing deterministic weekly sample without selecting by outcome.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from shadow_lab import runtime as rt

def packets(day):
    registry=rt.read(rt.ROOT/'docs/data/races.json')['races']
    candidates=[r for r in registry if r['date']==day and r.get('scope')=='jra-main']
    reports=[]
    for r in candidates:
        path=r.get('e2e_prediction')
        if not path or not rt.safe(path).exists(): continue
        current=rt.read(rt.safe(path))
        base_path=current.get('source_prediction_path') or path
        source=rt.read(rt.safe(base_path))
        # Find the exact original input by reproducing STEP1 and quote snapshots;
        # recovered fresh inputs take priority, but no choice depends on results.
        inputs=[]
        for p in (rt.ROOT/'e2e_validation/inputs').rglob('*.json'):
            try:
                v=rt.read(p)
                if v.get('race_id')==source.get('race_id') and v.get('step1',{}).get('runners')==source.get('step1_ranking'):
                    signature=lambda q:(q['type'],tuple(q['selection']),q.get('observed_at'),q.get('source_url'),json.dumps(q.get('market_odds'),sort_keys=True))
                    quotes={signature(q) for q in v.get('market_quotes',[])}
                    used={signature(q) for s in source.get('purchase_strategy_evaluations',[]) for q in s.get('lines',[]) if q.get('quote_verified')}
                    # Candidate engine performs exact input/output reproduction.
                    inputs.append((len(quotes&used),str(p.relative_to(rt.ROOT))))
            except (ValueError,KeyError): continue
        packet={'baseline_path':base_path,'input_path':sorted(inputs,reverse=True)[0][1] if inputs else 'shadow_lab/missing-input.json',
                'information_cutoff_at':current.get('final_bets_fixed_at',source.get('final_bets_fixed_at')),
                'conditions':{'venue':r['venue'],'surface':source['race_context'].get('surface','unknown'),
                              'rain':'unknown','meeting_week':'unknown'},'features':{}}
        if current.get('purchase_strategy_version'): packet['official_purchase_path']=path
        # Explicit source packets can add pace S/M/H and official going/bias data.
        feature_path=rt.ROOT/'shadow_lab/requests'/day/(r['id']+'.json')
        if feature_path.exists():
            supplied=rt.read(feature_path)
            packet['features'].update(supplied.get('features',{}))
        for plan_path in (rt.ROOT/'experience_regime_v1/collection').glob('*/sample_plan.json'):
            plan=rt.read(plan_path)
            match=[x for x in plan['selected_races'] if x['date']==day and x['venue']==r['venue'] and x['race_no']==source['race_context']['race_no']]
            if not match: continue
            packet['sample_plan_path']=str(plan_path.relative_to(rt.ROOT))
            snapshot=plan_path.parent/'snapshots'/(match[0]['race_id']+'.json')
            if snapshot.exists():
                frozen=rt.read(snapshot); horses=frozen['experience']['horses']
                obs=[h['observed_at'] for h in horses.values()]
                packet['features']['experience']={'path':str(snapshot.relative_to(rt.ROOT)),'sha256':rt.digest(snapshot.read_bytes()),
                    'url':frozen['race_context']['official_source_url'],'observed_at':max(obs),
                    'starts_by_horse':{n:h['starts_before_race'] for n,h in horses.items()}}
        reports.append(packet)
    return reports

def discover(day):
    reports=[]
    for packet in packets(day): reports.extend(rt.prepare(packet))
    # Expose every unserved sampled race, including non-main E0/E1/E2 races.
    # Collection infrastructure can later supply a genuine full-field probability
    # input via requests; experience-only snapshots are never converted to odds.
    missing=[]
    for plan_path in (rt.ROOT/'experience_regime_v1/collection').glob('*/sample_plan.json'):
        for race in rt.read(plan_path)['selected_races']:
            if race['date']!=day: continue
            snapshot=plan_path.parent/'snapshots'/(race['race_id']+'.json')
            groups=set()
            if snapshot.exists():
                frozen=rt.read(snapshot); horse_data=frozen.get('experience',{}).get('horses',{})
                groups={h['regime'] for h in horse_data.values()}
                prediction=rt.ROOT/'experience_regime_v1/step1_frozen'/plan_path.parent.name/(race['race_id']+'.json')
                if prediction.exists() and rt.now()<rt.when(race['start_at']):
                    original=rt.read(prediction)
                    packet={'research_snapshot_path':str(prediction.relative_to(rt.ROOT)),
                            'sample_plan_path':str(plan_path.relative_to(rt.ROOT)),
                            'information_cutoff_at':original['step1_fixed_at'],
                            'features':{'experience':{'path':str(snapshot.relative_to(rt.ROOT)),'sha256':rt.digest(snapshot.read_bytes()),
                                'url':frozen['race_context']['official_source_url'],'observed_at':max(h['observed_at'] for h in horse_data.values()),
                                'starts_by_horse':{n:h['starts_before_race'] for n,h in horse_data.items()}}}}
                    reports.extend(rt.prepare(packet,tuple(sorted(groups))))
                    continue
            for theme in groups or {'E0','E1','E2'}:
                missing.append({'theme':theme,'race_id':race['race_id'],'state':'blocked',
                                'blocker':'full_field_prerace_probabilities_required; fixed_sample_unchanged'})
    if not reports:
        reports=[{'theme':t,'state':'blocked','blocker':'current_official_forecast_or_same_cutoff_input_not_available:'+day} for t in rt.THEMES]
    path=rt.ROOT/rt.DATA/'attempts'/(rt.now().strftime('%Y%m%dT%H%M%S%f')+'-discovery.json')
    rt.dump(path,{'at':rt.now().isoformat(),'day':day,'reports':reports,'sample_gaps':missing},immutable=True)
    return reports

def reconcile():
    """Import canonical official results into Shadow only, never edit originals."""
    imported=[]
    for pair_path in (rt.ROOT/rt.DATA/'pairs').glob('*/*.json'):
        pair=rt.read(pair_path); rid=pair['race_id']
        output=rt.ROOT/rt.DATA/'results'/(rid+'.json')
        if output.exists() or rt.now()<rt.when(pair['scheduled_start_at']): continue
        source=rt.ROOT/'e2e_validation/results'/(rid+'.json')
        if not source.exists() and pair['metadata'].get('research_only'):
            original=pair['baseline'].get('original_research_forecast',{})
            canonical=original.get('source_race_id')
            if canonical:
                source=rt.safe('e2e_validation/results/'+canonical+'.json')
            else:
                matches=list((rt.ROOT/'experience_regime_v1/results').glob('*/'+rid+'.json'))
                if len(matches)==1:source=matches[0]
        if not source.exists():continue
        result=rt.read(source)
        url=result.get('official_url') or result.get('official_result_url')
        if not str(url).startswith('https://www.jra.go.jp/'): continue
        if 'horses' in result:
            horses=result['horses']
            # Scratches, DNF and ties are explicitly not silently scored.
            if not all(h['started'] and isinstance(h['finish_position'],int) for h in horses):continue
            positions=[h['finish_position'] for h in horses]
            result={**result,'official_result_at':result['result_capture_at'],
                    'finish_order':[h['horse_number'] for h in sorted(horses,key=lambda h:h['finish_position'])],
                    'dead_heat':len(set(positions))!=len(positions),'official_payouts_yen_per_100':{}}
        # Existing JRA result extraction is the official data workflow's source.
        structured={'race_id':rid,'observed_at':result['official_result_at'],'source_url':url,
                    'finish_order':result['finish_order'],'dead_heat':result.get('dead_heat',False),
                    'payouts':{t:[{'selection':[int(n) for n in k.split('-')],'yen_per_100':v} for k,v in values.items()]
                               for t,values in result['official_payouts_yen_per_100'].items()},
                    'source_result_path':str(source.relative_to(rt.ROOT)), 'source_result_sha256':rt.digest(source.read_bytes())}
        capture=rt.ROOT/rt.DATA/'result-captures'/(rid+'.json')
        rt.dump(capture,structured,immutable=True)
        rt.dump(output,{**structured,'capture_path':str(capture.relative_to(rt.ROOT)),'capture_sha256':rt.digest(capture.read_bytes())},immutable=True)
        imported.append(rid)
    return imported

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['morning','research','evening']);p.add_argument('--date')
    a=p.parse_args(); day=a.date or datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat()
    print(reconcile() if a.phase=='evening' else discover(day))
    rt.dump(rt.ROOT/'docs/lab/data/shadow-runtime.json',rt.status())

if __name__=='__main__':main()
