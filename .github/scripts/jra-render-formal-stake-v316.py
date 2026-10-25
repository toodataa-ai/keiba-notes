#!/usr/bin/env python3
"""v3.16 standalone approved-reader-v1 render: stake-only overlay, historical pages intact."""
import argparse,copy,hashlib,importlib.util,json,re
from pathlib import Path
import fitz
from weasyprint import HTML

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('approved_formal_reader_v315',ROOT/'jra-render-formal-reader-v315.py')
prior=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

def main():
 ap=argparse.ArgumentParser()
 for x in ('plan','source','html','pdf'):ap.add_argument('--'+x,required=True)
 a=ap.parse_args()
 plan=json.loads(Path(a.plan).read_text(encoding='utf-8'))
 source_bytes=Path(a.source).read_bytes()
 source=json.loads(source_bytes)
 if plan.get('status')!='formal_prestart' or plan.get('purchase_strategy_version')!='v3.16':
  raise ValueError('separate v3.16 prestart proof required')
 if not plan.get('stake_optimization_audit',{}).get('shadow_proposal_available'):
  raise ValueError('no positive verified v3.16 amount proposal')
 if not plan.get('source_purchase_sha256') or len(plan.get('source_purchase_proof',''))!=40:
  raise ValueError('missing prior formal v3.15 proof')
 presentation=copy.deepcopy(plan)
 # The approved v3.15 reader generator is only reused in memory for layout.
 # No frozen v3.15 file or CSS is changed.
 presentation['purchase_strategy_version']='v3.15'
 for c in [*presentation['regular_commands'],presentation['medium_command'],presentation['large_command']]:
  if c.get('method')!='pass':
   c['jra_input']=f"{c['jra_input']}（1点{c['unit_stake_yen']:,}円）"
 html,expected=prior.read_make(presentation,source,source_bytes)
 for old,new in (
  ('能力v3.13／正式購入v3.15','能力v3.13／正式購入v3.16'),
  ('購入ポートフォリオ｜正式v3.15最終判断','購入ポートフォリオ｜正式v3.16最終判断'),
  ('最新の実購入候補はv3.15の確定した組番と金額です。',
   '最新の実購入候補はv3.16で確定した組番と金額です。金額を変えない方が良いと判定した買い目は元の100円を維持しています。'),
  ('v3.15で発走前に採用した実際の購入指示','v3.16で発走前に採用した実際の購入指示'),
  ('現在の正式なv3.15購入セット','現在の正式なv3.16購入セット'),
  ('正式v3.15','正式v3.16')):
  html=html.replace(old,new)
 if not re.search('（1点[123]00円）',html):
  raise ValueError('reader must show at least one exact unit stake')
 if '正式購入v3.16' not in html:raise ValueError('v3.16 publication version absent')
 if '<style>'+Path('docs/assets/jra-pdf-reader-v1.css').read_text()+'</style>' not in html:
  raise ValueError('approved CSS missing')
 Path(a.html).parent.mkdir(parents=True,exist_ok=True)
 Path(a.pdf).parent.mkdir(parents=True,exist_ok=True)
 Path(a.html).write_text(html,encoding='utf-8')
 HTML(string=html,base_url=str(Path.cwd())).write_pdf(a.pdf)
 with fitz.open(a.pdf) as pdf:
  if len(pdf)!=expected:raise ValueError(f'A4 overflow {len(pdf)} != {expected}')
 print('PASS_READER_V1_V316',len(source['step1_ranking']),'horses',expected,'A4 pages',plan['total_stake_yen'],'yen')
if __name__=='__main__':main()
