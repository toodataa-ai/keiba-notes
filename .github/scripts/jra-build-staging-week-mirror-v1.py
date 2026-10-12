#!/usr/bin/env python3
"""Derive a 1:1 JRA this-week staging page from current production HTML.

Only intentional differences:
  (1) invisible asset path base and noindex;
  (2) staging home destination;
  (3) a tiny non-layout STAGING marker;
  (4) the reviewed race-specific preview target URL for only two 2026-10-12 races.
Never edit the production template, races.json, predictions or final_bets.
"""
from pathlib import Path
import re
import sys

PRODUCTION = Path("docs/this-week.html")
STAGING = Path("docs/staging/this-week.html")
START = "<head>"
HOME = 'href="index.html"'
OVERRIDE = r"""<script id="jra-staging-report-link-override">
(() => {
  const root=document.getElementById('weekPredictions');
  if(!root)return;
  const reviewOnly = {
    '2026-10-12-october-stakes':'tokyo11',
    '2026-10-12-swan-stakes':'kyoto11'
  };
  const update=()=>{
    for(const a of root.querySelectorAll('.race-card a[href]')){
      const href=a.getAttribute('href')||'';
      for(const [slug,short] of Object.entries(reviewOnly)){
        if(!href.includes(slug))continue;
        if(href.startsWith('reports/') && href.endsWith('.html'))
          a.setAttribute('href','staging/jra-v315-20261012/'+short+'.html');
        else if(href.startsWith('pdfs/') && href.endsWith('.pdf'))
          a.setAttribute('href','staging/jra-v315-20261012/'+short+'.pdf');
      }
    }
  };
  new MutationObserver(update).observe(root,{subtree:true,childList:true});
  update();
})();
</script>"""
MARKER_CSS = """<style id="jra-staging-nonlayout-marker">
.staging-visual-marker{position:fixed;right:6px;bottom:6px;z-index:2147483647;
  border-radius:4px;padding:3px 6px;font:700 9px "Meiryo UI",Meiryo,sans-serif;
  line-height:1.2;letter-spacing:.02em;color:#fff;background:rgba(110,69,33,.82);
  pointer-events:none}
</style>"""
MARKER = '<div class="staging-visual-marker" aria-label="ステージング版">STAGING</div>'

def render(production: str) -> str:
    assert production.count(START)==1 and production.count('</head>')==1
    assert production.count('<body>')==1 and production.count('</body>')==1
    assert production.count(HOME)==1, 'production home link changed; update stage mirror generator intentionally'
    assert 'id="weekPredictions"' in production and 'assets/week.js?' in production
    result = production.replace(START,START+'\n<meta name="robots" content="noindex,nofollow"><base href="../">\n',1)
    result = result.replace('</head>', MARKER_CSS+'\n</head>',1)
    result = result.replace(HOME, 'href="staging/index.html"',1)
    result = result.replace('<body>', '<body>\n'+MARKER,1)
    result = result.replace('</body>', OVERRIDE+'\n</body>',1)
    return result

def main():
    prod=PRODUCTION.read_text(encoding='utf8')
    expected=render(prod)
    assert expected.count('id="jra-staging-report-link-override"')==1
    assert expected.count('id="weekPredictions"')==1
    if '--check' in sys.argv[1:]:
        assert STAGING.read_text(encoding='utf8')==expected, 'JRA_STAGING_NOT_1_TO_1_PRODUCTION_TEMPLATE'
        print('PASS_JRA_THIS_WEEK_STAGE_EXACT_PRODUCTION_MIRROR_WITH_URL_ONLY_OVERLAY')
    else:
        STAGING.write_text(expected,encoding='utf8')
        print('PREPARED_JRA_THIS_WEEK_STAGE_EXACT_PRODUCTION_MIRROR',STAGING)
if __name__ == '__main__':
    main()
