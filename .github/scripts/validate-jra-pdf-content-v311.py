#!/usr/bin/env python3
"""Additional v3.11 content gate. Approved v3.7 CSS/grade/page checks remain mandatory."""
import argparse
import importlib.util
import json
import re
from pathlib import Path
import fitz

BASE=Path(__file__).with_name('validate-jra-pdf-layout.py')
spec=importlib.util.spec_from_file_location('jra_v37_reader_gate', BASE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
EXPECTED=('採用買い目','不採用買い目','購入最適化')

def validate_content(html_path,pdf_path,prediction_path):
    errors=mod.validate(html_path,pdf_path,'docs/data/jra_pdf_layout_policy_v1.json')
    html=Path(html_path).read_text(encoding='utf-8')
    data=json.loads(Path(prediction_path).read_text(encoding='utf-8'))
    if data.get('prompt_version')!='v3.11':errors.append('requires sealed v3.11 input')
    if data.get('stage')!='formal_prestart':errors.append('prediction not formally sealed')
    segments=re.findall(r'<section class="page"><div class="chapter">(.*?)</div>(.*?)</section>',html,re.S)
    if len(segments)!=8:
        errors.append('expected exactly five front and three authored tail sections')
    else:
        for i,(heading,body) in enumerate(segments[-3:]):
            if EXPECTED[i] not in heading:errors.append('tail section '+str(i+1)+' has wrong purpose')
            if 'この範囲に最終購入候補はありません' in body:errors.append('dummy empty purchase page')
            visible=re.sub('<[^>]+>',' ',body)
            if len(re.sub(r'\s','',visible))<200:errors.append('tail section '+str(i+1)+' contains too little meaningful text')
        if '不採用理由' not in segments[-2][1]:errors.append('missing rejected-ticket explanations')
        if '実損確率' not in segments[-1][1]:errors.append('missing portfolio risk comparison')
    bs=data.get('purchase_portfolio_selection',{}).get('optimizer_audit',{}).get('balanced_selection')
    if not isinstance(bs,dict):errors.append('missing frozen risk balancing audit')
    selected=data.get('final_bets',[])
    if len(selected)>18:errors.append('cannot fit all selected final_bets within approved tail pages')
    for line in selected:
        if not isinstance(line.get('id'),str) or html.count('<td>'+line['id']+'</td>')!=1:
            errors.append('missing or duplicated final_bets HTML row '+str(line.get('id')))
    with fitz.open(str(pdf_path)) as doc:
        if len(doc)>=3:
            text=[page.get_text() for page in doc[-3:]]
            for i,purpose in enumerate(EXPECTED):
                if purpose not in text[i]:errors.append('rendered tail page '+str(i+1)+' lacks '+purpose)
            for line in selected:
                if sum(page.count(line['id']) for page in text)!=1:
                    errors.append('purchased line missing/duplicated in rendered PDF '+line['id'])
            # A footer and a repeated disclaimer do not constitute an authored page.
            for i,page in enumerate(text):
                if len(re.sub(r'\s','',page))<260:errors.append('rendered v3.11 tail page '+str(i+1)+' sparse')
    return errors

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--html',required=True);p.add_argument('--pdf',required=True)
    p.add_argument('--prediction',required=True)
    a=p.parse_args()
    errors=validate_content(a.html,a.pdf,a.prediction)
    if errors:
        for e in errors:print('PDF V311 BLOCKER:',e)
        raise SystemExit(1)
    print('PASS v3.11 PDF: exact selected lines, exclusions, risk audit, stable A4/color/horse pages')
