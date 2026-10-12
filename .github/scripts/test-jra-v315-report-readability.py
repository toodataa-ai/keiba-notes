#!/usr/bin/env python3
"""Regression: replay both 2026-10-12 immutable JRA sources in memory; never publish or revise."""
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from weasyprint import HTML
import fitz

ROOT=Path('.')
sys.path.insert(0,str(ROOT/'.github/scripts'))
spec=importlib.util.spec_from_file_location('jra_v315_report',ROOT/'.github/scripts/jra-render-formal-3action-v315.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
races=json.loads((ROOT/'docs/data/races.json').read_text())['races']
for rid in ('2026-10-12-october-stakes','2026-10-12-swan-stakes'):
    registry=next(x for x in races if x['id']==rid)
    assert registry['purchase_strategy_version']=='v3.15'
    plan=json.loads((ROOT/registry['e2e_prediction']).read_text())
    sourcepath=ROOT/plan['source_prediction_path']
    raw=sourcepath.read_bytes()
    source=json.loads(raw)
    assert plan['source_prediction_sha256']==hashlib.sha256(raw).hexdigest()
    assert source['step1_ranking']
    htmltext,count=mod.html_report(plan,source)
    assert count==1+len(source['step1_ranking'])
    assert count==1+registry['field_size']
    assert htmltext.count('class="page horse-page"')==registry['field_size']
    for internal in ('<strong>overall_grade</strong>','<strong>factor_grades</strong>',
                     '<strong>past_performances</strong>','<strong>source_url</strong>'):
        assert internal not in htmltext,(rid,internal)
    for x in source['step1_ranking']:
        assert x['horse_name'] in htmltext
    pdf=HTML(string=htmltext,base_url=str(ROOT.resolve())).write_pdf()
    preview_dir=os.environ.get('JRA_V315_PREVIEW_DIR')
    if preview_dir:
        dest=Path(preview_dir)
        dest.mkdir(parents=True,exist_ok=True)
        (dest/(rid+'-readable-v315.html')).write_text(htmltext,encoding='utf8')
        (dest/(rid+'-readable-v315.pdf')).write_bytes(pdf)
    with fitz.open(stream=pdf,filetype='pdf') as pages:
        assert len(pages)==count,(rid,len(pages),count)
        for i,page in enumerate(pages):
            content=page.get_text()
            assert len(content)>100
            if i>0:
                for section in ('①〜⑨ 評価内訳','判断根拠','近走成績','モデル単勝確率'):
                    assert section in content,(rid,i,section)
                for internal in ('overall_grade','factor_grades','past_performances','source_url'):
                    assert internal not in content,(rid,i,internal)
            for b in page.get_text('dict')['blocks']:
                for line in b.get('lines',[]):
                    for span in line['spans']:
                        x0,y0,x1,y1=span['bbox']
                        assert x0>=-1 and y0>=-1 and x1<=page.rect.width+1 and y1<=page.rect.height+1,(rid,i,span['text'])
    assert hashlib.sha256(sourcepath.read_bytes()).digest()==hashlib.sha256(raw).digest()
    print('PASS_JRA_V315_READABLE_A4_19_PAGE_REAL_SOURCE',rid,count)
