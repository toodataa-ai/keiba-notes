#!/usr/bin/env python3
"""Render complete v3.10 formal JRA report in approved reader-v1 layout.
No outside market data, probabilities, or new marks may enter at this point."""
import html,json,sys
from pathlib import Path
from itertools import islice
LABELS=['斤量','展開','馬場','ローテ','コース','血統','調教','騎手','基礎能力']
def h(x):return html.escape(str(x),quote=True)
def number(x,precision=1):
 return '未確定' if x is None else f'{x:,.{precision}f}'
def page(title,body):
 return f'<section class="page"><div class="chapter">{h(title)}</div>{body}</section>\n'
def rows_table(headers,data,cls='table dense'):
 s=f'<table class="{cls}"><thead><tr>'+''.join('<th>'+h(x)+'</th>' for x in headers)+'</tr></thead><tbody>'
 for row in data:s+='<tr>'+''.join('<td>'+h(x)+'</td>' for x in row)+'</tr>'
 return s+'</tbody></table>'
def make(report):
 race=report['race_context'];runners=report['step1_ranking'];n=len(runners)
 runners=sorted(runners,key=lambda t:({'◎':0,'○':1,'▲':2,'△':3,'×':4}[t['mark']],
    {'A+':0,'A':1,'B+':2,'B':3,'B-':4,'C':5}[t['overall_grade']],t['horse_number']))
 portfolio=report['purchase_portfolio_selection']
 lines=report['final_bets']
 coverage=report['strategy_coverage_audit']
 market=report['market_quote_audit']
 bought=report['purchase_decision']=='buy'
 cost=report['total_stake_yen']
 central=portfolio.get('expected_net_profit_yen_scenarios') or {}
 roi=portfolio.get('roi_scenarios') or {}
 loss=portfolio.get('loss_probability_scenarios') or {}
 full=portfolio.get('full_loss_probability_scenarios') or {}
 hit=portfolio.get('hit_probability_scenarios') or {}
 css=Path('docs/assets/jra-pdf-reader-v1.css').read_text(encoding='utf-8')
 body=''
 def paragraph(t):return '<p>'+h(t)+'</p>'
 marks=rows_table(['印','馬番','馬名','評価'],[(r['mark'],r['horse_number'],r['horse_name'],r['overall_grade']) for r in runners[:7]])
 body+=page('本日の正式予想｜表紙',f'<h1>{h(race["venue"])}11R {h(race["race_name"])}</h1>'
  +paragraph(f'{race.get("date","")}　{race["surface"]}{race["distance_m"]}m　発走 {race["start_at"][11:16]}　馬場 {race.get("official_going","未確認")}')
  +paragraph('GitHub正式プロンプト v3.10／STEP1印を事前固定、STEP2だけ実オッズと厳密期待純利益で判定。')
  +'<div class="hero"><div class="m">'+h('購入候補あり' if bought else '購入見送り')+'</div>'
  +paragraph(f'購入予定 {len(lines)}点／上限6,000円、モデル上の合計額 {cost:,}円（実購入は行っていません）')
  +paragraph('◎ '+', '.join(f'{x["horse_number"]} {x["horse_name"]}' for x in runners if x['mark']=='◎'))+'</div>'
  +'<h3>STEP1上位馬（市場オッズで印は変更していません）</h3>'+marks
  +'<h3>公開・検証状態</h3>'+paragraph('出馬表はJRA公式情報と照合。個別価格はスポーツナビの発走前中間オッズを正規化し、取得証跡と選択番号を固定。')
  +paragraph('本分析は未校正の能力モデルによる条件付き期待値で、実際の的中率や利益を保証するものではありません。'))
 body+=page('適用ルール・情報の鮮度',
  paragraph('STEP1は①斤量、②展開、③馬場、④ローテ、⑤コース、⑥血統、⑦調教、⑧騎手、⑨基礎能力で評価。'
   'JRA公式の近4走と過去に固定した印・総合評価を使用し、STEP2の価格を能力に入力しません。')
  +paragraph('芝とダートは別の馬場特性として評価し、JRAの公式馬場区分を取得。脚質・当日進路バイアスは十分な当日実走証拠がないため信頼度を制限しています。')
  +paragraph('馬場予測の良／稍重／重／不良の正確な分布は当日気象入力未整備のため未検証です。価格感応度は確率モデルの上振れ／下振れ仮定と区別します。')
  +paragraph('馬場の発走時点予測・調教時計・騎手の同条件補正データは欠損を明記し、未経験を不適性とみなしません。')
  +rows_table(['監査項目','状態'],[
   ('JRA出馬表','公式確認済み'),('馬場','公式区分を観測、発走時推定は未完成'),
   ('STEP1固定','実オッズ照会前の生成ログ・出典を確認'),
   ('オッズ','券種ごとの中間価格取得。発走まで変動あり'),
   ('確率校正','未実施。推定を検証済み的中率と表示しない'),
   ('購入','競走馬券の購入行為は行っていない')]))
 body+=page('STEP1 全頭能力・適性一覧',
  paragraph('以下は全頭の①〜⑨評価の統合結果です。詳細は各馬1ページの診断で確認できます。'
   '前走成績はJRA公式に照らした客観資料ですが、総合評価と印には推定が含まれます。')
  +rows_table(['印','馬番','馬名','総合','斤量','前走概要'],[(x['mark'],x['horse_number'],x['horse_name'],
   x['overall_grade'],str(x.get('weight_kg',''))+'kg',
   (x.get('past_performances') or [{}])[0].get('source_excerpt','データなし')[:14]) for x in runners])
  +paragraph('同条件直接実績を優先し、古い好走だけで現在値を判断しない。出走数とオッズは発走前に変わる可能性があります。'))
 body+=page('STEP2 8券種・購入方式の検証',
  paragraph('WIN5は対象外。単勝／複勝／枠連／馬連／馬単／ワイド／三連複／三連単について、単点・流し・BOX・フォーメーション・マルチ等を展開しています。')
  +rows_table(['券種','方式数','事前生成/実価格を確認した個別点'],[
   (s['type'],len(s['modes']),
     f'{len([c for c in report["ticket_candidate_comparisons"] if c["type"]==s["type"]])} / '+
     str(len([c for c in report['ticket_candidate_comparisons'] if c['type']==s['type'] and c['eligibility']=='eligible'])))
   for s in coverage])
  +paragraph('価格が得られない券種・組み合わせはオッズを創作せず除外し、取得可能な券種の検証を継続します。')
  +paragraph('フォーメーション等の全点購入と、そこから選択された一部買い目の購入を区別しています。')
  +paragraph(f'取得した個別選択価格 {market["verified"]}件／一致しない候補 {market["missing_individual_lines"]}件。'))
 body+=page('購入ポートフォリオ｜概要',
  paragraph('最適化第一目的：合計期待純利益（円）。1レースの予算上限6,000円。各馬券100円、正規化された同一買い目の重複は1回のみ。')
  +rows_table(['指標','推定値'],[
   ('購入予定総額',f'{cost:,}円'),('購入候補の最終件数',f'{len(lines)}点'),
   ('中央シナリオ期待純利益',number(central.get('central'))+'円' if bought else '算定対象外'),
   ('中央モデル期待回収率',number((roi.get('central') or 0)*100)+'%' if bought else '算定対象外'),
   ('少なくとも1点的中する確率',number((hit.get('central') or 0)*100)+'%' if bought else '算定対象外'),
   ('全点不的中の確率',number((full.get('central') or 0)*100)+'%' if bought else '算定対象外'),
   ('投資に対して純損失となる確率',number((loss.get('central') or 0)*100)+'%' if bought else '算定対象外'),
   ('未使用予算',f'{6000-cost:,}円')])
  +paragraph('低・中央・高の３つの条件付きシナリオを表示。複数馬券の同時的中・同時損失は同一着順事象上で合算しています。')
  +rows_table(['シナリオ','期待純利益','期待回収率'],[
   (a,number(central.get(a))+'円',number(100*(roi.get(a) or 0))+'%' if bought else '対象外') for a in ['low','central','high']])
  +paragraph('機械的に6,000円を使い切りません。モデル誤差・確率未校正・オッズ変化により実現損益は大きく変動します。'))
 for idx,r in enumerate(runners):
  num=r['horse_number'];name=r['horse_name'];mark=r['mark']
  direct=r.get('past_performances') or []
  rows=[]
  for p in direct[:4]:
   rows.append((p.get('date') or '不明',p.get('course') or '不明',
    f'{p.get("distance_m") or "?"}{p.get("surface") or ""}',p.get('class_name',''),
    (str(p.get('finish'))+'着') if p.get('finish') is not None else '不明',
    (p.get('time') or '?'),('同条件' if p.get('same_condition') else '近似/別条件')))
  while len(rows)<4:rows.append(('情報なし','—','—','—','—','—','—'))
  factors=rows_table(['①斤量','②展開','③馬場','④ローテ','⑤コース','⑥血統','⑦調教','⑧騎手','⑨能力'],
   [[*r['factor_grades']]],cls='table dense')
  note=r.get('evidence','')[:240]
  body+=f'<section class="horse"><div class="chapter">全頭診断・個別評価　{idx+1}/{n}</div>'
  body+=f'<h1>{h(mark)} {num} {h(name)}</h1>'
  body+=(f'<div class="hero"><b>総合 {h(r["overall_grade"])}</b>　負担重量 {h(r.get("weight_kg"))}kg'
  +f'　騎手 {h(r.get("jockey"))}</div>')
  body+=paragraph('能力と今回適性：'+note)
  body+='<h3>①〜⑨：評価軸別グレード</h3>'+factors
  body+='<h3>JRA公式・直近4走（同条件優先）</h3>'+rows_table(['日付','場','距離','クラス','着順','時計','比較'],rows)
  body+=paragraph('直接実績と類似条件：'+('このページに同競馬場同距離の走歴があります。' if any(p.get('same_condition') for p in direct)
   else '直近4走に完全一致する直接実績を確認できません。未知として処理します。'))
  body+=paragraph('最大の強み：'+('同条件で3着以内の実績' if any(p.get('same_condition') and p.get('finish') and p['finish']<=3 for p in direct)
   else '固定済みの能力・適性評価に該当する強み'))
  body+=paragraph('最大の不安：当日の馬場変化、斤量差、展開による再現性の不確実性。')
  body+=paragraph('負けるパターン：ペースが想定と逆方向に振れ、脚質・コース適性が発揮できない場合。')
  body+=paragraph('調教の一次時計・騎手コース別補正実績は未確認。過度な精度表現は避け、前走までの公式記録に基づきます。')
  body+='</section>\n'
 def buyTable(items):
  if not items:
   return paragraph('この範囲に最終購入候補はありません。モデル上の正の期待値と市場価格の証拠が揃わなければ投資額0円です。')
  return rows_table(['ID','券種','買い目','投資','実オッズ'],[(x['id'],x['type'],'-'.join(map(str,x['selection'])),
    str(x['stake_yen'])+'円',number(x['market_odds'][0] if isinstance(x['market_odds'],list) else x['market_odds']))
    for x in items])
 for k in range(3):
  cut=lines[k*20:(k+1)*20]
  body+=page('最終買い目｜'+str(k+1)+'/3',
   paragraph(f'以下は発走前固定のfinal_betsの一部。ページ{k+1}/3、最大20件。選択がゼロの場合は購入対象なし。')
   +buyTable(cut)
   +paragraph('発走前の中間オッズで計算。実際の発売価格は投票時に異なり得ます。'
    '購入候補は全券種の同一買い目を重複排除した個別馬券であり、投票済みの事実を表しません。')
   +paragraph(f'合計{len(lines)}点、投資予定総額{cost:,}円。公式成績とは独立した発走前予想原本に固定しています。')
   +paragraph('証跡に発走前Gitコミットを用い、公開後に都合よくオッズや買い目を書き換えません。モデルは未校正であり、過去結果への適合は未検証です。'))
 result='<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+h(race['race_name'])+' JRA v3.10予想</title><style>'+css+'</style></head><body data-full-report="true" data-authored-report="true">'+body+'</body></html>'
 return result
if __name__=='__main__':
 require=lambda ok,msg: (_ for _ in ()).throw(RuntimeError(msg)) if not ok else None
 require(len(sys.argv)==3,'Usage: python jra-render-live-v310.py formal.json docs/reports/slug.html')
 payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
 require(payload.get('prompt_version')=='v3.10' and payload.get('stage')=='formal_prestart','cannot render nonformal or unsealed prediction')
 dst=Path(sys.argv[2]);dst.parent.mkdir(parents=True,exist_ok=True)
 rendered=make(payload)
 dst.write_text(rendered,encoding='utf-8')
 print('AUTHORED_HTML',dst,len(rendered),'horses',len(payload['step1_ranking']))
