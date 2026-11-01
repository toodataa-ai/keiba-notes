#!/usr/bin/env python3
"""Append-only presentation repair: historical prediction, bets and PDFs remain immutable."""
import argparse,copy,datetime,hashlib,json,subprocess
from pathlib import Path
from zoneinfo import ZoneInfo
import fitz
REG=Path('docs/data/races.json')
LOG=Path('docs/data/jra-value-column-revision-log-v1.json')
def need(ok,msg):
 if not ok:raise RuntimeError('BLOCKER_VALUE_COLUMN_PUBLISH: '+msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(request):
 req=read(request);ids=req['race_ids']
 need(req['schema_version']==1 and ids==['2026-11-01-mahoroba-stakes','2026-11-01-tenno-sho-autumn'],'unexpected historic scope; must explicitly approve newer races')
 data=read(REG);revisions=read(LOG) if LOG.exists() else {'schema_version':1,'revisions':[]}
 now=datetime.datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
 outputs=[]
 for rid in ids:
  matches=[x for x in data['races'] if x['id']==rid and x['scope']=='jra-main']
  need(len(matches)==1,'missing canonical race '+rid)
  original=matches[0]
  need(original['status']=='predicted' and original.get('purchase_strategy_version')=='v3.15','only original predicted formal v3.15')
  need(not any(x['race_id']==rid for x in revisions['revisions']),'already presentation revised')
  for name in ('e2e_prediction','proof_commit','final_bets_fixed_at','step1_fixed_at'):
   need(bool(original.get(name)),name+' absent')
  planpath=Path(original['e2e_prediction']);plan=read(planpath)
  sourcepath=Path(plan['source_prediction_path']);source=read(sourcepath)
  need(plan['proof_commit']==original['proof_commit'] and plan['final_bets_fixed_at']==original['final_bets_fixed_at'],'canonical purchase proof differs')
  need(plan['source_prediction_proof']==source['proof_commit'],'frozen original source mismatch')
  old_html=Path('docs')/original['report'];old_pdf=Path('docs')/original['pdf']
  need(old_html.is_file() and old_pdf.is_file(),'historical original missing')
  new_html=old_html.with_name(old_html.stem+'-value-column-v1.html')
  new_pdf=old_pdf.with_name(old_pdf.stem+'-value-column-v1.pdf')
  need(not new_html.exists() and not new_pdf.exists(),'append-only filename already occupied')
  subprocess.run(['python3','.github/scripts/jra-v315-value-column-v1.py',
      '--plan',str(planpath),'--source',str(sourcepath),
      '--html-input',str(old_html),'--pdf-input',str(old_pdf),
      '--html-output',str(new_html),'--pdf-output',str(new_pdf)],check=True)
  with fitz.open(new_pdf) as pdf:
   pages=len(pdf)
  need(pages==original['full_report_pages'],'report page count changed')
  preserved=copy.deepcopy(original)
  revised=copy.deepcopy(original)
  revised['report']=str(new_html).removeprefix('docs/')
  revised['pdf']=str(new_pdf).removeprefix('docs/')
  unchanged=copy.deepcopy(revised)
  unchanged['report']=preserved['report'];unchanged['pdf']=preserved['pdf']
  need(unchanged==preserved,'protected canonical financial fields changed')
  data['races'][data['races'].index(original)]=revised
  revisions['revisions'].append({'race_id':rid,'presentation_only':True,'restored_at_jst':now,
    'old_html':preserved['report'],'old_pdf':preserved['pdf'],
    'old_html_sha256':sha(old_html),'old_pdf_sha256':sha(old_pdf),
    'new_html':revised['report'],'new_pdf':revised['pdf'],
    'new_html_sha256':sha(new_html),'new_pdf_sha256':sha(new_pdf),
    'immutable_prediction':original['e2e_prediction'],'immutable_proof_commit':original['proof_commit'],
    'final_bets_unchanged':True,'marks_unchanged':True,'original_artifacts_preserved':True})
  outputs.extend([str(new_html),str(new_pdf)])
 data['updated_at']=now
 REG.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 LOG.write_text(json.dumps(revisions,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('PASS_VALUE_COLUMN_ONLY_CANONICAL_POINTER',len(ids),'races',flush=True)
 for path in outputs: print('NEW_PRESENTATION_ONLY_ARTIFACT',path,flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--request',required=True)
 run(a.parse_args().request)
