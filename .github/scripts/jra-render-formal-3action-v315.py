#!/usr/bin/env python3
"""One current purchasable JRA v3.15 3+2 report, preserving v3.13 marks.
Not a rewrite of prior report or STEP1. One A4 page/horse plus purchase front.
"""
import argparse,json,html,re
from jra_v315_horse_layout import HORSE_STYLE, render_horse
from pathlib import Path
from weasyprint import HTML
import fitz
def e(v):return html.escape(str(v),quote=True)
def yen(v):return f'{int(v):,}円'
NAMES={'box':'BOX','single':'個別指定','formation':'フォーメーション',
 'key_wheel':'1頭軸流し','key_wheel_first':'1着固定流し',
 'key_wheel_second':'2着固定流し','key_wheel_multi':'馬単1頭軸マルチ',
 'one_key_wheel':'1頭軸流し','two_key_wheel':'2頭軸流し',
 'two_key_fixed':'2頭軸固定','two_key_multi':'2頭軸マルチ',
 'one_key_fixed':'1頭軸固定','one_key_multi':'1頭軸マルチ'}
STYLE="""<style>
@page { size:A4 portrait; margin:14mm 13mm 14mm; }
body{font-family:"Noto Sans CJK JP","Meiryo",sans-serif;color:#263143;font-size:9.5pt;line-height:1.58}
h1{font-size:19pt;margin:5px 0 10px}h2{font-size:14pt;margin:6px 0}h3{font-size:11pt}
small,.meta{color:#59687b;font-size:8pt}
.kicker{font-weight:700;color:#a62a41;font-size:9pt}
.page{break-after:page} .page:last-child{break-after:auto}
h1,h2,h3{break-after:avoid}
table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:9pt}
th{background:#eef0f4;text-align:left;color:#455063;border-bottom:1px solid #bdc6d1}
th,td{padding:8px 6px;vertical-align:top;border-bottom:1px solid #d9dee6;overflow-wrap:anywhere}
table col:nth-child(1){width:22%}table col:nth-child(2){width:46%}table col:nth-child(3){width:32%}
.method{color:#617184;font-size:8pt}.numbers{font-weight:600;font-variant-numeric:tabular-nums}
h3.hole{color:#93502d;font-size:10pt;margin:16px 0 5px}
div.totals{background:#f2f4f7;margin-top:12px;padding:10px}
.disclosure{background:#fff8ef;border-left:3px solid #bd8d5f;padding:9px;font-size:9pt}
.rider{margin-top:16px;font-size:8.6pt;color:#475366}
.fact{border:1px solid #e0e4e9;padding:10px;margin:9px 0}
</style>"""
def line(c):
 method='見送り' if c['method']=='pass' else NAMES.get(c['method'],c['method'])
 return f"<tr><td><b>{e(c.get('type','見送り'))}</b><div class='method'>{e(method)}</div></td><td class='numbers'>{e(c['jra_input'])}</td><td>{e(str(c['points']))}点 × {yen(c['unit_stake_yen'])} ＝ <b>{yen(c['stake_yen'])}</b></td></tr>" if c['points'] else f"<tr><td>見送り</td><td>{e(c['jra_input'])}</td><td>購入なし・0円</td></tr>"
def ticket_table(rows,heads=True):
 return ('<table><colgroup><col/><col/><col/></colgroup>'+
         ('<thead><tr><th>券種・買い方</th><th>馬番／購入操作</th><th>点数 × 単価＝金額</th></tr></thead>' if heads else '')+
         '<tbody>'+''.join(line(x) for x in rows)+'</tbody></table>')
def html_report(p,source):
 ctx=p['race_context']
 title=f"{ctx['date']}　{ctx['venue']}{ctx['race_no']}R　{ctx['race_name']}"
 m=p['purchase_metrics']
 assert p['purchase_strategy_version']=='v3.15' and p['status']=='formal_prestart' and len(p['regular_commands'])<=3
 assert p['total_stake_yen']==sum(x['stake_yen'] for x in p['formal_bets'])
 front=f"""<section class="page"><div class="kicker">JRA 正式購入セット v3.15 ／ 能力・適性評価 v3.13</div>
<h1>{e(title)}</h1>
<p class="meta">2026年10月12日の発走前情報だけで確定。馬番・券種・点数・購入額を1行ずつ照合済み。
通常の購入操作は最大3行、中穴・大穴は別枠で最大1行ずつです。</p>
<h2>通常の購入操作（最大3行）</h2>{ticket_table(p['regular_commands'])}
<h3 class='hole'>中穴（実測20倍以上100倍未満）</h3>{ticket_table([p['medium_command']],False)}
<h3 class='hole'>大穴（100円で的中時払戻1万円以上）</h3>{ticket_table([p['large_command']],False)}
<div class='totals'><b>総投資額：{yen(p['total_stake_yen'])}</b>　／　購入操作 {p['command_count']} 回
<p>モデル期待純利益：{m['modeled_expected_net_profit_yen']:.0f}円、
推定的中確率：{m['modeled_union_hit_probability']*100:.2f}%、
推定損失確率：{m['modeled_net_loss_probability']*100:.2f}%</p></div>
<p class='disclosure'>発走前オッズは取得時点の価格であり、最終オッズではありません。過去v3.13の60点方式とは
実際の購入点数・期待利益・的中率が異なります。推定モデルは未校正で、的中・利益は保証されません。</p>
<p class='meta'>固定済み発走前原本：{e(p['source_prediction_proof'])}<br>
新方式の発走前証跡：{e(p['proof_commit'])}／研究対象の旧買い目は履歴に保存</p>
</section>"""
 # The v3.13 source remains sealed; labels and typography alone change here.
 ranked=source.get('step1_ranking') or []
 if not ranked:
  raise ValueError('JRA_FORMAL_V315_BLOCKER: source STEP1 per-horse ranking missing')
 bodies=[render_horse(x,p['step1_fixed_at'],p['source_prediction_proof']) for x in ranked]
 return f'<!doctype html><html lang="ja"><head><meta charset="utf-8">{STYLE}{HORSE_STYLE}</head><body>{front}{"".join(bodies)}</body></html>',1+len(bodies)

def main():
 ap=argparse.ArgumentParser()
 for x in ['plan','source','html','pdf']:ap.add_argument('--'+x,required=True)
 z=ap.parse_args()
 p=json.loads(Path(z.plan).read_text())
 source=json.loads(Path(z.source).read_text())
 htmltext,pages=html_report(p,source)
 Path(z.html).parent.mkdir(parents=True,exist_ok=True)
 Path(z.pdf).parent.mkdir(parents=True,exist_ok=True)
 Path(z.html).write_text(htmltext,encoding='utf8')
 HTML(string=htmltext,base_url=str(Path.cwd())).write_pdf(z.pdf)
 with fitz.open(z.pdf) as d:
  assert len(d)==pages,('PDF must have exact purchase front + 1 per horse',len(d),pages)
  for i,page in enumerate(d):
   assert abs(page.rect.width-595.28)<1 and abs(page.rect.height-841.89)<1
   t=page.get_text()
   assert len(t)>100 and ('STEP1' in t if i>0 else '総投資額' in t)
   for block in page.get_text('dict')['blocks']:
    if 'lines' not in block:continue
    for l in block['lines']:
     for span in l['spans']:
      b=span['bbox']
      assert b[0]>=-1 and b[2]<=page.rect.width+1 and b[1]>=-1 and b[3]<=page.rect.height+1,('PDF content outside page',i,span['text'])
 print('PASS_JRA_V315_A4_3_ACTIONS_PLUS_TWO_TIERS_AND_ONE_HORSE_PER_PAGE',p['source_race_id'],pages)
if __name__=='__main__':main()

