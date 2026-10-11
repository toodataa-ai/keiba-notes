#!/usr/bin/env python3
"""Synthetic rendering only: v3.12 PDF must show 1/5/10/final comparisons, every
mode, frozen bets, all horse pages, and exact audit proof. No claim of live prices."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
fixture=json.loads(Path('/tmp/jra-v311-pdf-fixture.json').read_text(encoding='utf-8'))
fixture['prompt_version']='v3.12'
fixture['race_context']['race_name']='合成 v3.12 比較監査レース'
fixture['exact_quote_coverage_v312']={
 'status':'complete','total_candidates':4,'priced':4,'missing_count':0,
 'by_type':[{'type':'単勝','generated':4,'priced':4,'missing':0}],'missing_lines':[]}
base=fixture['purchase_portfolio_selection']
lines=fixture.get('final_bets',[])
central=base.get('hit_probability_scenarios') or {}
sets=[{'kind':'illustrative_max_marginal_hit','label':'的中率優先 1点','tickets':1,
       'stake_yen':100,'hit_pct':25,'profit_yen':12},
      {'kind':'illustrative_max_marginal_hit','label':'的中率優先 5点','tickets':5,
       'stake_yen':500,'hit_pct':45,'profit_yen':-30},
      {'kind':'illustrative_max_marginal_hit','label':'的中率優先 10点','tickets':10,
       'stake_yen':1000,'hit_pct':55,'profit_yen':-50},
      {'kind':'final_balanced','label':'最終採用セット','tickets':len(lines),
       'stake_yen':fixture.get('total_stake_yen',0),
       'hit_pct':central.get('central',0)*100,'profit_yen':23}]
modes=[{'strategy_id':'T%03d'%i,'type':(['単勝','馬連','三連複','三連単'][i%4]),
        'mode':'synthetic-formation','tickets':3,'generated':3,'status':'evaluated',
        'hit_pct':8+i*.7,'profit_yen':3-i,'loss_pct':60+i*.1}
       for i in range(1,41)]
fixture['purchase_set_comparisons_v312']={
 'version':'v3.12','original_purchase_unchanged':True,
 'comparison_sets':sets,'mode_comparisons':modes,
 'search_diagnostic':{'tested_portfolios':0,'no_marginal_hit_gain':15,
   'positive_marginal_hit_candidates':3,
   'zero_trial_reason':'v311_neighbourhood_pruned_all_proposals_before_full_evaluation_check_profit_floor_and_loss_guard'}}
with tempfile.TemporaryDirectory(prefix='jra-v312-pdf-') as d:
 p=Path(d);prediction=p/'prediction.json';prediction.write_text(json.dumps(fixture,ensure_ascii=False),encoding='utf-8')
 html=p/'report.html';pdf=p/'report.pdf'
 env={**os.environ,'JRA_SELECTED_ROWS_PER_PAGE':'4','JRA_REJECTED_ROWS_PER_PAGE':'4',
      'JRA_AUDIT_ROWS_PER_PAGE':'7'}
 subprocess.run([sys.executable,'.github/scripts/jra-render-live-v312.py',str(prediction),str(html)],
                cwd=ROOT,env=env,check=True)
 source=html.read_text(encoding='utf-8')
 assert '的中率優先 5点' in source and '的中率優先 10点' in source
 assert 'T040' in source and '探索と価格網羅性' in source
 subprocess.run([sys.executable,'-m','weasyprint',str(html),str(pdf)],cwd=ROOT,check=True)
 proc=subprocess.run([sys.executable,'.github/scripts/validate-jra-pdf-content-v312.py',
                      '--html',str(html),'--pdf',str(pdf),'--prediction',str(prediction)],
                     cwd=ROOT,text=True,capture_output=True)
 assert proc.returncode==0,proc.stdout+'\n'+proc.stderr
 tampered=p/'tampered.html';tampered.write_text(source.replace('<td>T040</td>','<td>欠落</td>'),encoding='utf-8')
 fail=subprocess.run([sys.executable,'.github/scripts/validate-jra-pdf-content-v312.py',
                      '--html',str(tampered),'--pdf',str(pdf),'--prediction',str(prediction)],
                     cwd=ROOT,text=True,capture_output=True)
 assert fail.returncode!=0 and 'T040' in fail.stdout+fail.stderr, 'all comparison modes must be present'
 print('PASS: synthetic v3.12 PDF, actual A4 renderer, comparison visibility and omission gate')
