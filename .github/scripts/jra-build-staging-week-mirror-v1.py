#!/usr/bin/env python3
"""Maintain the exact production JRA week layout on staging, adding only:
  - a common always-visible staging marker and four-pixel horizontal stripe,
  - preview-only in-page diagnosis on selected report links,
  - safe staging-home navigation and noindex.
The public data, final_bets, CSS, and report renderer are not modified.
"""
from pathlib import Path
import sys
PROD=Path("docs/this-week.html")
STAGE=Path("docs/staging/this-week.html")
STAGE_MARKER='<div class="staging-shell-marker" role="status" aria-label="ステージング版">STAGING <span>検証中</span></div>'
STAGE_STYLES='''<link rel="stylesheet" href="staging/stage-indicator.css?v=20261012-1">
<link rel="stylesheet" href="staging/stage-week-preview.css?v=20261012-1">'''
STAGE_SCRIPT='<script src="staging/stage-week-preview.js?v=20261012-1"></script>'
def render(prod):
    assert prod.count('<html lang="ja">')==1
    assert prod.count('<head>')==1 and prod.count('</head>')==1
    assert prod.count('</body>')==1 and prod.count('<body>')==1
    assert prod.count('href="index.html"')==1
    assert 'id="weekPredictions"' in prod and 'assets/week.js?' in prod
    h=prod.replace('<html lang="ja">','<html lang="ja" data-stage="preview">',1)
    h=h.replace('<head>','<head>\n<meta name="robots" content="noindex,nofollow"><base href="../">',1)
    h=h.replace('</head>',STAGE_STYLES+'\n</head>',1)
    h=h.replace('<body>','<body>\n'+STAGE_MARKER,1)
    h=h.replace('href="index.html"','href="staging/index.html"',1)
    h=h.replace('</body>',STAGE_SCRIPT+'\n</body>',1)
    return h
def main():
    prod=PROD.read_text(encoding='utf8')
    expected=render(prod)
    assert expected.count('class="staging-shell-marker"')==1
    assert expected.count('stage-week-preview.js')==1
    assert expected.count('id="weekPredictions"')==1
    if '--check' in sys.argv[1:]:
        assert STAGE.read_text(encoding='utf8')==expected,'JRA_WEEK_STAGING_NOT_PRODUCTION_MIRROR'
        print('PASS_JRA_WEEK_STAGING_EXACT_PRODUCTION_MIRROR_WITH_INPAGE_PREVIEW')
    else:
        STAGE.write_text(expected,encoding='utf8')
        print('WRITE_JRA_STAGE_MIRROR',STAGE)
if __name__=='__main__':main()
