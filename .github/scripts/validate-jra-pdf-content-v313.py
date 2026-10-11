#!/usr/bin/env python3
"""v3.13 PDF integrity: full original v3.12 page, color, ID, price and risk validator."""
import argparse,importlib.util,json,re,tempfile
from pathlib import Path
from collections import Counter
import fitz
THIS=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('jra_v312_complete_page_validator',THIS/'validate-jra-pdf-content-v312.py')
v312=importlib.util.module_from_spec(spec);spec.loader.exec_module(v312)

def validate_content(html_path,pdf_path,prediction_path):
    html=Path(html_path).read_text(encoding='utf8')
    payload=json.loads(Path(prediction_path).read_text(encoding='utf8'))
    errors=[]
    if payload.get('prompt_version')!='v3.13' or payload.get('stage')!='formal_prestart':
        errors.append('v3.13 approved sealed formal prediction required')
        return errors
    if 'data-purchase-audit="v3.13"' not in html:
        errors.append('missing v3.13 purchase audit marker')
        return errors
    if 'STEP2単勝金額最適化（v3.13）' not in html:
        errors.append('missing actual vs baseline stake comparison')
    if html.count('最終購入結論｜本日の正式予想')!=1:
        errors.append('v3.13 front-page purchase instructions missing')
    if payload.get('total_stake_yen')!=sum(x['stake_yen'] for x in payload.get('final_bets',[])):
        errors.append('total final yen not equal to ticket amounts')
    if payload.get('total_stake_yen',0)>6000:
        errors.append('budget beyond 6000 yen')
    # Preserve and execute the complete original full-page validator without
    # ever mutating user files; only the two temporary version strings differ.
    with tempfile.TemporaryDirectory(prefix='jra-v313-audit-') as tmp:
        temp=Path(tmp)
        adjusted_html=temp/'readback.html'
        adjusted_json=temp/'prediction.json'
        adjusted_html.write_text(html.replace('data-purchase-audit="v3.13"',
                                             'data-purchase-audit="v3.12"'),encoding='utf8')
        adjusted={**payload,'prompt_version':'v3.12'}
        adjusted_json.write_text(json.dumps(adjusted,ensure_ascii=False),encoding='utf8')
        errors.extend(v312.validate_content(adjusted_html,pdf_path,adjusted_json))
    # Every purchased amount must be in the row of its own unique final ID.
    for bet in payload.get('final_bets',[]):
        fragment=re.search(r'<tr><td>'+re.escape(bet['id'])+r'</td>(.*?)</tr>',html,re.S)
        if not fragment or f'<td>{bet["stake_yen"]}円</td>' not in fragment.group(0):
            errors.append('incorrect/missing exact final amount '+bet['id'])
    # The PDF must retain one horse per page and show active v3.13 stake/audit labels.
    with fitz.open(pdf_path) as pdf:
        text='\n'.join(p.get_text() for p in pdf[:min(6,len(pdf))])
        if 'v3.13' not in text or '単勝金額最適化' not in text:
            errors.append('v3.13 stake guidance lost in PDF')
    return errors
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for label in ('html','pdf','prediction'):parser.add_argument('--'+label,required=True)
    args=parser.parse_args()
    errors=validate_content(args.html,args.pdf,args.prediction)
    if errors:
        for e in errors:print('JRA_V313_PDF_BLOCKER:',e)
        raise SystemExit(1)
    print('PASS JRA V313 full page colors, buy-id amounts, one horse/page, baseline and net-loss audit')
