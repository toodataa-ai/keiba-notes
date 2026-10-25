#!/usr/bin/env python3
"""Publish v3.16 ONLY after a separate prestart Git proof; preserve all prior artifacts."""
import copy,datetime as dt,hashlib,json,subprocess,sys,importlib.util,re
from pathlib import Path
import fitz
REG=Path('docs/data/races.json')
LOG=Path('docs/data/jra_publication_revision_log.json')
def require(ok,msg):
 if not ok:raise RuntimeError('V316_PRODUCTION_BLOCKER: '+str(msg))
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
def tm(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(dt.timezone.utc)
def key(x):
 # equivalent to v3.9 stable normalized ticket identity for sources already sealed
 return x['market_selection_id']
def verify():
 require(len(sys.argv) in (7,8),'usage PLAN SOURCE PRIOR REPORT PDF MANIFEST [FRESH_INPUT]')
 pp,sp,bp,hp,fp,mp=map(Path,sys.argv[1:7])
 freshpath=Path(sys.argv[7]) if len(sys.argv)==8 else None
 fresh_mode=bool(freshpath)
 p,s,b=read(pp),read(sp),read(bp)
 now=dt.datetime.now(dt.timezone.utc)
 require(p.get('purchase_strategy_version')=='v3.16' and p.get('status')=='formal_prestart',
         'only independently sealed v3.16 formal prediction')
 require(s.get('prompt_version')=='v3.13' and s.get('stage')=='formal_prestart',
         'frozen v3.13 source required')
 require(b.get('purchase_strategy_version')=='v3.15' and b.get('status')=='formal_prestart',
         'frozen v3.15 predecessor required')
 require(p.get('source_prediction_sha256')==sha(sp) and p.get('source_prediction_proof')==s.get('proof_commit'),
         'original v3.13 source chain mismatch')
 require(p.get('source_purchase_sha256')==sha(bp) and p.get('source_purchase_proof')==b.get('proof_commit') and
         p.get('source_purchase_path')==bp.as_posix(),
         'original v3.15 purchase chain mismatch')
 require(b.get('source_prediction_sha256')==p.get('source_prediction_sha256') and
         b.get('source_prediction_proof')==p.get('source_prediction_proof'),
         'historical source reference diverged')
 require(p.get('race_context')==b.get('race_context')==s.get('race_context') and
         p.get('step1_fixed_at')==b.get('step1_fixed_at')==s.get('step1_fixed_at'),
         'STEP1 or race context changed')
 require(p.get('source_race_id')==b.get('source_race_id')==s.get('race_id'),
         'race mismatch')
 start=tm(p['race_context']['start_at'])
 require(now<start,'race already started; never revise after post')
 require(tm(s['final_bets_fixed_at'])<tm(b['final_bets_fixed_at'])<tm(p['final_bets_fixed_at'])<start,
         'incorrect historical or future freeze order')
 if not fresh_mode:
  require(b['quote_age_max_seconds']<=600 and b['quote_capture_span_seconds']<=180 and
          (tm(p['final_bets_fixed_at'])-tm(b['final_bets_fixed_at'])).total_seconds()+b['quote_age_max_seconds']<=600,
          'stale full-market original price evidence')
 else:
  fresh=read(freshpath);audit=p.get('full_refresh_odds')
  require(isinstance(audit,dict) and audit.get('all_eight_type_prices_refetched') is True,
          'full 8-type fresh recapture mandatory')
  require(audit['fresh_input_path']==freshpath.as_posix() and
          sha(freshpath)==audit['fresh_input_sha256'],'new full-odds source SHA mismatch')
  require(fresh['race_id']==p['source_race_id'] and
          fresh['race_context']==s['race_context'] and
          fresh['prompt_version']=='v3.13','wrong fresh source race or model')
  original_input=Path('e2e_validation/inputs/v313/'+p['source_race_id']+'.json')
  require(original_input.is_file() and sha(original_input)==audit['input_source_sha256'],
          'original v3.13 racecard input differs')
  historic=read(original_input)
  require(all(historic[x]==fresh[x] for x in ('step1','strategies','frame_map','scenario_factors','race_context')),
          'source plan or original STEP1 changed')
  qs=fresh.get('market_quotes',[])
  require(len(qs)==audit['checked_candidate_keys']==audit['quote_count'] and
          len({x['market_selection_id'] for x in qs})==len(qs),
          'full fresh-odds coverage mismatch')
  age=max((now-tm(q['observed_at'])).total_seconds() for q in qs)
  times=[tm(q['observed_at']) for q in qs]
  require(0<=age<=600 and (max(times)-min(times)).total_seconds()<=180 and
          max(times)<start,'price evidence expired at publication or spans mixed markets')
  require(p['quote_age_max_seconds']<=600 and p['quote_capture_span_seconds']<=180,
          'formal v3.16 audit reported stale prices')
  quoted={q['market_selection_id']:q for q in qs}
  for q in qs:
   path=q['source_capture_path']
   require(q['quote_verified'] is True and
           q['source_url'].startswith('https://sports.yahoo.co.jp/keiba/race/odds/') and
           path.startswith('e2e_validation/quote-evidence/'+p['source_race_id']+'/v316-') and
           '..' not in path and
           Path(path).is_file() and sha(path)==q['source_capture_sha256'],
           'fresh quote source provenance missing or corrupted')
  require(audit['original_v315_source_sha256']==sha(sp),
          'historical source SHA mismatch')

 proof=p.get('proof_commit')
 require(isinstance(proof,str) and bool(re.fullmatch('[a-f0-9]{40}',proof)),
         'missing independent new Git proof')
 snap=pp.as_posix().replace('predictions','snapshots').replace('-sealed.json','.json')
 require(Path(snap).is_file(),'new v3.16 research snapshot missing')
 original=json.loads(git('show',proof+':'+snap))
 sealed=copy.deepcopy(original);sealed['proof_commit']=proof;sealed['status']='formal_prestart'
 require(sealed==p,'v3.16 changed after Git proof')
 require(tm(git('show','-s','--format=%cI',proof))<start,'proof after actual race start')
 if fresh_mode:
  require(hashlib.sha256(subprocess.check_output(['git','show',proof+':'+freshpath.as_posix()])).hexdigest()==sha(freshpath),
          'fresh capture missing from before-start Git proof')
  for evidence in {q['source_capture_path'] for q in qs}:
   require(hashlib.sha256(subprocess.check_output(['git','show',proof+':'+evidence])).hexdigest()==sha(evidence),
           'evidence not fixed in the independent prestart Git proof')
 require(p['purchase_decision']=='buy' and b['purchase_decision']=='buy','cannot turn a pass into a bet')
 proposed=p['formal_bets']; baseline=b['formal_bets']
 require(isinstance(proposed,list) and len(proposed)==len(baseline)==p['ticket_count']>0,
         'ticket count changed from formal v3.15')
 require([key(x) for x in proposed]==[key(x) for x in baseline] and
         len({key(x) for x in proposed})==len(proposed),'ticket identity/order modified')
 require(all(x['type']==y['type'] and x['selection']==y['selection'] and
         x['quote_verified'] is True and x['stake_yen']>=y['stake_yen']==100 and
         x['stake_yen']%100==0 and
         (fresh_mode and x['market_odds']==quoted[x['market_selection_id']]['market_odds'] and
          x['source_url']==quoted[x['market_selection_id']]['source_url'] and
          x['observed_at']==quoted[x['market_selection_id']]['observed_at'] or
          not fresh_mode and x['market_odds']==y['market_odds'] and
          x['source_url']==y['source_url'] and x['observed_at']==y['observed_at'])
         for x,y in zip(proposed,baseline)),'unverified price or altered selection')
 amount=sum(x['stake_yen'] for x in proposed)
 require(amount==p['total_stake_yen'] and amount>= b['total_stake_yen'] and
         amount<=6000 and amount-b['total_stake_yen']<=600 and
         amount<=b['total_stake_yen']*1.5,'unsupported stake increase')
 oldcmd=[*b['regular_commands'],b['medium_command'],b['large_command']]
 newcmd=[*p['regular_commands'],p['medium_command'],p['large_command']]
 require(len(oldcmd)==len(newcmd)<=5 and len(b['regular_commands'])==len(p['regular_commands'])<=3,
         'purchase operations changed')
 for oc,nc in zip(oldcmd,newcmd):
  require(oc['category']==nc['category'] and oc['type']==nc['type'] and
          oc['method']==nc['method'] and oc['jra_input']==nc['jra_input'] and
          oc['points']==nc['points'] and oc['ticket_keys']==nc['ticket_keys'],
          'JRA purchase inputs changed')
  if oc['method']=='pass':continue
  unit=nc['unit_stake_yen']
  require(isinstance(unit,int) and unit%100==0 and
          unit<= (300 if nc['category']=='通常' else 100) and
          nc['stake_yen']==nc['points']*unit,
          'illegal command expansion or speculative stake increase')
 require(sum(x['stake_yen'] for x in newcmd if x['method']!='pass')==amount,
         'commands do not exactly cover the recommended bet amount')
 audit=p.get('stake_optimization_audit')
 require(isinstance(audit,dict) and
         (audit.get('shadow_proposal_available') is True or fresh_mode) and
         audit.get('publication_allowed') is False and
         audit.get('audit',{}).get('unchanged_ticket_set') is True and
         audit['audit']['speculation_stays_at_100_yen'] is True,
         'shadow audit unavailable')
 base=audit['baseline']['scenarios'];new=audit['candidate']['scenarios']
 require(audit['baseline']['stake_yen']==b['total_stake_yen'] and
         audit['candidate']['stake_yen']==p['total_stake_yen'],'shadow totals changed')
 require(new['central']['expected_net_profit_yen']>=base['central']['expected_net_profit_yen']+
         (10 if audit['shadow_proposal_available'] else 0)-1e-6 and
         new['low']['expected_net_profit_yen']>=base['low']['expected_net_profit_yen']-1e-6 and
         new['central']['loss_probability']<=base['central']['loss_probability']+1e-6 and
         new['low']['loss_probability']<=base['low']['loss_probability']+0.005+1e-6,
         'regressed EV, low-case or net-loss probability')
 require(Path(hp).is_file() and Path(fp).is_file() and
         str(hp).startswith('docs/reports/') and str(fp).startswith('docs/pdfs/'),
         'new publication paths missing')
 spec=importlib.util.spec_from_file_location('locked_reader_layout_validator',
      '.github/scripts/validate-jra-pdf-layout.py')
 validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
 errors=validator.validate(hp,fp,Path('docs/data/jra_pdf_layout_policy_v1.json'))
 require(not errors,'reader-v1 layout errors: '+'; '.join(errors[:6]))
 page=hp.read_text(encoding='utf-8')
 horses=len(re.findall(r'<section class="horse">',page))
 other=len(re.findall(r'<section class="page">',page))
 require('正式購入v3.16' in page and
         '購入操作とJRA入力馬番' in page and '採用買い目｜' in page,
         'official amount version not displayed')
 require(horses==p['race_context']['sale_field_size'] and other>=8,
         'missing horses or reader report content')
 with fitz.open(fp) as pdf:
  pages=len(pdf)
  require(pages==horses+other and '最終購入予定' in pdf[0].get_text(),
          'incomplete A4 PDF')
 master=read(REG)
 entries=[x for x in master['races'] if x.get('id')==p['source_race_id'] and x.get('scope')=='jra-main']
 require(len(entries)==1,'non-unique published JRA race')
 old=entries[0]
 require(old['status']=='predicted' and old.get('result') is None and old.get('review') is None,
         'postrace results already exist')
 require(old.get('purchase_strategy_version')=='v3.15' and
         old.get('e2e_prediction')==bp.as_posix() and
         old.get('proof_commit')==b['proof_commit'] and
         old.get('final_bets')==baseline,
         'current v3.15 already superseded or differs from original')
 require(old.get('date')==s['race_context']['date'] and
         old.get('venue')==s['race_context']['venue'] and
         old.get('race')==s['race_context']['race_name'],'race canonical identity changed')
 journal=read(LOG)
 require(not any(x.get('new_canonical',{}).get('proof_commit')==proof
                 for x in journal['revisions']),'duplicate proof publication')
 updated=copy.deepcopy(old)
 updated.update(purchase_strategy_version='v3.16',purchase_commands=p['regular_commands'],
  medium_command=p['medium_command'],large_command=p['large_command'],
  purchase_comparison=p['comparison_to_v313'],purchase_risk_metrics=p['purchase_metrics'],
  purchase_stake_optimization=p['stake_optimization_audit'],
  report=str(hp).removeprefix('docs/'),pdf=str(fp).removeprefix('docs/'),
  pdf_mode='full',full_report_pages=pages,final_bets=copy.deepcopy(proposed),
  bets=[x['type']+' '+'-'.join(map(str,x['selection'])) for x in proposed],
  total_stake_yen=amount,purchase_decision='buy',
  purchase_reason_code=('v316_fresh_eight_type_prices_and_bounded_amounts' if fresh_mode else 'v316_proof_verified_bounded_stake_improvement'),
  final_bets_fixed_at=p['final_bets_fixed_at'],e2e_prediction=pp.as_posix(),
  proof_commit=proof)
 journal['revisions'].append({
  'race_id':p['source_race_id'],'promoted_at_utc':now.isoformat(),
  'old_canonical':copy.deepcopy(old),
  'new_canonical':{k:updated[k] for k in
    ('prompt_version','purchase_strategy_version','report','pdf',
     'e2e_prediction','proof_commit','final_bets_fixed_at')},
  'original_v313_preserved':str(sp),'original_v315_preserved':str(bp),
  'fresh_quote_input':str(freshpath) if fresh_mode else None,
  'previous_pdf_preserved':old['pdf'],
  'html_sha256':sha(hp),'pdf_sha256':sha(fp),
  'approved_forward_only_variable_staking':True
 })
 idx=master['races'].index(old);master['races'][idx]=updated
 master['updated_at']=now.astimezone(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='milliseconds')
 REG.write_text(json.dumps(master,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 LOG.write_text(json.dumps(journal,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 mp.parent.mkdir(parents=True,exist_ok=True)
 mp.write_text(json.dumps({
  'schema_version':1,'status':'v3.16_variable_stake_formal_prestart',
  'race_id':p['source_race_id'],'v313_original':str(sp),
  'prior_v315_original':str(bp),'previous_proof_commit':b['proof_commit'],
  'new_proof_commit':proof,'plan':str(pp),'new_stake_yen':amount,
  'original_stake_yen':b['total_stake_yen'],'ticket_count':len(proposed),
  'operation_count':p['command_count'],
  'full_eight_type_refresh':fresh_mode,
  'html_sha256':sha(hp),'pdf_sha256':sha(fp)
 },ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('PASS_FORMAL_V316_CANONICAL_PROMOTION',p['source_race_id'],
       'old_yen',b['total_stake_yen'],'new_yen',amount,
       'original_ticket_count',len(proposed),'pdf_pages',pages)
if __name__=='__main__':
 try:verify()
 except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
