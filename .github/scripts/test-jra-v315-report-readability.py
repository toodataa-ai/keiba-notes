#!/usr/bin/env python3
"""Regression: replay both 2026-10-12 immutable JRA sources in memory; never publish or revise."""
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from weasyprint import HTML
import fitz

ROOT=Path('.')
sys.path.insert(0,str(ROOT/'.github/scripts'))
spec=importlib.util.spec_from_file_location('jra_v315_report',ROOT/'.github/scripts/jra-render-formal-3action-v315.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
# Snapshot of the approved v3.13 grade palette, not a newly invented palette.
legacy=(ROOT/'docs/reports/2026-10-12-october-stakes-v3.13-rerun38185599767-attempt2-v313.html').read_text()
legacy_classes={'A+':'gAp','A':'gA','B+':'gBp','B':'gB','B-':'gBm','C':'gC'}
new_classes={'A+':'g-Aplus','A':'g-A','B+':'g-Bplus','B':'g-B','B-':'g-Bminus','C':'g-C'}
palette={}
for grade,klass in legacy_classes.items():
    m=re.search(r'\.'+klass+r'\{background:(#[0-9a-fA-F]{6});color:(#[0-9a-fA-F]{6})\}',legacy)
    assert m is not None,('approved v3.13 grade source not found',grade)
    palette[grade]=(m.group(1).lower(),m.group(2).lower())
assert list(palette)==['A+','A','B+','B','B-','C']
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
    # Stable visual sorting: mark priority, then the original sealed source order.
    expected=mod.order_horses_by_mark(source['step1_ranking'])
    expected_marks=[x['mark'] for x in expected]
    assert expected_marks==sorted(expected_marks,key=mod.order_horses_by_mark.__globals__['MARK_ORDER'].__getitem__)
    assert sorted(x['horse_number'] for x in expected)==sorted(x['horse_number'] for x in source['step1_ranking'])
    assert expected is not source['step1_ranking']
    for mark in ('◎','○','▲','△','×'):
        assert [x['horse_number'] for x in expected if x['mark']==mark]==[
            x['horse_number'] for x in source['step1_ranking'] if x['mark']==mark], (rid,mark,'unstable within same mark')
    htmltext,count=mod.html_report(plan,source)
    actual_headings=re.findall(r'<section class="page horse-page">.*?<h1>(.*?)</h1>',htmltext,re.S)
    assert len(actual_headings)==len(expected)
    for i,(heading,x) in enumerate(zip(actual_headings,expected)):
        assert heading==f"{x['horse_number']}番　{x['horse_name']}　{x['mark']}",(rid,i,heading)

    assert count==1+len(source['step1_ranking'])
    assert count==1+registry['field_size']
    assert htmltext.count('class="page horse-page"')==registry['field_size']
    # Grade colors must match the original approved HTML byte-for-byte.
    for grade,(bg,fg) in palette.items():
        match=re.search(r'\.horse-page \.'+new_classes[grade]+r'\{([^}]*)\}',htmltext)
        assert match is not None,(rid,grade,'grade CSS rule missing')
        assert 'background:'+bg in match.group(1),(rid,grade,'background color regression')
        assert 'color:'+fg in match.group(1),(rid,grade,'foreground color regression')
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
                x=expected[i-1]
                header=f"{x['horse_number']}番　{x['horse_name']}　{x['mark']}"
                assert header in content,(rid,i,'PDF page horse order mismatch',header)
                for section in ('①〜⑨ 評価内訳','判断根拠','近走成績','モデル単勝確率'):
                    assert section in content,(rid,i,section)
                for internal in ('overall_grade','factor_grades','past_performances','source_url'):
                    assert internal not in content,(rid,i,internal)
            if i>0:
                # Verify not just CSS: grade foreground and background survive into the real PDF.
                grades=set(expected[i-1]['factor_grades']) | {expected[i-1]['overall_grade']}
                spans=[(span['text'].strip(),span['color'])
                       for b in page.get_text('dict')['blocks']
                       for line in b.get('lines',[]) for span in line['spans']]
                fills=[d['fill'] for d in page.get_drawings() if d.get('fill') is not None]
                for grade in grades:
                    bg,fg=palette[grade]
                    expected_fg=int(fg[1:],16)
                    expected_bg=tuple(int(bg[k:k+2],16)/255 for k in (1,3,5))
                    assert (grade,expected_fg) in spans,(rid,i,grade,'PDF foreground regression')
                    assert any(len(fill)>=3 and max(abs(fill[k]-expected_bg[k]) for k in range(3))<0.013 for fill in fills),(
                        rid,i,grade,'PDF background regression')
            for b in page.get_text('dict')['blocks']:
                for line in b.get('lines',[]):
                    for span in line['spans']:
                        x0,y0,x1,y1=span['bbox']
                        assert x0>=-1 and y0>=-1 and x1<=page.rect.width+1 and y1<=page.rect.height+1,(rid,i,span['text'])
    assert hashlib.sha256(sourcepath.read_bytes()).digest()==hashlib.sha256(raw).digest()
    print('PASS_JRA_V315_READABLE_A4_19_PAGE_REAL_SOURCE',rid,count)
