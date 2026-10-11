#!/usr/bin/env python3
"""Print one A4 stage-only cover from separately audited research data.
Original JRA prediction, final_bets, report HTML and PDFs are immutable."""
import argparse,json,re,html
from pathlib import Path
from weasyprint import HTML
import fitz
def esc(x):return html.escape(str(x),quote=True)
def yen(x):return f'{int(x):,}円'
def make(data):
 assert data['formal_final_bets_unchanged'] is True
 assert len(data['regular_commands'])<=3
 assert data['ana_command']['row']==4
 assert data['summary']['stake_yen']<=6000
 commands=data['regular_commands']+[data['ana_command']]
 assert len(commands)<=4
 tot=sum(c.get('stake_yen',0) for c in commands)
 assert tot==data['summary']['stake_yen']
 out=[]
 methods={'box':'BOX','single':'個別指定','formation':'フォーメーション',
  'key_wheel':'1頭軸流し','two_key_wheel':'2頭軸流し','one_key_wheel':'1頭軸流し',
  'key_wheel_first':'1着固定流し','key_wheel_second':'2着固定流し',
  'key_wheel_multi':'マルチ','two_key_fixed':'2頭軸固定',
  'two_key_multi':'2頭軸マルチ','one_key_fixed':'1頭軸固定',
  'one_key_multi':'1頭軸マルチ'}
 for c in commands:
  is_ana=c['category']=='穴狙い'
  method='見送り' if c['method']=='pass' else (
    (c['type']+' 個別指定') if is_ana else methods.get(c['method'],c['method']))
  type_label=('穴狙い' if is_ana else c['type'])
  number_text=c['jra_input']
  pay=(f"{c['points']}点 × {yen(c['unit_stake_yen'])} ＝ {yen(c['stake_yen'])}"
       if c['points'] else '購入なし・0円')
  out.append(f'<tr class="{"ana" if is_ana else "normal"}"><td><b>{esc(type_label)}</b>'
   f'<small>{esc(method)}</small></td><td class="spec">{esc(number_text)}</td>'
   f'<td class="money">{esc(pay)}</td></tr>')
 title='東京11R オクトーバーステークス' if 'october-stakes' in data['race_id'] else '京都11R スワンステークス'
 m=data['summary']
 return '''<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>
@page { size: A4 portrait; margin: 15mm 13mm 16mm; }
body{font-family:"Noto Sans CJK JP","Meiryo",sans-serif;color:#222e3a;font-size:10pt;line-height:1.55}
header{border-bottom:2px solid #a72239;padding-bottom:10px;margin-bottom:17px}
.kicker{font-weight:bold;color:#a72239;font-size:9pt;letter-spacing:.08em}
h1{font-size:19pt;margin:5px 0 0}
h2{font-size:12pt;margin:16px 0 8px}
p{margin:8px 0}
.warn{font-weight:bold;font-size:9pt;background:#fff6e8;border-left:3px solid #b0802a;padding:9px 10px}
table{width:100%;border-collapse:collapse;table-layout:fixed;page-break-inside:avoid}
th{background:#f0f2f5;font-size:9pt;color:#344151;text-align:left;padding:9px 8px;border-bottom:1px solid #bac1ca}
td{border-bottom:1px solid #d7dce2;padding:10px 8px;vertical-align:top;overflow-wrap:anywhere}
th:nth-child(1),td:nth-child(1){width:21%}th:nth-child(2),td:nth-child(2){width:43%}th:nth-child(3),td:nth-child(3){width:36%}
td small{display:block;font-size:8pt;color:#657386;margin-top:2px}
td.spec{font-weight:550;line-height:1.8}td.money{font-weight:bold;font-size:9pt}
tr.ana{background:#fff7ed}tr.ana td{border-top:2px solid #d8b682}
.metrics{padding:11px;background:#f2f4f7;border-radius:5px;margin-top:14px;font-size:9pt}
.foot{margin-top:16px;padding-top:8px;border-top:1px solid #cbd1d8;color:#677181;font-size:8pt}
</style></head><body><header><div class="kicker">STAGING v1.01 ／ 購入指示コンパクト化・検証見本</div>
<h1>'''+esc(title)+'''</h1></header>
<p class="warn">これは発走前に封印された正式版v3.13とは異なる、3操作＋穴狙いの研究案です。
実際の購入指示として使用しないでください。</p>
<h2>通常最大3操作 ＋ 穴狙い1行</h2>
<table><thead><tr><th>券種・買い方</th><th>JRA画面に指定する馬番</th><th>点数 × 単価 ＝ 金額</th></tr></thead>
<tbody>'''+''.join(out)+'''</tbody></table>
<div class="metrics"><b>合計：'''+yen(tot)+'''</b>（'''+str(m['command_count'])+'''操作）
　／　モデル期待純利益：'''+yen(m['modeled_expected_net_profit_yen'])+'''
　／　推定的中確率：'''+f"{m['modeled_union_hit_probability']*100:.1f}%"+'''
　／　推定損失確率：'''+f"{m['modeled_net_loss_probability']*100:.1f}%"+'''</div>
<p class="foot">通常と穴狙いで重複した組番を含まず、総額6,000円以内。各行のBOX・流し・フォーメーションの組番を展開して監査済み。
穴狙いは20倍以上かつ推定事象確率10%以下・正のモデル期待値を条件とします。モデルは未校正、オッズは取得時点の中間値で確定値ではありません。正式予想・過去原本は一切変更していません。</p>
</body></html>'''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--pdf',required=True);a=ap.parse_args()
 assert a.input.startswith('docs/staging/data/three-plus-ana/')
 assert a.pdf.startswith('docs/staging/pdfs/')
 data=json.loads(Path(a.input).read_text(encoding='utf8'))
 target=Path(a.pdf);target.parent.mkdir(parents=True,exist_ok=True)
 HTML(string=make(data),base_url=str(Path('.').resolve())).write_pdf(str(target))
 with fitz.open(str(target)) as pdf:
  assert len(pdf)==1,f'preview must be exactly one A4 page; got {len(pdf)}'
  page=pdf[0]
  assert abs(page.rect.width-595.28)<1 and abs(page.rect.height-841.89)<1
  text=re.sub(r'\s+','',page.get_text()) # normalize PDF line breaks, never skip or shorten content
  for token in ('STAGING','穴狙い','モデル期待純利益','6,000円以内','購入指示として使用しないでください'):
   assert token in text,'A4 missing '+token
  for block in page.get_text('dict')['blocks']:
   if 'lines' not in block:continue
   for line in block['lines']:
    for span in line['spans']:
     assert span['bbox'][0]>=0 and span['bbox'][2]<page.rect.width+1
     assert span['bbox'][1]>=0 and span['bbox'][3]<page.rect.height+1
 print('PASS_STAGING_A4_4_ROW_PDF',target,data['race_id'],'operations',data['summary']['command_count'])
if __name__=='__main__':main()

