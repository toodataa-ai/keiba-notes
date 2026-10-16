#!/usr/bin/env python3
"""Safe PRESTART replacement of only the current JRA canonical purchase plan.
v3.13 source STEP1, original predictions, PDF, original final_bets and proofs stay immutable.
"""
import copy,datetime as dt,hashlib,json,subprocess,sys
from pathlib import Path
import fitz
REG=Path('docs/data/races.json')
LOG=Path('docs/data/jra_publication_revision_log.json')
def need(ok,msg):
 if not ok:raise RuntimeError('BLOCKER JRA V315 PUBLISHER: '+str(msg))
def get(p):return json.loads(Path(p).read_text(encoding='utf8'))
def parse(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(dt.timezone.utc)
def g(*cmd):return subprocess.check_output(['git',*cmd],text=True).strip()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def key(x):
 from urllib.parse import quote
 return x['type']+':'+','.join(map(str,x['selection']))
def main():
 need(len(sys.argv)==6,'call with sealed-plan source, source snapshot, new html, new pdf, manifest filename')
 planpath,sourcepath,html,pdf,manifest=map(Path,sys.argv[1:])
 plan=get(planpath);source=get(sourcepath)
 now=dt.datetime.now(dt.timezone.utc)
 raceid=plan['source_race_id']
 need(plan['status']=='formal_prestart' and plan['purchase_strategy_version']=='v3.15','unsealed or invalid purchase version')
 need(plan['source_prediction_proof']==source['proof_commit'],'old source proof changed')
 need(plan['source_prediction_sha256']==sha(sourcepath),'source content changed')
 need(source['stage']=='formal_prestart' and source['prompt_version']=='v3.13','immutable v3.13 source required')
 start=parse(plan['race_context']['start_at'])
 need(now<start,'race has already started; no modification of current prediction')
 need(parse(plan['final_bets_fixed_at'])<start and parse(plan['final_bets_fixed_at'])>parse(source['final_bets_fixed_at']),'bad prereace times')
 need(plan['step1_fixed_at']==source['step1_fixed_at'],'STEP1 modified')
 need(plan['race_context']==source['race_context'],'race context changed')
 need(plan['quote_age_max_seconds']<=600 and plan['quote_capture_span_seconds']<=180,'stale/unsynchronized evidence')
 proof=plan['proof_commit'];need(len(proof)==40,'missing Git proof')
 snap=planpath.as_posix().replace('predictions','snapshots').replace('-sealed.json','.json')
 need(Path(snap).is_file(),'immutable pending snapshot missing')
 orig=json.loads(g('show',proof+':'+snap))
 want=copy.deepcopy(orig);want['status']='formal_prestart';want['proof_commit']=proof
 need(want==plan,'post-proof modification detected')
 need(parse(g('show','-s','--format=%cI',proof))<start,'proof commit after race start')
 tickets=plan['formal_bets']
 need(isinstance(tickets,list) and tickets and len(tickets)==plan['ticket_count'],'ticket count mismatch')
 need(len({key(t) for t in tickets})==len(tickets),'duplicate purchase ticket')
 need(sum(t['stake_yen'] for t in tickets)==plan['total_stake_yen']<=6000,'purchase budget mismatch')
 need(plan['command_count']<=5 and len(plan['regular_commands'])<=3,'too many purchase operations')
 for x in tickets:
  need(x['quote_verified'] is True and x['market_selection_id'] and x['source_url'] and x['observed_at'],'unverified price')
 need(plan['source_prediction_path']==sourcepath.as_posix(),'source path mismatch')
 need(Path(html).is_file() and Path(pdf).is_file(),'report missing')
 need(str(html).startswith('docs/reports/') and str(pdf).startswith('docs/pdfs/'),'unsafe public filenames')
 # Strict canonical reader-v1 contract: 5 front pages, all horse pages,
 # substantive dynamic-tail pages, no spill, no blank page or internal identifiers.
 # Execute on the actual PDF, not merely generated HTML or Actions green status.
 import importlib.util,re
 lpath=Path('.github/scripts/validate-jra-pdf-layout.py')
 spec=importlib.util.spec_from_file_location('approved_jra_reader_v1_validator',lpath)
 validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
 errors=validator.validate(html,pdf,Path('docs/data/jra_pdf_layout_policy_v1.json'))
 need(not errors,'reader-v1 PDF acceptance failed: '+'; '.join(errors[:6]))
 authored=html.read_text(encoding='utf8')
 horse_count=len(re.findall(r'<section class="horse">',authored))
 front_and_tail=len(re.findall(r'<section class="page">',authored))
 need(horse_count==plan['race_context']['sale_field_size'],'one reader page per horse')
 need(front_and_tail>=8,'reader-v1 missing front or complete tail pages')
 need('購入操作とJRA入力馬番' in authored and '採用買い目｜' in authored,
      'v3.15 full purchase report sections missing')
 with fitz.open(pdf) as doc:
  pagecount=len(doc)
  need(pagecount==horse_count+front_and_tail,'A4 report has overflow or missing page')
  need('最終購入予定' in doc[0].get_text(),'PDF purchase headline absent')
 master=get(REG)
 entries=[x for x in master['races'] if x.get('id')==raceid and x.get('scope')=='jra-main']
 need(len(entries)==1,'missing unique published canonical record')
 old=entries[0]
 need(old['status']=='predicted' and old.get('result') is None and old.get('review') is None,'postrace data cannot be overwritten')
 need(old['e2e_prediction']==sourcepath.as_posix() and old['proof_commit']==plan['source_prediction_proof'],
      'canonical changed since selection or proof')
 need(old['date']==source['race_context']['date'] and old['venue']==source['race_context']['venue'] and old['race']==source['race_context']['race_name'],'race identity mismatch')
 journal=get(LOG)
 need(not any(x.get('new_canonical',{}).get('proof_commit')==proof for x in journal['revisions']),'proof already published')
 new=copy.deepcopy(old)
 new.update(prompt_version='v3.13',purchase_strategy_version='v3.15',
  purchase_commands=plan['regular_commands'],
  medium_command=plan['medium_command'],large_command=plan['large_command'],
  purchase_comparison=plan['comparison_to_v313'],
  purchase_risk_metrics=plan['purchase_metrics'],
  report=str(html).removeprefix('docs/'),pdf=str(pdf).removeprefix('docs/'),
  pdf_mode='full',full_report_pages=pagecount,
  final_bets=copy.deepcopy(tickets),
  bets=[x['type']+' '+'-'.join(map(str,x['selection'])) for x in tickets],
  total_stake_yen=plan['total_stake_yen'],
  purchase_decision=plan['purchase_decision'],
  purchase_reason_code='v315_grouped_verified_positive_edge',
  final_bets_fixed_at=plan['final_bets_fixed_at'],
  e2e_prediction=planpath.as_posix(),proof_commit=proof)
 before=copy.deepcopy(old)
 new_total=len(new['final_bets'])
 need(new_total<=60,'unexpected more purchased selections than baseline')
 journal['revisions'].append({'race_id':raceid,
  'promoted_at_utc':now.isoformat(),'old_canonical':before,
  'new_canonical':{k:new[k] for k in ('prompt_version','purchase_strategy_version','report','pdf','e2e_prediction','proof_commit','final_bets_fixed_at')},
  'old_source_original_preserved':sourcepath.as_posix(),
  'old_pdf_preserved':before['pdf'],'html_sha256':sha(html),'pdf_sha256':sha(pdf),
  'user_requested_formal_three_command_policy':True})
 idx=master['races'].index(old)
 master['races'][idx]=new
 master['updated_at']=now.astimezone(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='milliseconds')
 REG.write_text(json.dumps(master,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 LOG.write_text(json.dumps(journal,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 Path(manifest).parent.mkdir(parents=True,exist_ok=True)
 Path(manifest).write_text(json.dumps({'schema_version':1,'status':'v3.15_purchase_formal_prestart','race_id':raceid,
  'source_prediction_path':sourcepath.as_posix(),'old_proof_commit':before['proof_commit'],
  'new_proof_commit':proof,'new_plan':str(planpath),'total_stake_yen':new['total_stake_yen'],
  'ticket_count':new_total,'regular_commands':len(plan['regular_commands']),
  'medium_method':plan['medium_command']['method'],'large_method':plan['large_command']['method'],
  'html_sha256':sha(html),'pdf_sha256':sha(pdf)},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('PASS_FORMAL_V315_CANONICAL_REPLACEMENT',raceid,'operations',plan['command_count'],'tickets',new_total,'investment_yen',new['total_stake_yen'],'pdf_pages',pagecount)
if __name__=='__main__':
 try:main()
 except Exception as ex:print(str(ex),file=sys.stderr);sys.exit(1)

