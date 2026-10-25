#!/usr/bin/env python3
"""Produce separately named, display-only corrected HTML copies in a staging folder.
Never touch canonical predictions, reports, PDFs, registry or proof commits.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from jra_clock_v1 import recover

ROOT=Path(__file__).resolve().parents[2]
TARGETS={'2026-10-17-hokuriku-stakes':5,'2026-10-25-lumiere-autumn-dash':25}
SECTIONS=re.compile(r'(<section class="horse">)(.*?)(</section>)',re.S)
ROW=re.compile(r'(<tr><td>(\d{4}-\d{2}-\d{2})</td><td>([^<]+)</td><td>(\d{3,4}(?:芝|ダート))</td><td>[^<]*</td><td>([^<]+)</td><td>)(\?)(</td><td>[^<]*</td></tr>)')

def render_one(race,original,output):
    before=original.read_bytes()
    html=before.decode('utf-8')
    src=json.loads((ROOT/'e2e_validation/inputs/v313'/(race+'.json')).read_text(encoding='utf8'))
    mappings={}
    for horse in src['step1']['runners']:
        slots={}
        for p in horse.get('past_performances',[]):
            fixed=recover(p)
            if p.get('time') or not fixed.get('time'):continue
            k=(p['date'],p['course'],str(p['distance_m'])+p['surface'],str(p['finish'])+'着')
            if k in slots:raise ValueError('non-unique historical clock '+str(k))
            slots[k]=fixed['time']
        mappings[horse['horse_name']]=slots
    applied=[]
    def section_replace(m):
        section=m[2]
        head=re.search(r'<h1>([◎○▲△×])\s+\d+\s+([^<]+)</h1>',section)
        if not head:return m[0]
        horse=head[2]
        def row_replace(row):
            k=(row[2],row[3],row[4],row[5])
            time=mappings.get(horse,{}).get(k)
            if time is None:return row[0]
            applied.append({'horse':horse,'date':row[2],'venue':row[3],'course':row[4],'clock':time})
            return row[1]+time+row[7]
        return m[1]+ROW.sub(row_replace,section)+m[3]
    html=SECTIONS.sub(section_replace,html)
    if len(applied)!=TARGETS[race]:
        raise RuntimeError('clock row count mismatch '+race+' actual='+str(len(applied)))
    if html.count('<td>?</td>')!=before.decode('utf8').count('<td>?</td>')-len(applied):
        raise RuntimeError('unexpected unrelated row edit')
    html=html.replace('本日の正式予想｜表紙','本日の正式予想｜表紙（時計補完・閲覧版）',1)
    html=html.replace('<body ','<body data-clock-only-correction="v1" ',1)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(html,encoding='utf8')
    if original.read_bytes()!=before:raise RuntimeError('original report unexpectedly mutated')
    return {'race_id':race,'archived_original':str(original.relative_to(ROOT)),
            'archived_original_sha256':hashlib.sha256(before).hexdigest(),
            'stage_html':str(output),'stage_html_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'clock_changes':applied,'clock_change_count':len(applied),
            'immutable_formal_ratings_and_bets':True}

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--output',required=True)
    args=cli.parse_args()
    output=Path(args.output)
    registry=json.loads((ROOT/'docs/data/races.json').read_text(encoding='utf8'))
    report_map={x['id']:x['report'] for x in registry['races']}
    manifests=[]
    for race in TARGETS:
        src=ROOT/'docs'/report_map[race]
        target=output/(src.stem+'-clockview-v1.html')
        manifests.append(render_one(race,src,target))
    (output/'clockview-stage-manifest.json').write_text(
        json.dumps({'mode':'staging_display_only','canonical_modified':False,
                    'reports':manifests},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS_STAGE_CLOCK_VIEW',*[r['clock_change_count'] for r in manifests])
if __name__=='__main__':main()
