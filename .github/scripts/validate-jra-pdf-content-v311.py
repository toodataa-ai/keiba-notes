#!/usr/bin/env python3
"""v3.11 dynamic JRA report guard. No imposed PDF page limit; all records must be printed."""
import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
import fitz

BASE=Path(__file__).with_name('validate-jra-pdf-layout.py')
spec=importlib.util.spec_from_file_location('jra_v37_reader_gate', BASE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def validate_content(html_path,pdf_path,prediction_path):
    errors=mod.validate(html_path,pdf_path,'docs/data/jra_pdf_layout_policy_v1.json')
    html=Path(html_path).read_text(encoding='utf-8')
    data=json.loads(Path(prediction_path).read_text(encoding='utf-8'))
    if data.get('prompt_version')!='v3.11':errors.append('requires immutable v3.11 input')
    if data.get('stage')!='formal_prestart':errors.append('prediction not formally sealed')
    if 'data-tail-pagination="dynamic"' not in html:errors.append('unlimited v3.11 PDF pagination flag missing')
    sections=re.findall(r'<section class="page"><div class="chapter">(.*?)</div>(.*?)</section>',html,re.S)
    expected_count=len(data.get('step1_ranking',[]))+len(sections)
    if len(sections)<8:errors.append('five front pages plus one or more selected/rejected and audit pages are required')
    tail=sections[5:]
    selected=[(title,body) for title,body in tail if title.startswith('採用買い目｜')]
    excluded=[(title,body) for title,body in tail if title.startswith('不採用買い目｜')]
    audit=[(title,body) for title,body in tail if title.startswith('購入最適化監査｜')]
    if len(selected)<1 or len(excluded)<1 or len(audit)!=1 or tail!=selected+excluded+audit:
        errors.append('dynamic tail page sequence incorrect')
    for label,parts in [('selected',selected),('excluded',excluded)]:
        for i,(title,body) in enumerate(parts,1):
            if not title.endswith(f'{i}/{len(parts)}'):errors.append(label+' page serial missing')
            if 'この範囲に最終購入候補はありません' in body:errors.append('dummy purchase page prohibited')
    bs=data.get('purchase_portfolio_selection',{}).get('optimizer_audit',{}).get('balanced_selection')
    if not isinstance(bs,dict):errors.append('frozen joint-risk balancing audit missing')
    selected_records=data.get('final_bets',[])
    rejected_records=data.get('purchase_portfolio_selection',{}).get('optimizer_audit',{}).get('considered_excluded',[])
    if not isinstance(rejected_records,list):
        errors.append('excluded ticket registry missing');rejected_records=[]
    unknown=[x for x in data.get('ticket_candidate_comparisons',[]) if x.get('eligibility')=='unpriced']
    for bet in selected_records:
        ticket_id=bet.get('id')
        if not isinstance(ticket_id,str) or html.count('<td>'+ticket_id+'</td>')!=1:
            errors.append('final_bets missing/duplicated in HTML '+str(ticket_id))
    excluded_expected=['X'+str(i).zfill(4) for i in range(1,len(rejected_records)+1)]
    unknown_expected=['U'+str(i).zfill(4) for i in range(1,len(unknown)+1)]
    for ticket_id in excluded_expected+unknown_expected:
        if html.count('<td>'+ticket_id+'</td>')!=1:
            errors.append('excluded/unpriced candidate missing/duplicated in HTML '+ticket_id)
    if len(re.findall(r'<td>X\d{4}</td>',html))!=len(excluded_expected):
        errors.append('rejected candidates lost from HTML')
    if len(re.findall(r'<td>U\d{4}</td>',html))!=len(unknown_expected):
        errors.append('unpriced candidates lost from HTML')
    if not audit or '実損確率' not in audit[0][1] or '集合的中率' not in audit[0][1]:
        errors.append('risk comparison section missing real probability evidence')
    with fitz.open(str(pdf_path)) as doc:
        if len(doc)!=expected_count:
            errors.append(f'page overflow, underflow or lost items: actual={len(doc)} expected={expected_count}')
        actual=Counter()
        horse_count=len(data.get('step1_ranking',[]))
        tail_start=5+horse_count
        for i,page in enumerate(doc):
            pdftext=page.get_text()
            if i>=tail_start:
                for word in re.findall(r'(?<![A-Za-z0-9])(B\d{2,}|X\d{4}|U\d{4})(?![A-Za-z0-9])',pdftext):
                    actual[word]+=1
                if 'この範囲に最終購入候補はありません' in pdftext:
                    errors.append('repeated non-substantive purchase dummy page')
                if len(re.sub(r'\s','',pdftext))<210:errors.append(f'sparse tail PDF page {i+1}')
        for bet in selected_records:
            if actual[bet['id']]!=1:errors.append('missing/repeated PDF purchased line '+bet['id'])
        for ticket_id in excluded_expected+unknown_expected:
            if actual[ticket_id]!=1:errors.append('missing/repeated PDF rejected line '+ticket_id)
        stray=[k for k,v in actual.items() if v>1 and (k.startswith('X') or k.startswith('U'))]
        if stray:errors.append('repeated PDF rejected IDs '+','.join(stray[:10]))
    return errors

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--html',required=True)
    parser.add_argument('--pdf',required=True)
    parser.add_argument('--prediction',required=True)
    p=parser.parse_args()
    problems=validate_content(p.html,p.pdf,p.prediction)
    if problems:
        for problem in problems:print('PDF V311 BLOCKER:',problem)
        raise SystemExit(1)
    print('PASS: unlimited pagination, all final_bets, every excluded/unpriced candidate, colored horses, joint-risk table')
