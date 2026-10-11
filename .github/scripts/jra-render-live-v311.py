#!/usr/bin/env python3
"""Render complete v3.11 formal JRA report in approved reader-v1 layout.
No outside market data, probabilities, or new marks may enter at this point."""
import html,json,sys
from pathlib import Path
from itertools import islice
LABELS=['斤量','展開','馬場','ローテ','コース','血統','調教','騎手','基礎能力']
# Reference colours are already defined in docs/assets/jra-pdf-reader-v1.css.
# Preserve the accepted stylesheet fingerprint: apply existing CSS classes only.
GRADE_CLASSES={'A+':'gAp','A':'gA','B+':'gBp','B':'gB','B-':'gBm','C':'gC'}
def grade_badge(value):
 if value not in GRADE_CLASSES:raise ValueError('Unexpected grade: '+str(value))
 return '<span class="g '+GRADE_CLASSES[value]+'">'+h(value)+'</span>'
def h(x):return html.escape(str(x),quote=True)
def number(x,precision=1):
 return '未確定' if x is None else f'{x:,.{precision}f}'
def page(title,body):
 return f'<section class="page"><div class="chapter">{h(title)}</div>{body}</section>\n'
def rows_table(headers,data,cls='table dense',grade_columns=()):
 s=f'<table class="{cls}"><thead><tr>'+''.join('<th>'+h(x)+'</th>' for x in headers)+'</tr></thead><tbody>'
 for row in data:
  s+='<tr>'+''.join('<td>'+(grade_badge(x) if i in grade_columns else h(x))+'</td>' for i,x in enumerate(row))+'</tr>'
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
 marks=rows_table(['印','馬番','馬名','評価'],[(r['mark'],r['horse_number'],r['horse_name'],r['overall_grade']) for r in runners[:7]],grade_columns=(3,))
 body+=page('本日の正式予想｜表紙',f'<h1>{h(race["venue"])}11R {h(race["race_name"])}</h1>'
  +paragraph(f'{race.get("date","")}　{race["surface"]}{race["distance_m"]}m　発走 {race["start_at"][11:16]}　馬場 {race.get("official_going","未確認")}')
  +paragraph('GitHub正式プロンプト v3.11／STEP1印を事前固定、STEP2のみ実オッズを使い、期待利益と集合的中率・実損率を比較して判定。')
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
   (x.get('past_performances') or [{}])[0].get('source_excerpt','データなし')[:14]) for x in runners],grade_columns=(3,))
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
  paragraph('最適化：期待純利益最大の基準解を確保した上で、利益下限・損失確率の制約内で集合的中率を改善。1レースの予算上限6,000円。各馬券100円、正規化された同一買い目の重複は1回のみ。')
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
   [[*r['factor_grades']]],cls='table dense',grade_columns=range(9))
  note=r.get('evidence','')[:240]
  body+=f'<section class="horse"><div class="chapter">全頭診断・個別評価　{idx+1}/{n}</div>'
  body+=f'<h1>{h(mark)} {num} {h(name)}</h1>'
  body+=(f'<div class="hero"><b>総合 {grade_badge(r["overall_grade"])}</b>　負担重量 {h(r.get("weight_kg"))}kg'
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
 # Dynamic tail sections: never drop candidates or impose a PDF page ceiling.
 # Fixed A4 typography / color and one-horse-per-page CSS remain untouched.
 def paginate_records(records,items_per_page):
  return [records[k:k+items_per_page] for k in range(0,len(records),items_per_page)] or [[]]
 def rows_page(headers,records):
  return rows_table(headers,records) if records else paragraph('該当する明細はありません。')
 def quote(x):
  v=x.get('market_odds')
  if isinstance(v,list):v=v[0] if v else None
  return number(v)+'倍' if v is not None else '未確認'
 balanced=portfolio.get('optimizer_audit',{}).get('balanced_selection')
 if not balanced:raise RuntimeError('PDF BLOCKER: balanced portfolio audit missing')
 excluded=portfolio.get('optimizer_audit',{}).get('considered_excluded')
 if not isinstance(excluded,list):raise RuntimeError('PDF BLOCKER: excluded candidates not in frozen model')
 unpriced=[x for x in report.get('ticket_candidate_comparisons',[]) if x.get('eligibility')=='unpriced']
 # Publish exact final_bets, including more than 60 rows if the purchase contract ever permits.
 select_chunks=paginate_records(lines,10)
 for i,block in enumerate(select_chunks,1):
  entries=[(x['id'],x['type'],'-'.join(map(str,x['selection'])),str(x['stake_yen'])+'円',quote(x)) for x in block]
  intro=paragraph('購入は個別チケット全件の発走前確定候補です。重複馬券は除き、券種・買い目・購入額・観測したオッズを一意に列記します。')
  summary=paragraph(f'採用{len(lines)}点、総投資{cost:,}円、余剰予算{6000-cost:,}円。実投票済みを意味しません。')
  why=paragraph('集合で採用する理由：利益下限と実損リスクの制約内で、複数の馬券に流したときの集合的中率を検証しています。') if i==1 else ''
  body+=page(f'採用買い目｜{i}/{len(select_chunks)}',
   intro+rows_page(['ID','券種','買い目','投資','実オッズ'],entries)+summary+why
   +paragraph('個別オッズの出典と取得時刻、購入方式、発走前証跡は発走前JSONに全件保存されています。'))
 reasons=[]
 for i,x in enumerate(sorted(excluded,key=lambda x:(-float(x.get('expected_profit_yen') or 0),str(x.get('key')))),1):
  reason='個別期待利益が0円以下。補完効果も集合の制約内では採用されなかった。' if x.get('reason_code')=='nonpositive_individual_expected_profit' else '単独期待利益は正だが、予算と集合的中率・期待利益下限・実損リスクの組合せ比較で不採用。'
  reasons.append(('X'+str(i).zfill(4),x.get('type',''),'-'.join(map(str,x.get('selection') or [])),number(x.get('expected_profit_yen'))+'円',reason))
 for i,x in enumerate(unpriced,1):
  reasons.append(('U'+str(i).zfill(4),x.get('type',''),'-'.join(map(str,x.get('selection') or [])),'算定不可','発走前の当該買い目の実オッズ未確認。買い目の購入資格がない。'))
 reject_chunks=paginate_records(reasons,7)
 for i,block in enumerate(reject_chunks,1):
  body+=page(f'不採用買い目｜{i}/{len(reject_chunks)}',
   paragraph('不採用候補を省略せず全件掲載します。Xは価格確認済みで不採用、Uは個別実オッズ未確認です。')
   +rows_page(['ID','券種','買い目','期待利益','不採用理由'],block)
   +paragraph(f'全不採用候補 {len(reasons)}点（価格確認済 {len(excluded)}点、実オッズ未確認 {len(unpriced)}点）。')
   +paragraph('個別期待利益が低い理由と、個別期待利益がプラスでも集合の投資最適性で落とした理由を区別。')
   +paragraph('予想時点の不採用理由と、発走後に採用馬券が不的中となった回顧理由は別です。'))
 risk_rows=[
  ('期待純利益',number(balanced.get('baseline_expected_profit_yen'))+'円',number(central.get('central'))+'円' if bought else '対象外'),
  ('集合的中確率',number(100*balanced.get('baseline_hit_probability',0))+'%',number(100*hit.get('central',0))+'%' if bought else '対象外'),
  ('実損確率',number(100*balanced.get('baseline_net_loss_probability',0))+'%',number(100*loss.get('central',0))+'%' if bought else '対象外'),
  ('許容する利益低下','比較基準0円',number(balanced.get('expected_profit_sacrifice_yen'))+'円'),
  ('確保する期待純利益の下限','比較の基準解',number(balanced.get('expected_profit_floor_yen'))+'円')]
 body+=page('購入最適化監査｜基準解と集合的中率',
  paragraph('1つのレースの同時着順分布を使い、馬連・ワイド・三連複・三連単などの複数買い目が同時的中する場合も二重に数えません。')
  +rows_table(['比較項目','期待利益最大の基準解','今回の集合改善案'],risk_rows)
  +paragraph('3シナリオ：発走前に凍結した低・中央・高の着順確率で、セット全体の損益を再計算しています。')
  +rows_table(['条件','期待純利益','集合的中率','実損確率'],[
   (sc,number(central.get(sc))+'円' if bought else '対象外',
    number(100*hit.get(sc,0))+'%' if bought else '対象外',
    number(100*loss.get(sc,0))+'%' if bought else '対象外')
   for sc in ['low','central','high']])
  +paragraph('期待利益は厳密最大解から最大10%かつ200円以内の減少を許容。実損確率の悪化は2ポイント以内、集合的中率の改善が1ポイント未満なら基準解を維持。')
  +paragraph('多目的最適化は決定的な近傍探索です。期待利益最大の基準解は厳密ですが、集合的中率の大域最適解の証明ではありません。')
  +paragraph('根拠のある中間オッズのみ使用。利益や的中率は未校正の条件付き推定であり、結果を保証しません。'))
 result='<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+h(race['race_name'])+' JRA v3.11予想</title><style>'+css+'</style></head><body data-full-report="true" data-authored-report="true" data-tail-pagination="dynamic">'+body+'</body></html>'
 return result
if __name__=='__main__':
 require=lambda ok,msg: (_ for _ in ()).throw(RuntimeError(msg)) if not ok else None
 require(len(sys.argv)==3,'Usage: python jra-render-live-v311.py formal.json docs/reports/slug.html')
 payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
 require(payload.get('prompt_version')=='v3.11' and payload.get('stage')=='formal_prestart','cannot render nonformal or unsealed prediction')
 dst=Path(sys.argv[2]);dst.parent.mkdir(parents=True,exist_ok=True)
 rendered=make(payload)
 dst.write_text(rendered,encoding='utf-8')
 print('AUTHORED_HTML',dst,len(rendered),'horses',len(payload['step1_ranking']))
