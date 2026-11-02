"""Fail-closed prospective lifecycle. All writes confined to Shadow sidecars.

The receipt references a GitHub commit STATUS: created_at is a server timestamp,
unlike a forgeable git author/committer time. No receipt is its own evidence.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experience_regime_v1.model import classify_regime
from experience_regime_v1.sampling import select_races, load_sampling_policy
from e2e_validation.tokyo_kyoto_going_shadow_v1 import capture

REPO = 'toodataa-ai/keiba-notes'
DATA = 'shadow_lab/evidence'
GRADE = {'C': .6, 'B-': 1., 'B': 1.65, 'B+': 2.55, 'A': 3.7, 'A+': 5.3}
THEMES = ('pace_positioning', 'track_condition', 'ticket_portfolio', 'field_experience', 'E0', 'E1', 'E2')

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def dump(p, value, immutable=False):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x' if immutable else 'w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def when(s):
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('timezone_required')
    return d.astimezone(timezone.utc)

def now():
    return datetime.now(timezone.utc)

def check(v, message):
    if not v:
        raise ValueError(message)

def digest(b):
    return hashlib.sha256(b).hexdigest()

def code_digest():
    paths={ROOT/'shadow_lab/runtime.py',ROOT/'shadow_lab/candidate.mjs'}
    paths.update(ROOT/p for p in ('e2e_validation/tokyo_kyoto_going_shadow_v1.py','baba_models_v2/predict.py',
        'baba_models_v2/config.json','experience_regime_v1/model.py','experience_regime_v1/sampling.py','experience_regime_v1/config.json'))
    queue=[ROOT/'shadow_lab/candidate.mjs']
    while queue:
        path=queue.pop()
        for name in re.findall(r"from ['\"]([^'\"]+)['\"]",path.read_text()):
            if not name.startswith('.'):continue
            dependency=(path.parent/name).resolve()
            check(dependency.is_relative_to(ROOT),'dependency_outside_repository')
            if dependency not in paths:paths.add(dependency);queue.append(dependency)
    return digest(b''.join(str(p.relative_to(ROOT)).encode()+b'\0'+p.read_bytes() for p in sorted(paths) if p.exists()))

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

def api(path, *args):
    return json.loads(subprocess.check_output(['gh', 'api', 'repos/'+REPO+'/'+path, *args], cwd=ROOT))

def safe(path):
    p = Path(path)
    check(not p.is_absolute() and '..' not in p.parts and not (ROOT/p).is_symlink(), 'unsafe_path')
    check((ROOT/p).resolve().is_relative_to(ROOT), 'outside_repository')
    return ROOT/p

def finite(x, lo=0, hi=1):
    check(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and lo <= x <= hi, 'invalid_numeric_feature')
    return x

def source(block, cutoff):
    check(when(block['observed_at']) <= cutoff, 'feature_after_cutoff')
    path = safe(block['path'])
    check(digest(path.read_bytes()) == block['sha256'], 'feature_source_digest_mismatch')
    check(str(block['url']).startswith(('https://www.jra.go.jp/', 'https://www.jma.go.jp/', 'https://www.data.jma.go.jp/')), 'nonofficial_feature_source')

def plans():
    return read(ROOT/'e2e_validation/improvement_experiments_v1.json')['experiments']

def design(theme):
    return next(p for p in plans() if (p.get('research_regime') or p['hypothesis_ids'][0]) == theme)

def gate(theme):
    if theme.startswith('E'):
        return True  # collection must run BEFORE a probability diagnostic can pass
    d = read(ROOT/'docs/data/jra_improvement_cycle_v1.json')
    h = next(h for h in d['formal']['hypotheses'] if h['id'] == theme)
    return h['next_decision']['screening']['ready_to_design_experiment'] is True

def make_pair(packet, theme, instant=None):
    instant = instant or now()
    check(theme in THEMES, 'unknown_theme')
    if theme.startswith('E') and packet.get('research_snapshot_path'):
        return research_pair(packet,theme,instant)
    baseline = read(safe(packet['baseline_path']))
    baseline_bytes = safe(packet['baseline_path']).read_text()
    purchase = read(safe(packet['official_purchase_path'])) if packet.get('official_purchase_path') else None
    registry=read(ROOT/'docs/data/races.json')['races']
    canonical=next((r for r in registry if r.get('scope')=='jra-main' and r['id']==baseline['race_id']),None)
    check(canonical, 'baseline_not_canonical_formal_race')
    current_path=canonical['e2e_prediction']; current=read(safe(current_path))
    check(packet['baseline_path']==(current.get('source_prediction_path') or current_path), 'baseline_not_current_formal_source')
    check((packet.get('official_purchase_path') or packet['baseline_path'])==current_path, 'current_official_purchase_required')
    inp = read(safe(packet['input_path']))
    start = when(inp['race_context']['start_at'])
    cutoff = when(packet['information_cutoff_at'])
    check(cutoff <= instant < start, 'start_passed_or_future_cutoff')
    check(baseline['race_id'] == inp['race_id'], 'race_mismatch')
    check(cutoff==when(current['final_bets_fixed_at']), 'same_formal_information_cutoff_required')
    check(baseline['prompt_version'] == read(ROOT/'docs/data/latest_prompt.json')['version'], 'baseline_not_current')
    check(when(baseline['final_bets_fixed_at']) <= cutoff and when(inp['step1']['fixed_at']) <= cutoff, 'baseline_after_cutoff')
    if purchase:
        check(when(purchase['final_bets_fixed_at'])<=cutoff, 'official_purchase_after_cutoff')
    check(gate(theme), 'observation_gate_not_met')
    runners = inp['step1']['runners']
    ids = {str(r['horse_number']) for r in runners}
    check(len(ids) == len(runners), 'duplicate_horse')
    multipliers = {n: 1 for n in ids}
    grades, index, metadata = {}, None, {}
    features = packet.get('features', {})
    if theme == 'pace_positioning':
        f = features['pace']; source(f, cutoff)
        weights = f['scenario_probabilities']
        check(set(weights) == {'S', 'M', 'H'} and abs(sum(finite(v) for v in weights.values())-1)<1e-6, 'pace_scenarios_invalid')
        check(set(f['by_horse']) == ids, 'pace_full_field_missing')
        index = 1
        for r in runners:
            n = str(r['horse_number']); row = f['by_horse'][n]
            check(set(row) == {'S', 'M', 'H'} and all(v in GRADE for v in row.values()), 'pace_grades_invalid')
            score = sum(weights[k]*GRADE[row[k]] for k in weights)
            grades[n] = min(GRADE, key=lambda g: abs(GRADE[g]-score))
            multipliers[n] = math.exp(.1*(score-GRADE[r['factor_grades'][index]]))
        metadata = {'pace': weights, 'rule': 'factor2_scenario_expected_grade_logtilt_0.1'}
    elif theme == 'track_condition':
        f = features['track']; source(f, cutoff)
        check(f['pilot_input']['race_id'] == inp['race_id'] and when(f['pilot_input']['information_cutoff_at']) == cutoff and when(f['pilot_input']['scheduled_start_at']) == start, 'pilot_identity_cutoff_mismatch')
        venue = {'東京':'tokyo','京都':'kyoto'}.get(inp['race_context']['venue'])
        surface = {'芝':'turf','ダート':'dirt','turf':'turf','dirt':'dirt'}.get(inp['race_context']['surface'])
        check(f['pilot_input']['track'] == venue and f['pilot_input']['surface'] == surface, 'pilot_scope_mismatch')
        pilot = capture(f['pilot_input'], now=instant)
        weights = pilot['prediction']['condition_probs_operational']; total = sum(weights.values())
        weights = {k:v/total for k,v in weights.items()}
        check(set(f['by_horse']) == ids, 'track_full_field_missing')
        index = 2
        for r in runners:
            n = str(r['horse_number']); row = f['by_horse'][n]
            check(set(row['going_grades']) == set(weights) and all(g in GRADE for g in row['going_grades'].values()), 'going_grades_invalid')
            # Inner/outer bias must have prestart evidence; bounded effect.
            bias = finite(row['bias_adjustment'], -.5, .5)
            score = sum(weights[k]*GRADE[row['going_grades'][k]] for k in weights)+bias
            grades[n] = min(GRADE, key=lambda g:abs(GRADE[g]-score))
            multipliers[n] = math.exp(.1*(score-GRADE[r['factor_grades'][index]]))
        metadata = {'going': weights, 'pilot': pilot, 'rule': 'factor3_expected_grade_bias_logtilt_0.1', 'validated': False}
    elif theme == 'field_experience' or theme.startswith('E'):
        f = features['experience']; source(f, cutoff)
        check(set(f['starts_by_horse']) == ids, 'experience_full_field_missing')
        groups = {n:classify_regime(v) for n,v in f['starts_by_horse'].items()}
        if theme.startswith('E'):
            plan_path = safe(packet['sample_plan_path']); pool_path = plan_path.parent/'race_pool.json'
            plan = read(plan_path)
            check(plan == select_races(read(pool_path), load_sampling_policy(ROOT/'experience_regime_v1/config.json')), 'fixed_sample_plan_changed')
            selected = [r for r in plan['selected_races'] if r['date'] == inp['race_context']['date'] and r['venue'] == inp['race_context']['venue'] and r['race_no'] == inp['race_context']['race_no']]
            check(len(selected) == 1 and when(selected[0]['start_at']) == start, 'not_in_fixed_sample_plan')
            check(any(v == theme for v in groups.values()), 'no_horses_in_regime')
        for r in runners:
            n = str(r['horse_number']); group = groups[n]
            alpha = {'E0':.20, 'E1':.10, 'E2':.05}[group] if theme == 'field_experience' or group == theme else 0
            multipliers[n] = ((1-alpha)*r['win_probability']+alpha/len(runners))/r['win_probability']
        metadata = {'groups':groups,'rule':'fixed_uniform_shrinkage_E0_.20_E1_.10_E2_.05', 'research_only':theme.startswith('E')}
    elif theme == 'ticket_portfolio':
        check(len(baseline['bet_type_evaluations']) == 8, 'eight_type_review_missing')
        check(all(when(q['observed_at']) <= cutoff for q in inp['market_quotes']), 'odds_after_cutoff')
        check((cutoff-min(when(q['observed_at']) for q in inp['market_quotes'])).total_seconds()<=600, 'odds_stale_at_shared_cutoff')
        metadata = {'rule':'positive_low_EV_equal_100_v1', 'marks_unchanged':True}
    if 'experience' in features and 'groups' not in metadata:
        f=features['experience'];source(f,cutoff)
        check(set(f['starts_by_horse'])==ids,'collateral_experience_full_field_missing')
        metadata['groups']={n:classify_regime(v) for n,v in f['starts_by_horse'].items()}
    request = {'theme':theme,'input':inp,'baseline':baseline,'baseline_bytes':baseline_bytes,'purchase':purchase,'multipliers':multipliers,'grades':grades,'factor_index':index,
               'cutoff':packet['information_cutoff_at'],'candidate_version':design(theme)['challenger']+'-runtime1'}
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as temp:
        json.dump(request,temp);temp.flush()
        result = json.loads(subprocess.check_output(['node', 'shadow_lab/candidate.mjs',temp.name], cwd=ROOT,
                                                   timeout=max(1,min(60,(start-now()).total_seconds()-2))))
    result.update({'schema_version':1,'theme':theme,'race_id':inp['race_id'],'scheduled_start_at':inp['race_context']['start_at'],
                   'information_cutoff_at':packet['information_cutoff_at'],'generated_at':instant.isoformat(),
                   'metadata':metadata,'production_effect':False,'approval':'not_requested',
                   'week':(start.date()-timedelta(days=start.weekday())).isoformat(),
                   'conditions':packet.get('conditions',{}), 'packet':packet,
                   'sources':{path:digest(safe(path).read_bytes()) for path in [packet['baseline_path'],packet['input_path']]},
                   'code_sha256':code_digest()})
    if purchase:
        result['sources'][packet['official_purchase_path']]=digest(safe(packet['official_purchase_path']).read_bytes())
    if packet.get('sample_plan_path'):
        for path in (safe(packet['sample_plan_path']),safe(packet['sample_plan_path']).parent/'race_pool.json'):
            result['sources'][str(path.relative_to(ROOT))]=digest(path.read_bytes())
    check(now()<start, 'candidate_finished_after_start')
    return result

def research_pair(packet, theme, instant):
    """Research accepts a genuine full-field prereace probability forecast,
    independently of formal STEP2 and the eight-ticket sale-field restriction.
    No probabilities are invented for experience-only collection snapshots.
    """
    forecast_path=safe(packet['research_snapshot_path']); forecast=read(forecast_path)
    check(packet['research_snapshot_path'].startswith('experience_regime_v1/step1_frozen/'), 'research_forecast_outside_verified_capture')
    plan_path=safe(packet['sample_plan_path']); plan=read(plan_path)
    check(plan==select_races(read(plan_path.parent/'race_pool.json'),load_sampling_policy(ROOT/'experience_regime_v1/config.json')), 'fixed_sample_plan_changed')
    selection=next((r for r in plan['selected_races'] if r['race_id']==forecast['race_id']),None)
    check(selection, 'research_race_not_selected')
    start=when(selection['start_at']); cutoff=when(packet['information_cutoff_at'])
    check(cutoff<=instant<start and when(forecast['step1_fixed_at'])<=cutoff, 'research_after_cutoff_or_start')
    check(forecast.get('no_odds_used') is True and forecast.get('no_synthetic_predictions') is True, 'genuine_research_forecast_required')
    rows=forecast['runners']; ids={str(r['horse_number']) for r in rows}
    check(len(ids)==len(rows) and len(rows)>=4, 'full_field_required')
    wp={str(r['horse_number']):finite(r['predicted_win_probability']) for r in rows}
    tp={str(r['horse_number']):finite(r['predicted_top3_probability']) for r in rows}
    check(abs(sum(wp.values())-1)<1e-5 and abs(sum(tp.values())-3)<1e-5 and all(0<wp[n]<=tp[n]<1 for n in ids), 'invalid_research_probabilities')
    f=packet['features']['experience'];source(f,cutoff)
    check(set(f['starts_by_horse'])==ids, 'experience_full_field_missing')
    groups={n:classify_regime(v) for n,v in f['starts_by_horse'].items()}
    check(theme in groups.values(),'no_horses_in_regime')
    alpha={'E0':.20,'E1':.10,'E2':.05}[theme]
    # Shrink win probabilities, then recompute top3 with PL. Full-field masses
    # remain 1 and 3. Report collateral effects across every experience group.
    changed={n:((1-alpha)*wp[n]+alpha/len(ids)) if groups[n]==theme else wp[n] for n in ids}
    total=sum(changed.values()); changed={n:v/total for n,v in changed.items()}
    # PL is a prospective model assumption, never a finish-derived probability.
    top={n:0. for n in ids}
    for a in ids:
        for b in ids-{a}:
            for c in ids-{a,b}:
                prob=changed[a]*changed[b]/(1-changed[a])*changed[c]/(1-changed[a]-changed[b])
                for n in (a,b,c):top[n]+=prob
    context={k:selection[k] for k in ('date','venue','race_no','start_at')}
    base={'race_id':forecast['race_id'],'race_context':context,'step1_ranking':[{'horse_number':int(n),'win_probability':wp[n]} for n in ids],
          'final_bets':[],'total_stake_yen':0,'original_research_forecast':forecast}
    candidate=copy.deepcopy(base);candidate['prompt_version']=design(theme)['challenger']+'-runtime1';candidate['stage']='shadow_only'
    candidate['step1_ranking']=[{'horse_number':int(n),'win_probability':changed[n]} for n in ids]
    check(now()<start,'research_finished_after_start')
    return {'schema_version':1,'theme':theme,'race_id':forecast['race_id'],'scheduled_start_at':selection['start_at'],
            'information_cutoff_at':packet['information_cutoff_at'],'generated_at':instant.isoformat(),'baseline':base,'candidate':candidate,
            'probabilities':{'baseline':{'win':wp,'top3':tp},'candidate':{'win':changed,'top3':top}},
            'metadata':{'groups':groups,'rule':'fixed_uniform_shrinkage_E0_.20_E1_.10_E2_.05','research_only':True},
            'production_effect':False,'approval':'not_requested','week':(start.date()-timedelta(days=start.weekday())).isoformat(),
            'conditions':packet.get('conditions',{}),'packet':packet,
            'sources':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in (forecast_path,plan_path,plan_path.parent/'race_pool.json')},
            'code_sha256':code_digest()}

def prepare(packet, themes=THEMES):
    """No caller can supply now: only pure make_pair tests can use a clock."""
    reports=[]
    for theme in themes:
        try:
            origin=read(safe(packet.get('research_snapshot_path') or packet['baseline_path']))
            existing=f'{DATA}/pairs/{theme}/{origin["race_id"]}.json'
            if safe(existing).exists():
                reports.append({'theme':theme,'state':'preserved_no_rerun','path':existing})
                continue
            pair=make_pair(packet,theme)
            path=f'{DATA}/pairs/{theme}/{pair["race_id"]}.json'
            dump(safe(path),pair,immutable=True)
            reports.append({'theme':theme,'state':'prepared_not_proven','path':path})
        except (ValueError, KeyError, subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            reports.append({'theme':theme,'state':'blocked','blocker':str(e)})
    path=ROOT/DATA/'attempts'/(now().strftime('%Y%m%dT%H%M%S%f')+'.json')
    dump(path,{'at':now().isoformat(),'packet':packet,'reports':reports},immutable=True)
    return reports

def seal(branch):
    check(branch.startswith('experiment/'), 'shadow_branch_required')
    check(git('branch','--show-current') == branch, 'wrong_branch')
    check(git('remote','get-url','origin').rstrip('.git').endswith(REPO), 'wrong_remote')
    paths=git('diff','--name-only','--cached').splitlines()
    check(not paths or all(p.startswith(DATA+'/') for p in paths), 'non_shadow_staged_changes')
    candidates=[]
    for p in (ROOT/DATA/'pairs').glob('*/*.json'):
        receipt=ROOT/DATA/'receipts'/p.parent.name/p.name
        if not receipt.exists():
            pair=read(p)
            if now()>=when(pair['scheduled_start_at']):
                dump(ROOT/DATA/'attempts'/(now().strftime('%Y%m%dT%H%M%S%f')+'-expired.json'),
                     {'at':now().isoformat(),'reports':[{'theme':pair['theme'],'state':'blocked','blocker':'late_seal_forbidden:'+pair['race_id']}]},immutable=True)
                continue
            candidates.append((p,pair))
    check(candidates, 'no_unsealed_pairs')
    for p,pair in candidates:
        check(not git('status','--porcelain','--','shadow_lab/runtime.py','shadow_lab/candidate.mjs'), 'uncommitted_candidate_code')
        git('add','--',str(p.relative_to(ROOT)))
        for path in pair['sources']:
            check(not git('status','--porcelain','--',path), 'canonical_source_modified_or_untracked')
        # Feature evidence and sample plan are included in the same immutable tree.
        for feature in pair['packet'].get('features',{}).values():
            changed=git('status','--porcelain','--',feature['path'])
            check(not changed or feature['path'].startswith(('shadow_lab/requests/','shadow_lab/evidence/')), 'protected_feature_source_modified')
            if changed:git('add','--',feature['path'])
        if pair['packet'].get('sample_plan_path'):
            git('add','--',pair['packet']['sample_plan_path'])
    git('commit','-m','Seal independent prospective Shadow forecasts')
    proof=git('rev-parse','HEAD')
    git('push','origin','HEAD:refs/heads/'+branch)
    # GitHub creates this server-dated status only after accepting the proof SHA.
    status=api('statuses/'+proof,'-f','state=success','-f','context=shadow/prestart-sealed',
               '-f','description=Independent Shadow evidence accepted; no production effect')
    for p,pair in candidates:
        check(when(status['created_at']) < when(pair['scheduled_start_at']), 'github_received_after_start')
        receipt={'proof_commit':proof,'status_id':status['id'],'status_created_at':status['created_at'],
                 'pair_path':str(p.relative_to(ROOT)),'pair_sha256':digest(p.read_bytes()),'repository':REPO}
        dump(ROOT/DATA/'receipts'/p.parent.name/p.name,receipt,immutable=True)
    git('add','--',DATA+'/receipts')
    git('commit','-m','Record server-dated Shadow proof receipts')
    git('push','origin','HEAD:refs/heads/'+branch)

def audit(receipt, fetch_status=None):
    fetch_status=fetch_status or (lambda sha:api('commits/'+sha+'/statuses?per_page=100'))
    sha=receipt['proof_commit']
    check(re.fullmatch('[a-f0-9]{40}',sha) and receipt['repository']==REPO, 'bad_proof_identity')
    path=receipt['pair_path']
    check(path.startswith(DATA+'/pairs/') and '..' not in Path(path).parts, 'invalid_pair_path')
    raw=subprocess.check_output(['git','show',sha+':'+path],cwd=ROOT)
    check(digest(raw)==receipt['pair_sha256'] and raw==safe(path).read_bytes(), 'pair_changed_since_proof')
    pair=json.loads(raw)
    statuses=fetch_status(sha)
    status=next((s for s in statuses if s['id']==receipt['status_id']),None)
    check(status and status['context']=='shadow/prestart-sealed' and status['state']=='success', 'github_status_missing')
    stamp=when(status['created_at']); start=when(pair['scheduled_start_at'])
    generated=when(pair['generated_at'])
    # GitHub commit-status timestamps have second precision; local generation
    # timestamps have microseconds. Compare equal-precision times, still strictly
    # before the official start. Git author timestamps are never substituted.
    check(when(pair['information_cutoff_at'])<=generated and generated.replace(microsecond=0)<=stamp<start, 'not_prospective_grade_A')
    check(status['created_at']==receipt['status_created_at'], 'receipt_timestamp_changed')
    for path,expected in pair['sources'].items():
        check(digest(subprocess.check_output(['git','show',sha+':'+path],cwd=ROOT))==expected, 'source_not_in_proof')
    for f in pair['packet'].get('features',{}).values():
        check(digest(subprocess.check_output(['git','show',sha+':'+f['path']],cwd=ROOT))==f['sha256'], 'feature_not_in_proof')
    check(pair['theme'] in THEMES and pair['baseline']['race_id']==pair['candidate']['race_id']==pair['race_id'], 'pair_identity_mismatch')
    check(pair['baseline']['race_context']==pair['candidate']['race_context'], 'race_context_changed')
    expected_code=code_digest()
    check(pair['code_sha256']==expected_code, 'different_candidate_code_keep_separate_version')
    check(pair['candidate']['prompt_version']==design(pair['theme'])['challenger']+'-runtime1', 'different_candidate_version')
    return pair

def settle(pair, result):
    check(result['race_id']==pair['race_id'], 'result_wrong_race')
    start=when(pair['scheduled_start_at'])
    check(when(result['observed_at'])>=start and now()>=start, 'result_before_start')
    check(str(result['source_url']).startswith('https://www.jra.go.jp/'), 'official_result_required')
    capture_path=safe(result['capture_path']); check(digest(capture_path.read_bytes())==result['capture_sha256'], 'official_result_digest_mismatch')
    # Capture is the structured official-result extract, not an unbound HTML blob.
    check(read(capture_path)=={k:v for k,v in result.items() if k not in {'capture_path','capture_sha256'}}, 'result_not_bound_to_capture')
    finish=result['finish_order']
    ids=set(pair['probabilities']['baseline']['win'])
    check(len(finish)==len(set(finish)) and {str(n) for n in finish}==ids, 'incomplete_result_or_scratch_requires_review')
    check(result.get('dead_heat') is False, 'dead_heat_manual_review_required')
    payouts=result['payouts']
    if not pair['metadata'].get('research_only'):
        check(set(payouts)=={'単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'}, 'official_payout_coverage_incomplete')
    rows={}
    for side in ('baseline','candidate'):
        probs=pair['probabilities'][side]
        horses=[]
        for n in sorted(ids,key=int):
            wp,tp=finite(probs['win'][n]),finite(probs['top3'][n])
            win,top3=int(n==str(finish[0])),int(n in {str(x) for x in finish[:3]})
            horses.append({'horse':n,'group':pair['metadata'].get('groups',{}).get(n),
                           'win_brier':(wp-win)**2,'top3_brier':(tp-top3)**2,
                           'win_log_loss':-math.log(max(1e-12,wp if win else 1-wp)),
                           'win_probability':wp,'actual_win':win,'top3_probability':tp,'actual_top3':top3})
        forecast=pair[side]; stake=0; returned=0
        for bet in forecast['final_bets']:
            stake+=bet['stake_yen']
            # Exact selections as published; payout entries include every winner,
            # including frame and place/multiple-winner tickets. Losers pay zero.
            match=[q for q in payouts[bet['type']] if q['selection']==bet['selection']]
            check(len(match)<=1, 'duplicate_official_payout')
            if match: returned+=finite(match[0]['yen_per_100'],0,1e10)*bet['stake_yen']/100
        ranking=sorted(forecast['step1_ranking'],key=lambda r:-r['win_probability'])
        honmei=next((r for r in ranking if r.get('mark')=='◎'),ranking[0])
        rows[side]={'horses':horses,'stake_yen':stake,'return_yen':returned,'net_yen':returned-stake,
                    'roi':returned/stake if stake else None,'honmei_top3':int(honmei['horse_number'] in finish[:3]),
                    'top3_capture':len({r['horse_number'] for r in ranking[:3]}&set(finish[:3]))/3,
                    'expected_value':forecast.get('shadow_metrics',forecast.get('purchase_portfolio_selection'))}
    return {'race_id':pair['race_id'],'theme':pair['theme'],'week':pair['week'],'conditions':pair['conditions'],'grade':'prospective_strict','sides':rows}

def summarize(cases):
    result={}
    for side in ('baseline','candidate'):
        rows=[c['sides'][side] for c in cases]; horses=[h for r in rows for h in r['horses']]
        avg=lambda xs:sum(xs)/len(xs) if xs else None
        stake=sum(r['stake_yen'] for r in rows); returned=sum(r['return_yen'] for r in rows)
        bins=[[h for h in horses if min(9,int(h['win_probability']*10))==i] for i in range(10)]
        ece=sum(len(b)*abs(avg([h['win_probability'] for h in b])-avg([h['actual_win'] for h in b])) for b in bins if b)/len(horses) if horses else None
        result[side]={'races':len(rows),'stake_yen':stake,'return_yen':returned,'roi':returned/stake if stake else None,
                      'honmei_top3_rate':avg([r['honmei_top3'] for r in rows]),'top3_capture':avg([r['top3_capture'] for r in rows]),
                      **{k:avg([h[k] for h in horses]) for k in ('win_brier','top3_brier','win_log_loss')},
                      'calibration_gap':avg([h['win_probability']-h['actual_win'] for h in horses]),
                      'calibration_ece_10_bins':ece,
                      'max_race_loss_yen':max([max(0,-r['net_yen']) for r in rows],default=0)}
        evs=[]
        for row in rows:
            ev=row['expected_value'] or {}
            payout=(ev.get('expected_payout_yen_scenarios') or {}).get('central')
            if payout is not None:evs.append(payout-row['stake_yen'])
        result[side]['mean_modeled_expected_net_yen']=avg(evs)
    result['deltas_candidate_minus_baseline']={k:result['candidate'][k]-result['baseline'][k]
        if isinstance(result['candidate'][k],(float,int)) and isinstance(result['baseline'][k],(float,int)) else None
        for k in result['baseline'] if k!='races'}
    return result

def diagnostic_counts(cases,theme):
    horses=[h for c in cases for h in c['sides']['baseline']['horses'] if h['group']==theme]
    races=len({c['race_id'] for c in cases});weeks=len({c['week'] for c in cases})
    return len(horses),races,weeks,len(horses)>=30 and races>=3 and weeks>=2

def approval_state(theme, enough, metrics, fetch_comment=None):
    """Record manual A/B/C judgment without any production-changing capability.
    A JSON file alone is never authorization: verify the owner's GitHub comment.
    """
    path=ROOT/DATA/'reviews'/(theme+'.json')
    if not path.exists():return ('pending_A_B_C_review' if enough else 'not_ready'),None
    review=read(path); token=review['decision']
    check(token['theme']==theme and token['candidate']==design(theme)['challenger']+'-runtime1','review_version_mismatch')
    check(token['classification'] in {'A','B','C'},'A_B_C_classification_required')
    check(token['decision'] in {'rejected','continue_collecting','approved_for_release','diagnostic_reviewed'},'invalid_manual_decision')
    expected=digest(json.dumps(metrics,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    check(token['metrics_sha256']==expected,'review_metrics_changed_requires_new_review')
    if token['decision'] in {'approved_for_release','diagnostic_reviewed'}:
        check(enough,'sample_threshold_not_met')
        check(all(review.get('checks',{}).get(k) is True for k in ('accuracy','expected_value','side_effects','holdout','overfit','conditions')),'review_checks_incomplete')
        check(not theme.startswith('E') or token['decision']=='diagnostic_reviewed','research_cannot_approve_formal_release')
    report=safe(review['report_path'])
    check(digest(report.read_bytes())==review['report_sha256'],'review_report_mismatch')
    fetch_comment=fetch_comment or (lambda id_:api('issues/comments/'+str(id_)))
    comment=fetch_comment(review['github_comment_id'])
    check(comment['user']['login']==REPO.split('/')[0],'owner_approval_required')
    line='SHADOW_DECISION '+json.dumps(token,sort_keys=True,separators=(',',':'))
    check(line in comment['body'].splitlines(),'explicit_github_decision_missing')
    return token['decision'],{'classification':token['classification'],'comment_url':comment['html_url'],'report_path':review['report_path']}

def status(fetch_status=None):
    accepted=defaultdict(list); errors=defaultdict(list); seen=set(); pending=defaultdict(int)
    for p in sorted((ROOT/DATA/'receipts').glob('*/*.json')):
        theme=p.parent.name
        try:
            pair=audit(read(p),fetch_status); key=(pair['theme'],pair['race_id'])
            check(key not in seen,'duplicate_pair'); seen.add(key)
            rp=ROOT/DATA/'results'/(pair['race_id']+'.json')
            if not rp.exists():
                pending[theme]+=1; errors[theme].append('official_result_not_collected:'+pair['race_id']); continue
            case=settle(pair,read(rp)); accepted[theme].append(case)
        except Exception as e:
            errors[theme].append(p.name+':'+str(e))
    attempts=sorted((ROOT/DATA/'attempts').glob('*.json'))
    latest={}
    sample_gaps=[]
    for path in attempts:
        attempt=read(path)
        for report in attempt.get('reports',[]): latest[report['theme']]=report
        if 'sample_gaps' in attempt:sample_gaps=attempt['sample_gaps']
    output=[]
    roadmap=read(ROOT/'docs/data/jra_improvement_cycle_v1.json')
    for theme in THEMES:
        cases=accepted[theme]; plan=design(theme)
        horse_count,races,weeks,diagnostic=diagnostic_counts(cases,theme)
        enough=diagnostic if theme.startswith('E') else races>=20
        conditions={}
        for dim in ('venue','surface','rain','meeting_week'):
            labels={str(c['conditions'].get(dim,'unknown')) for c in cases}
            conditions[dim]={label:summarize([c for c in cases if str(c['conditions'].get(dim,'unknown'))==label]) for label in sorted(labels)}
        blockers=list(errors[theme])
        gaps=[g for g in sample_gaps if g['theme']==theme]
        if gaps:blockers.append('fixed_sample_missing_full_field_probabilities:'+str(len(gaps)))
        if latest.get(theme,{}).get('blocker'): blockers.append(latest[theme]['blocker'])
        if not cases: blockers.append('no_valid_prospective_comparisons')
        if not gate(theme): blockers.append('observation_gate_not_met')
        if theme.startswith('E') and not diagnostic: blockers.append('diagnostic_requires_30_horses_3_races_2_weeks')
        observation=next((h['next_decision']['screening'] for h in roadmap['formal']['hypotheses'] if h['id']==theme),None)
        metrics=summarize(cases)
        try:
            approval,decision=approval_state(theme,enough,metrics)
        except Exception as e:
            approval,decision='blocked_review',None;blockers.append('review:'+str(e))
        output.append({'theme':theme,'id':plan['id'],'title':plan['title'],'implemented':True,'candidate_version':plan['challenger']+'-runtime1',
                       'runner_ready':True,'observation':observation,'observation_gate_ready':gate(theme),'latest_attempt':latest.get(theme),
                       'data_collection_gaps':gaps,
                       'valid_pairs':races,'paired_target':None if theme.startswith('E') else 20,'probability_horses':horse_count,
                       'distinct_races':races,'independent_weeks':weeks,'diagnostic_ready':diagnostic if theme.startswith('E') else None,
                       'sealed_awaiting_result':pending[theme],'metrics':metrics,'condition_audit':conditions,
                       'regime_probability_audit':{group:{side:{
                           'horse_records':len(hs),
                           **{key:sum(h[key] for h in hs)/len(hs) if hs else None for key in ('win_brier','top3_brier','win_log_loss')}
                           } for side in ('baseline','candidate')
                           for hs in [[h for c in cases for h in c['sides'][side]['horses'] if h['group']==group]]}
                           for group in ('E0','E1','E2')},
                       'approval':approval,'manual_decision':decision,'adopted':False,'automatic_promotion':False,
                       'validation':'sample_threshold_only_review_required' if enough else 'collecting',
                       'overfit_review':{'frozen_policy':True,'independent_weeks':weeks,'holdout_review':'required_before_approval','multiple_testing':'seven_themes_report_all_no_winner_selection'},
                       'evidence_races':[c['race_id'] for c in cases],
                       'blockers':sorted(set(blockers)),'next_action':'review accuracy, side effects, holdout and A/B/C approval' if enough else 'collect missing inputs before next start, seal and reconcile official results'})
    return {'schema_version':1,'kind':'shadow_runtime','repository':REPO,'automatic_promotion':False,'experiments':output}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['prepare','seal','status'])
    parser.add_argument('--packet'); parser.add_argument('--branch')
    args=parser.parse_args()
    if args.command=='prepare': print(json.dumps(prepare(read(safe(args.packet))),ensure_ascii=False))
    elif args.command=='seal': seal(args.branch)
    else:
        d=status(); dump(ROOT/'docs/lab/data/shadow-runtime.json',d)
        print(json.dumps({x['theme']:{'pairs':x['valid_pairs'],'blockers':x['blockers']} for x in d['experiments']},ensure_ascii=False))

if __name__=='__main__': main()
