#!/usr/bin/env python3
"""Forward-only v3.15 publisher using the exact approved reader-v1 A4 CSS.
Historical v3.13 STEP1 and its original purchased lines remain unchanged.
The locked layout CSS is copied verbatim from docs/assets; proof SHAs stay in audit JSON.
"""
import argparse,hashlib,html,importlib.util,json,re
from pathlib import Path
import fitz
from weasyprint import HTML

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('locked_jra_v313_reader',HERE/'jra-render-live-v313.py')
legacy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
core=legacy.old
METHOD={'box':'BOX','single':'個別指定','formation':'フォーメーション',
 'key_wheel':'1頭軸流し','key_wheel_first':'1着軸流し','key_wheel_second':'2着軸流し',
 'key_wheel_multi':'軸馬マルチ','one_key_wheel':'1頭軸流し','two_key_wheel':'2頭軸流し',
 'one_key_fixed':'1頭固定','two_key_fixed':'2頭固定',
 'one_key_multi':'1頭軸マルチ','two_key_multi':'2頭軸マルチ',
 'multiple_singles':'複数単勝・複勝'}
GRADE=['A+','A','B+','B','B-','C']
MARK=['◎','○','▲','△','×']
def e(x):return html.escape(str(x),quote=True)
def para(x):return '<p>'+e(x)+'</p>'
def page(t,body):return core.page(t,body)
def tab(h,r):return core.rows_table(h,r)
def fmt(x,unit=''):
 return '未評価' if x is None else f'{float(x):,.2f}{unit}'
def price(t):
 x=t.get('market_odds')
 if isinstance(x,list):x=x[0] if x else None
 return fmt(x,'倍')
def read_make(p,source,source_bytes):
 if p.get('status')!='formal_prestart' or p.get('purchase_strategy_version')!='v3.15':
  raise ValueError('Sealed v3.15 only')
 if source.get('prompt_version')!='v3.13' or source.get('stage')!='formal_prestart':
  raise ValueError('No sealed v3.13 source')
 if hashlib.sha256(source_bytes).hexdigest()!=p.get('source_prediction_sha256'):
  raise ValueError('Source content hash mismatch')
 if source['proof_commit']!=p['source_prediction_proof'] or source['step1_fixed_at']!=p['step1_fixed_at']:
  raise ValueError('Historical proof or STEP1 mismatch')
 if source['race_context']!=p['race_context']:raise ValueError('Race metadata mismatch')
 tickets=p['formal_bets']
 if len(tickets)!=len({(b['type'],tuple(b['selection'])) for b in tickets}):
  raise ValueError('Duplicated final bets')
 if sum(x['stake_yen'] for x in tickets)!=p['total_stake_yen'] or p['total_stake_yen']>6000:
  raise ValueError('Incorrect stake')
 original=legacy.make(source)
 css=Path('docs/assets/jra-pdf-reader-v1.css').read_text(encoding='utf-8')
 if '<style>'+css+'</style>' not in original:raise ValueError('Approved reader-v1 CSS not retained')
 orig_pages=re.findall(r'<section class="page">.*?</section>',original,re.S)
 horse_pages=re.findall(r'<section class="horse">.*?</section>',original,re.S)
 if len(orig_pages)<8 or len(horse_pages)!=len(source['step1_ranking']):
  raise ValueError('Historical source report has incomplete sections')
 ctx=p['race_context']
 ranked=sorted(source['step1_ranking'],key=lambda h:(MARK.index(h['mark']),GRADE.index(h['overall_grade']),h['horse_number']))
 marks=' ／ '.join(f"{x['mark']}{x['horse_number']} {x['horse_name']}" for x in ranked if x['mark'] in MARK[:3])
 commands=p['regular_commands']+[p['medium_command'],p['large_command']]
 command_rows=[]
 for c in commands:
  if c['method']=='pass':
   command_rows.append((c['category'],'見送り','購入なし','0点','0円'))
  else:
   command_rows.append((c['category'],c['type']+' '+METHOD.get(c['method'],c['method']),
                        c['jra_input'],str(c['points'])+'点',f"{c['stake_yen']:,}円"))
 cover=page('本日の正式予想｜表紙',
  f'<h1>{e(ctx["venue"])}11R {e(ctx["race_name"])}</h1>'
  +para(f"{ctx['date']}　{ctx['surface']}{ctx['distance_m']}m　発走 {ctx['start_at'][11:16]}　能力v3.13／正式購入v3.15")
  +'<div class="hero"><div class="m">'+('購入候補あり' if tickets else '購入見送り')+'</div>'
  +para(f"最終購入予定{len(tickets)}点・{p['total_stake_yen']:,}円／上限6,000円。実際の投票完了を意味しません。")+'</div>'
  +'<h3>購入操作とJRA入力馬番</h3>'
  +tab(['区分','券種・方法','具体的な購入操作','点数','金額'],command_rows)
  +para('発走前STEP1の固定印：'+marks)
  +para('BOXやフォーメーションは正式採用組番と全点一致する場合にのみ表示。単独・複数購入方式は実オッズ取得後に評価しており、未確認価格から期待利益を創作しません。'))
 m=p['purchase_metrics']
 overview=page('購入ポートフォリオ｜正式v3.15最終判断',
  para('最新の実購入候補はv3.15の確定した組番と金額です。以前のv3.13で提案された多点購入案は履歴比較用の原本であり、新方式の購入指示ではありません。')
  +tab(['区分','券種・方法','JRA入力馬番','点数','金額'],command_rows)
  +tab(['監査項目','正式予想'],[
     ('最終購入額',f"{p['total_stake_yen']:,}円"),('個別買い目',str(len(tickets))+'点'),
     ('購入操作回数',str(p['command_count'])+'回'),
     ('中央モデル期待純利益',fmt(m.get('modeled_expected_net_profit_yen'),'円')),
     ('少なくとも1点の的中確率',fmt(100*m['modeled_union_hit_probability'],'%')),
     ('投資額に対する損失確率',fmt(100*m['modeled_net_loss_probability'],'%'))])
  +para('低・中央・高シナリオのうち新購入セットに対する値が検証できないものは監査JSON側で未評価とし、表に架空の数値を補記しません。前走成績と9軸の説明は個別馬ページに記載されています。'))
 # Exactly five approved reader front pages, horses unchanged, then dynamic tail.
 pages=[cover,*orig_pages[1:4],overview]
 adopted=[]
 parts=[tickets[i:i+8] for i in range(0,len(tickets),8)] or [[]]
 for i,subset in enumerate(parts,1):
  rows=[(x['type'],'-'.join(map(str,x['selection'])),f"{x['stake_yen']:,}円",price(x)) for x in subset]
  adopted.append(page(f'採用買い目｜{i}/{len(parts)}',
    para('v3.15で発走前に採用した実際の購入指示の完全な個別展開です。この表に存在しない組番は購入対象外です。表示額は各組番の購入金額で、BOX等を二重に買う指示ではありません。')
    +tab(['券種','馬番／買い目','購入額','確認したオッズ'],rows)
    +para(f"正式採用は全{len(tickets)}点、総額{p['total_stake_yen']:,}円。個別価格の出典、取得時刻、元の予想や二つの発走前proofは監査用JSONに記録しており、読者用PDFに識別子は掲載しません。")
    +para('オッズは発走前の観測値で、投票締切時点の価格とは異なることがあります。未校正の着順確率を用いるため期待利益や的中を保証しません。')))
 modes=source.get('purchase_set_comparisons_v312',{}).get('mode_comparisons',[])
 excluded=source.get('purchase_portfolio_selection',{}).get('optimizer_audit',{}).get('considered_excluded',[])
 unpriced=[x for x in source.get('ticket_candidate_comparisons',[]) if x.get('eligibility')=='unpriced']
 cmp=[]
 for x in modes:
  cmp.append((x.get('type','未確認'),METHOD.get(x.get('mode'),x.get('mode','未確認')),
              str(x.get('tickets',x.get('generated',0)))+'点',
              fmt(x.get('hit_pct'),'%'),fmt(x.get('profit_yen'),'円'),
              '旧v3.13方式の試算。現在の正式購入指示ではありません。'))
 for x in excluded:
  reason='期待利益が非正値' if x.get('reason_code')=='nonpositive_individual_expected_profit' else '旧方式の予算・利益・損失制約で非採用'
  cmp.append((x.get('type','未確認'),'-'.join(map(str,x.get('selection') or [])),
      '旧方式候補','非適用',fmt(x.get('expected_profit_yen'),'円'),reason))
 for x in unpriced:
  cmp.append((x.get('type','未確認'),'-'.join(map(str,x.get('selection') or [])),
      '未確認価格','非適用','未評価','実価格の証跡がないため期待値を算定しません。'))
 rejected=[]
 chunks=[cmp[i:i+6] for i in range(0,len(cmp),6)] or [[]]
 for i,subset in enumerate(chunks,1):
  rejected.append(page(f'不採用買い目｜{i}/{len(chunks)}',
    para('以下は比較対象の全方式と旧方式で除外した候補です。過去のv3.13モデルにおける試算で、現在の正式なv3.15購入セットではありません。個別組番の根拠・モデルの未確定を区別します。')
    +tab(['券種','購入方式・組番','点数','的中率','期待利益','判断の理由'],subset)
    +para('古いモデルの候補の期待値を新しい購入セットの期待値として流用しません。正確な実オッズ・組番に一致しない場合は算定不能です。過去の確定済み原本は変更していません。')))
 cv=source.get('exact_quote_coverage_v312',{})
 types=cv.get('by_type',[])
 audit=page('購入最適化監査｜新旧モデルの比較',
  para('WIN5は対象外。8券種の単点・軸流し・BOX・フォーメーション・マルチを複数組合せとして比較し、購入総額は6,000円を超えないことを監査しています。三連単は機械的に除外せず、価格証跡がある候補を評価します。')
  +tab(['券種','検討した点数','実価格あり','価格欠損'],
       [(x['type'],x['generated'],x['priced'],x['missing']) for x in types])
  +tab(['条件・判定項目','正式v3.15'],[
    ('最終投資額',f"{p['total_stake_yen']:,}円"),
    ('個別購入組番',str(len(tickets))+'点'),
    ('最終購入方式',str(p['command_count'])+'件'),
    ('モデル期待純利益',fmt(m.get('modeled_expected_net_profit_yen'),'円')),
    ('集合的中確率',fmt(100*m['modeled_union_hit_probability'],'%')),
    ('純損失確率',fmt(100*m['modeled_net_loss_probability'],'%')),
    ('旧v3.13と比較した期待利益差',fmt(p.get('comparison_to_v313',{}).get('expected_profit_yen'),'円')),
    ('旧v3.13と比較した集合的中率差',fmt(p.get('comparison_to_v313',{}).get('union_hit_pp'),'ポイント'))])
  +para('低・中央・高シナリオの新購入セットで根拠が不足する指標は未評価。価格が揃わない券種を非採算と決めつけません。期待値・的中確率は未校正の事前モデルからの推定で、実現利益を保証しません。'))
 head=original.split('<section class="page">',1)[0]
 rendered=head+''.join(pages)+''.join(horse_pages)+''.join(adopted)+''.join(rejected)+audit+'</body></html>'
 visible=re.sub(r'<[^>]*>',' ',rendered)
 if re.search(r'(?<![0-9a-fA-F])[0-9a-fA-F]{24,}(?![0-9a-fA-F])',visible):
  raise ValueError('Reader-facing report leaked an opaque identifier')
 return rendered,5+len(horse_pages)+len(adopted)+len(rejected)+1
def main():
 ap=argparse.ArgumentParser()
 for name in ('plan','source','html','pdf'):ap.add_argument('--'+name,required=True)
 z=ap.parse_args()
 p=json.loads(Path(z.plan).read_text(encoding='utf8'))
 data=Path(z.source).read_bytes()
 source=json.loads(data)
 result,expected=read_make(p,source,data)
 Path(z.html).parent.mkdir(parents=True,exist_ok=True)
 Path(z.pdf).parent.mkdir(parents=True,exist_ok=True)
 Path(z.html).write_text(result,encoding='utf8')
 HTML(string=result,base_url=str(Path.cwd())).write_pdf(z.pdf)
 with fitz.open(z.pdf) as pdf:
  if len(pdf)!=expected:raise ValueError(f'A4 PDF overflow: {len(pdf)} != {expected}')
 print('READER_V1_V315_RENDERED',len(source['step1_ranking']),'horses',expected,'pages')
if __name__=='__main__':main()
