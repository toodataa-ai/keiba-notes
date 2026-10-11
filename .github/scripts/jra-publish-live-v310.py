#!/usr/bin/env python3
"""Only after proof-commit sealed and full PDF per-page guard passed:
append today's real JRA main races to public registry. Never alter older entries."""
import datetime,json,sys
from pathlib import Path
def require(ok,message):
 if not ok:raise RuntimeError('BLOCKER: '+message)
races_file=Path('docs/data/races.json')
root=json.loads(races_file.read_text(encoding='utf-8'))
for path in sys.argv[1:]:
 p=Path(path);o=json.loads(p.read_text(encoding='utf-8'))
 require(o.get('stage')=='formal_prestart' and o.get('prompt_version')=='v3.10','not a formal sealed prediction '+str(p))
 r=o['race_context'];slug=o['race_id']
 html_path='reports/'+slug+'.html';pdf_path='pdfs/'+slug+'.pdf'
 require(Path('docs',html_path).exists() and Path('docs',pdf_path).exists(),'report/PDF pair not available')
 require(not any(e['id']==slug for e in root['races']),'existing race entry cannot be replaced '+slug)
 marks={k:next((f'{x["horse_number"]} {x["horse_name"]}' for x in o['step1_ranking'] if x['mark']==m),None)
  for k,m in [('win','◎'),('second','○'),('third','▲')]}
 require(all(marks.values()),'missing fixed marks')
 lines=o.get('final_bets') or []
 root['races'].append(dict(id=slug,date=r['date'],venue=r['venue'],race=r['race_name'],scope='jra-main',
  prompt_version='v3.10',status='predicted',source='jra-live-source-capture-prerace-fixed',
  eligible_for_learning=False,field_size=r['sale_field_size'],
  report=html_path,pdf=pdf_path,pdf_mode='full',full_report_pages=r['sale_field_size']+8,
  marks=marks,bets=[x['type']+' '+'-'.join(map(str,x['selection'])) for x in lines],
  purchase_decision=o['purchase_decision'],purchase_reason_code=o['purchase_reason_code'],
  total_stake_yen=o['total_stake_yen'],final_bets=lines,final_bets_fixed_at=o['final_bets_fixed_at'],
  step1_fixed_at=o['step1_fixed_at'],e2e_prediction=str(p),
  proof_commit=o['proof_commit'],purchase_budget_yen=6000,
  note='Frozen official-prerace JSON + JRA primary form and separately verified Sportnavi odds. Model is not historically calibrated; bets represent recommendations, not actual wagers.'))
root['updated_at']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='milliseconds')
races_file.write_text(json.dumps(root,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('JRA_PUBLIC_REGISTRY',[(x['id'],x['total_stake_yen'],x['full_report_pages']) for x in root['races'] if x['date']=='2026-10-11'])
