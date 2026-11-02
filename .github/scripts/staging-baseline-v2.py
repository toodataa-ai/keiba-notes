#!/usr/bin/env python3
"""JRA staging = current production UI + pending UI candidates, with STAGING shell and staging links.

READS production docs/*.html and candidate sources listed in .github/staging-candidates.json
(kept in PRODUCTION form under .github/staging-candidates/<docs path>).
WRITES ONLY docs/staging/<canonical>.html and docs/staging/candidate-assets/.
It never touches prediction data, reports, PDFs, buys, proofs, or LAB sources.
A page with no candidate is exactly render(production); a candidate page is render(candidate).
After approval, jra-ui-promote-v1.yml copies candidate sources byte-for-byte into docs/.
"""
from pathlib import Path
import json
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
PROD=ROOT/"docs"
STAGE=PROD/"staging"
PAGES=("index.html","this-week.html","schedule.html","results.html","methodology.html",
       "roadmap.html","e2e.html","baba-models.html","local-racing-shadow.html",
       "experience-regime.html","release-history.html","improvement-cycle.html")
CANDIDATES=ROOT/".github"/"staging-candidates.json"
CANDIDATE_SRC=ROOT/".github"/"staging-candidates"
CANDIDATE_ASSETS=STAGE/"candidate-assets"
MARKER='<div class="staging-shell-marker" role="status" aria-label="ステージング版">STAGING <span>検証中</span></div>'
CANDIDATE_MARKER='<div class="staging-shell-marker" role="status" aria-label="ステージング版・承認待ちの変更案">STAGING <span>変更案・承認待ち</span></div>'

def candidates():
    """{page: entry} for pending candidates. Each page may belong to one candidate only."""
    if not CANDIDATES.exists():
        return {}
    data=json.loads(CANDIDATES.read_text(encoding='utf-8'))
    out={}
    for c in data.get('candidates',[]):
        for page in c.get('pages',[]):
            assert page in PAGES,('candidate page must be a canonical staging page',page)
            assert page not in out,('page in two candidates',page)
            assert (CANDIDATE_SRC/page).is_file(),('missing candidate source',page)
            out[page]=c
        for asset in c.get('assets',[]):
            assert asset.startswith('assets/') and '..' not in asset,asset
            assert (CANDIDATE_SRC/asset).is_file(),('missing candidate asset',asset)
    return out

def candidate_assets():
    return sorted({a for c in candidates().values() for a in c.get('assets',[])})

def render(prod,*,candidate=False,assets=(),page=None):
    assert prod.count('<html lang="ja">')==1
    assert prod.count('<head>')==1 and prod.count('</head>')==1
    assert len(re.findall(r'<body(?:\s+[^>]*)?>',prod))==1 and prod.count('</body>')==1
    assert 'data-stage="preview"' not in prod and 'noindex' not in prod
    out=prod.replace('<html lang="ja">','<html lang="ja" data-stage="preview">',1)
    out=out.replace('<head>','<head>\n<meta name="robots" content="noindex,nofollow"><base href="../">',1)
    out=out.replace('</head>','<link rel="stylesheet" href="staging/stage-indicator.css?v=20261012-1">\n</head>',1)
    marker=CANDIDATE_MARKER if candidate else MARKER
    out=re.sub(r'(<body(?:\s+[^>]*)?>)',lambda m:m.group(1)+'\n'+marker,out,count=1)
    # Candidate-only assets are served from docs/staging/candidate-assets/ until approval.
    for asset in assets:
        target='staging/candidate-assets/'+asset[len('assets/'):]
        out=re.sub(r'((?:href|src)=["\x27])'+re.escape(asset)+r'(?=[?"\x27#])',lambda m:m.group(1)+target,out)
    def fix(match):
        quote,url=match.group(1),match.group(2)
        base,sep,tail=url.partition('?')
        hashsep=base.find('#')
        if hashsep>=0:
            plain,hashpart=base[:hashsep],base[hashsep:]
        else: plain,hashpart=base,''
        # <base href="../"> would send same-page anchors (#x) to docs/; keep them on this staging page.
        if plain=='' and len(hashpart)>1 and page: return 'href='+quote+'staging/'+page+hashpart+quote
        if plain in PAGES: return 'href='+quote+'staging/'+plain+hashpart+(sep+tail if sep else '')+quote
        return match.group(0)
    out=re.sub(r'href=(["\x27])([^"\x27]+)\1',fix,out)
    # Production has the approved visitor widget now. Replace it with the
    # stage's existing READ-ONLY preview instead of rendering duplicate counts.
    if 'id="siteUsageToday"' in out:
        n=out.count('<section class="site-usage"')
        assert n==1, 'Expected exactly one production usage widget'
        out,count=re.subn(r'<section class="site-usage"[^>]*>.*?</section>\n?', '',out,count=1,flags=re.S)
        assert count==1, 'Unable to isolate production usage widget from stage'
        out=out.replace('<link rel="stylesheet" href="assets/usage-summary.css?v=20261031-1">\n','',1)
        out=out.replace('<script src="assets/usage-summary.js?v=20261031-1" defer></script>\n','',1)
        assert 'id="siteUsageToday"' not in out, 'Production counter leaked into stage'
    # Approved LAB -> STAGING promotion: keep the production top-page
    # template unchanged and add only stage analytics teaser + dedicated assets.
    # This must remain in the canonical renderer or the mirror overwrites it.
    if 'id="mainTitle"' in out and '<p class="photo-credit">' in out:
        preview=(
            '<section class="stage-usage" aria-labelledby="stageUsageTitle">'
            '<div class="stage-usage-top"><strong id="stageUsageTitle" class="stage-usage-title">閲覧数</strong>'
            '<div class="stage-usage-values">'
            '<span class="stage-usage-value">今日 <b id="stageUsageToday" aria-live="polite">—</b></span>'
            '<span class="stage-usage-value">累計 <b id="stageUsageTotal" aria-live="polite">—</b></span>'
            '<a href="staging/usage-analytics.html">推移を見る</a>'
            '</div></div><p class="stage-usage-notice" id="stageUsageNote" role="status">'
            '</p></section>\n'
        )
        assert out.count('<p class="photo-credit">')==1
        out=out.replace('<p class="photo-credit">',preview+'<p class="photo-credit">',1)
        out=out.replace('</head>',
            '<link rel="stylesheet" href="staging/usage-summary.css?v=20261030-1">\n</head>',1)
        out=out.replace('</body>',
            '<script src="staging/usage-summary.js?v=20261030-1" defer></script>\n</body>',1)
        assert out.count('id="stageUsageToday"')==1 and out.count('id="stageUsageTotal"')==1
    # Stage-only cache key for the common week script: publication wording
    # may differ by staging policy, while production HTML stays unchanged.
    if 'id="weekSchedule"' in out:
        out,count=re.subn(r'(<script src="assets/week\.js\?v=[^"]+)("></script>)',
                          lambda m:m.group(1)+'-stage-morning-preview1'+m.group(2),out,count=1)
        assert count==1,'Missing unique week.js tag for preview'
    assert out.count('staging-shell-marker" role="status"')==1
    assert 'data-stage="preview"' in out and 'noindex,nofollow' in out
    return out

def expected(name):
    """Exact staging HTML for a canonical page (candidate source if one is pending)."""
    cand=candidates()
    if name in cand:
        return render((CANDIDATE_SRC/name).read_text(encoding='utf-8'),candidate=True,assets=candidate_assets(),page=name)
    return render((PROD/name).read_text(encoding='utf-8'),page=name)

def sync(*,check=False,only=None):
    names=[only] if only else PAGES
    cand=candidates()
    for name in names:
        assert name in PAGES,name
        stage=STAGE/name
        want=expected(name)
        if check:
            assert stage.read_text(encoding='utf-8')==want, 'STAGING_PRODUCTION_BASELINE_DRIFT:'+name
        else:
            stage.write_text(want,encoding='utf-8')
        print(('PASS_' if check else 'WRITE_')+('STAGE_CANDIDATE_UI ' if name in cand else 'STAGE_EXACT_PRODUCTION_UI ')+name)
    if only:
        return True
    wanted={a[len('assets/'):]:CANDIDATE_SRC/a for a in candidate_assets()}
    present={p.relative_to(CANDIDATE_ASSETS).as_posix() for p in CANDIDATE_ASSETS.rglob('*') if p.is_file()} if CANDIDATE_ASSETS.exists() else set()
    if check:
        assert present==set(wanted),('STAGING_CANDIDATE_ASSET_SET_DRIFT',sorted(present),sorted(wanted))
        for rel,src in wanted.items():
            assert (CANDIDATE_ASSETS/rel).read_bytes()==src.read_bytes(),'STAGING_CANDIDATE_ASSET_DRIFT:'+rel
    else:
        for rel in present-set(wanted):
            (CANDIDATE_ASSETS/rel).unlink()
        for rel,src in wanted.items():
            (CANDIDATE_ASSETS/rel).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,CANDIDATE_ASSETS/rel)
        if CANDIDATE_ASSETS.exists() and not any(CANDIDATE_ASSETS.rglob('*')):
            CANDIDATE_ASSETS.rmdir()
    return True

if __name__=='__main__':
    mode='--check' in sys.argv
    only=next((arg.split('=',1)[1] for arg in sys.argv[1:] if arg.startswith('--only=')),None)
    sync(check=mode,only=only)
