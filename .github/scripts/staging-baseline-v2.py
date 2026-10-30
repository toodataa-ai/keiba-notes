#!/usr/bin/env python3
"""JRA staging = exact current production UI plus only STAGING shell and safe local links.

READS production docs/*.html. WRITES ONLY docs/staging/<canonical>.html.
It never touches prediction data, reports, PDFs, buys, proofs, or LAB sources.
"""
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
PROD=ROOT/"docs"
STAGE=PROD/"staging"
PAGES=("index.html","this-week.html","schedule.html","results.html","methodology.html",
       "roadmap.html","e2e.html","baba-models.html","local-racing-shadow.html",
       "experience-regime.html","release-history.html")
MARKER='<div class="staging-shell-marker" role="status" aria-label="ステージング版">STAGING <span>検証中</span></div>'

def render(prod):
    assert prod.count('<html lang="ja">')==1
    assert prod.count('<head>')==1 and prod.count('</head>')==1
    assert len(re.findall(r'<body(?:\s+[^>]*)?>',prod))==1 and prod.count('</body>')==1
    assert 'data-stage="preview"' not in prod and 'noindex' not in prod
    out=prod.replace('<html lang="ja">','<html lang="ja" data-stage="preview">',1)
    out=out.replace('<head>','<head>\n<meta name="robots" content="noindex,nofollow"><base href="../">',1)
    out=out.replace('</head>','<link rel="stylesheet" href="staging/stage-indicator.css?v=20261012-1">\n</head>',1)
    out=re.sub(r'(<body(?:\s+[^>]*)?>)',lambda m:m.group(1)+'\n'+MARKER,out,count=1)
    def fix(match):
        quote,url=match.group(1),match.group(2)
        base,sep,tail=url.partition('?')
        hashsep=base.find('#')
        if hashsep>=0:
            plain,hashpart=base[:hashsep],base[hashsep:]
        else: plain,hashpart=base,''
        if plain in PAGES: return 'href='+quote+'staging/'+plain+hashpart+(sep+tail if sep else '')+quote
        return match.group(0)
    out=re.sub(r'href=(["\x27])([^"\x27]+)\1',fix,out)
    # Stage-only cache key for the common week script: publication wording
    # may differ by staging policy, while production HTML stays unchanged.
    if 'id="weekSchedule"' in out:
        out,count=re.subn(r'(<script src="assets/week\\.js\\?v=[^"]+)("></script>)',
                          lambda m:m.group(1)+'-stage-morning-preview1'+m.group(2),out,count=1)
        assert count==1,'Missing unique week.js tag for preview'
    assert out.count('staging-shell-marker" role="status"')==1
    assert 'data-stage="preview"' in out and 'noindex,nofollow' in out
    return out

def sync(*,check=False,only=None):
    names=[only] if only else PAGES
    for name in names:
        assert name in PAGES,name
        path=PROD/name
        stage=STAGE/name
        expected=render(path.read_text(encoding='utf-8'))
        if check:
            assert stage.read_text(encoding='utf-8')==expected, 'STAGING_PRODUCTION_BASELINE_DRIFT:'+name
        else:
            stage.write_text(expected,encoding='utf-8')
        print(('PASS_' if check else 'WRITE_')+'STAGE_EXACT_PRODUCTION_UI',name)
    return True

if __name__=='__main__':
    mode='--check' in sys.argv
    only=next((arg.split('=',1)[1] for arg in sys.argv[1:] if arg.startswith('--only=')),None)
    sync(check=mode,only=only)
