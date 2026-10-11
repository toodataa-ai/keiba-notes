#!/usr/bin/env python3
"""v3.13 reader: exact historical v3.12 HTML/PDF layout and immutable CSS.
Only stamp official version, proofed WIN stake risk, and accurate final purchase metrics.
"""
import copy,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE=HERE/'jra-render-live-v312.py'
spec=importlib.util.spec_from_file_location('immutable_jra_v312_renderer',SOURCE)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

def make(report):
    if report.get('prompt_version')!='v3.13' or report.get('stage')!='formal_prestart':
        raise ValueError('v313 BLOCKER: requires sealed formal v3.13 prediction')
    if report.get('total_stake_yen',0)>6000:
        raise ValueError('v313 BLOCKER: max 6000 yen exceeded')
    state=copy.deepcopy(report)
    state['prompt_version']='v3.12'  # compatibility only within locked renderer
    m=state['purchase_portfolio_selection']
    for row in state['purchase_set_comparisons_v312']['comparison_sets']:
        if row.get('kind')=='final_balanced':
            # UI row now describes THE CURRENT adjusted total, never frozen baseline.
            row['stake_yen']=report['total_stake_yen']
            row['tickets']=len(report['final_bets'])
            row['profit_yen']=(m.get('expected_net_profit_yen_scenarios') or {}).get('central')
            hit=(m.get('hit_probability_scenarios') or {}).get('central')
            row['hit_pct']=hit*100 if hit is not None else None
            row['label']='最終採用セット（v3.13 単勝金額調整後）'
    html=old.make(state)
    html=html.replace('v3.12','v3.13')
    html=html.replace('各馬券100円、','各馬券100円単位、単勝は期待利益・実損確率の条件を満たす場合に100円刻みで増額、')
    audit=report['win_stake_allocation_v313']
    st=report['v312_balanced_baseline']['total_stake_yen']
    original=audit.get('baseline') or {}
    now=audit.get('selected') or {}
    b=original.get('central') or {}
    a=now.get('central') or {}
    esc=old.h
    def pct(n):return '対象外' if n is None else f'{100*n:.2f}%'
    def yen(n):return '対象外' if n is None else f'{n:,.1f}円'
    note=('<p>STEP2単勝金額最適化（v3.13）：'
          +('条件を満たしたため単勝の一部を増額' if audit['activated'] else '期待利益・損失制約を満たさず原則100円を維持')
          +f'。基準 {st:,}円 → 最終 {report["total_stake_yen"]:,}円。'
          +f'投資総額を回収できる推定確率 {pct(b.get("nonloss_probability"))}'
          +f' → {pct(a.get("nonloss_probability"))}。'
          +f'中央期待純利益 {yen(b.get("expected_net_profit_yen"))}'
          +f' → {yen(a.get("expected_net_profit_yen"))}。'
          +'旧購入セットは比較用基準として保存し、発走前の全組番・価格証跡と印を保持。'
          +'モデルは未校正であり、利益を保証しません。</p>')
    # This text sits in the STEP2 purchase overview, not on a horse page,
    # and is included before dynamic tail chapters/one-page-per-horse logic.
    anchor='<div class="chapter">購入ポートフォリオ｜概要</div>'
    if html.count(anchor)!=1:raise ValueError('v313 BLOCKER: no unique portfolio overview')
    html=html.replace(anchor,anchor+note,1)
    assert 'data-purchase-audit="v3.13"' in html
    return html
if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: jra-render-live-v313.py prediction.json report.html')
    payload=json.loads(Path(sys.argv[1]).read_text())
    output=Path(sys.argv[2]);output.parent.mkdir(parents=True,exist_ok=True)
    result=make(payload)
    output.write_text(result,encoding='utf8')
    print('AUTHORED_HTML_V313',output,len(result),'horses',len(payload['step1_ranking']))
