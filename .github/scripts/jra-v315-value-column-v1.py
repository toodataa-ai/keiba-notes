#!/usr/bin/env python3
"""Presentation-only v3.15 value commentary. Never rewrite sealed forecasts or historical PDFs."""
import argparse,hashlib,html,json,re,tempfile
from pathlib import Path
import fitz
from weasyprint import HTML

TAG='data-jra-value-column="v1"'
TITLE='購入判断の理由（妙味・期待値）'
ANCHOR='<h3>購入操作とJRA入力馬番</h3>'
def fail(msg): raise ValueError('JRA_VALUE_COLUMN_V1_BLOCKER: '+msg)
def valid(ok,msg):
 if not ok: fail(msg)
def numbers(command):
 d=command.get('definition') or {}
 if isinstance(d.get('selection'),list): return d['selection'][:2]
 if isinstance(d.get('key'),int):
  others=d.get('partners') or []
  return [d['key']]+others[:1]
 if isinstance(d.get('horses'),list):return d['horses'][:2]
 keys=command.get('ticket_keys') or []
 if not keys:return []
 m=re.search(r'\[([0-9, ]+)\]',keys[0])
 return list(map(int,m.group(1).split(',')))[:2] if m else []
def column(plan,source):
 valid(plan.get('purchase_strategy_version')=='v3.15' and plan.get('status')=='formal_prestart','unsealed official plan')
 valid(source.get('stage')=='formal_prestart' and source.get('prompt_version')=='v3.13','unsealed original')
 valid(plan['source_prediction_proof']==source['proof_commit'] and plan['step1_fixed_at']==source['step1_fixed_at'],'source proof mismatch')
 valid(plan['race_context']==source['race_context'],'race context mismatch')
 valid(sum(x['stake_yen'] for x in plan['formal_bets'])==plan['total_stake_yen'],'final_bets/stake mismatch')
 horses={int(x['horse_number']):x['horse_name'] for x in source['step1_ranking']}
 metrics=plan['purchase_metrics']
 if plan['purchase_decision']=='pass':
  valid(not plan['formal_bets'] and plan['total_stake_yen']==0,'PASS cannot have bets')
  honmei=next((x['horse_name'] for x in source['step1_ranking'] if x['mark']=='◎'),None)
  valid(bool(honmei),'◎ missing')
  body=f'◎{honmei}を能力面で評価しましたが、実測オッズと複数購入方式を照合した結果、予算・期待利益・損失制約を満たす購入セットはありません。今回は見送りと判断します。'
  names=[honmei]
 else:
  commands=plan['regular_commands']
  valid(bool(commands),'BUY without regular operations')
  c=commands[0]
  selected=numbers(c)
  valid(1<=len(selected)<=2 and all(n in horses for n in selected),'missing named horse in first purchased operation')
  names=[horses[n] for n in selected]
  tickets=[x for x in plan['formal_bets'] if x['market_selection_id'] in c.get('ticket_keys',[])]
  valid(len(tickets)==c['points'] and all(x.get('quote_verified') is True for x in tickets),'first operation not matched to verified purchased tickets')
  odds=[x['market_odds'][0] if isinstance(x['market_odds'],list) else x['market_odds'] for x in tickets]
  valid(all(isinstance(x,(float,int)) and x>1 for x in odds),'real odds missing')
  first=f'{min(odds):g}倍' if min(odds)==max(odds) else f'{min(odds):g}～{max(odds):g}倍'
  valid(metrics.get('modeled_expected_net_profit_yen') is not None and metrics.get('modeled_net_loss_probability') is not None,'missing portfolio metrics')
  body=(f'{c["type"]}（{"・".join(names)}）は実測{first}を確認。'
        f'購入{len(plan["formal_bets"])}点・{plan["total_stake_yen"]:,}円のモデル期待純利益は'
        f'{metrics["modeled_expected_net_profit_yen"]:,.0f}円、損失確率{metrics["modeled_net_loss_probability"]*100:.1f}%。'
        '能力の印と購入時の妙味を分けて判断。推定値で利益は保証されません。')
 valid(30<len(body)<260,'value commentary unexpectedly short/long')
 return '<p '+TAG+'><strong>'+html.escape(TITLE)+'</strong>：'+html.escape(body)+'</p>',names

def apply(original,note):
 valid(TAG not in original,'commentary already present; refuse duplicate insertion')
 valid(original.count(ANCHOR)==1,'unique purchased ticket anchor absent')
 i=original.index(ANCHOR)
 close=original.find('</table>',i)
 section_end=original.find('</section>',i)
 valid(i<close<section_end,'purchased table not in front section')
 pos=close+len('</table>')
 return original[:pos]+note+original[pos:]

def verify_pdf(original_pdf,new_pdf,note,names):
 old=fitz.open(original_pdf)
 new=fitz.open(new_pdf)
 try:
  valid(len(old)==len(new),'new PDF paginated differently; do not publish')
  first=''.join(new[0].get_text().split())
  for word in [TITLE,*names]:
   valid(''.join(word.split()) in first,'missing rendered PDF commentary/horse name: '+word)
  valid(first.index(''.join(TITLE.split()))>first.index('購入操作とJRA入力馬番'),'commentary is not after purchased ticket header')
  for i in range(1,len(old)):
   if old[i].get_text()!=new[i].get_text():
    print('DIAGNOSTIC_PAGE_DIFF',i+1,
      'old_first',repr(old[i].get_text()[:180]),
      'new_first',repr(new[i].get_text()[:180]),flush=True)
    fail(f'PDF changed outside commentary cover at page {i+1}')
 finally:
  old.close();new.close()

def run(args):
 planpath=Path(args.plan)
 sourcepath=Path(args.source)
 plan=json.loads(planpath.read_text(encoding='utf8'))
 source_bytes=sourcepath.read_bytes()
 source=json.loads(source_bytes)
 valid(hashlib.sha256(source_bytes).hexdigest()==plan['source_prediction_sha256'],'historical prediction hash mismatch')
 note,names=column(plan,source)
 original=Path(args.html_input).read_text(encoding='utf8')
 revised=apply(original,note)
 out_html=Path(args.html_output);out_pdf=Path(args.pdf_output)
 valid(not out_html.exists() and not out_pdf.exists(),'append-only presentation revision paths already exist')
 out_html.parent.mkdir(parents=True,exist_ok=True)
 out_pdf.parent.mkdir(parents=True,exist_ok=True)
 out_html.write_text(revised,encoding='utf8')
 HTML(string=revised,base_url=str(Path.cwd())).write_pdf(str(out_pdf))
 valid(revised.replace(note,'',1)==original,'presentation-only HTML diff verification failed')
 # Existing immutable PDF can have a different renderer/font environment. Compare
 # before/after reflow in the SAME WeasyPrint 68 process, never against unreliable
 # historical rasterization. Original PDF bytes and all source artifacts stay untouched.
 with tempfile.TemporaryDirectory() as tempdir:
  baseline=Path(tempdir)/'unmodified-baseline.pdf'
  HTML(string=original,base_url=str(Path.cwd())).write_pdf(str(baseline))
  with fitz.open(args.pdf_input) as historical, fitz.open(baseline) as rerender:
   valid(len(historical)==len(rerender),'historical report page count drift')
  verify_pdf(baseline,out_pdf,note,names)
 import importlib.util
 spec=importlib.util.spec_from_file_location('jra_layout_gate',Path('.github/scripts/validate-jra-pdf-layout.py'))
 gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
 errors=gate.validate(out_html,out_pdf,Path('docs/data/jra_pdf_layout_policy_v1.json'))
 valid(not errors,'reader-v1 layout CI: '+'; '.join(errors[:5]))
 print('PASS_JRA_VALUE_COLUMN_V1',plan['source_race_id'],'pages',len(fitz.open(out_pdf)),'source_unchanged',hashlib.sha256(source_bytes).hexdigest(),'horse_names',','.join(names))
def main():
 a=argparse.ArgumentParser()
 for field in ('plan','source','html-input','pdf-input','html-output','pdf-output'):
  a.add_argument('--'+field,required=True)
 run(a.parse_args())
if __name__=='__main__':main()
