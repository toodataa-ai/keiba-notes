#!/usr/bin/env python3
"""Family-events-matched staging badge + noindex injected in temporary Pages output.
Production source HTML/CSS/JS are never edited by this script."""
from pathlib import Path
import argparse,re
META='<meta name="robots" content="noindex,nofollow">'
STYLE='''<style id="staging-visual-marker">
html::after{content:"";position:fixed;inset:0;border:2px solid rgba(138,75,8,.8);pointer-events:none;z-index:2147483646}
.staging-visual-marker{position:fixed;right:6px;bottom:6px;display:flex;align-items:center;gap:5px;background:rgba(138,75,8,.92);color:#fff7ed;border-radius:999px;padding:4px 7px;font-family:"Meiryo UI",Meiryo,sans-serif;font-size:9px;font-weight:800;line-height:1;letter-spacing:.02em;z-index:2147483647;box-shadow:0 1px 3px rgba(0,0,0,.18);pointer-events:none}
.staging-visual-marker small{font-size:8px;font-weight:700;opacity:.9}
</style>'''
def stage(path,sha):
 p=Path(path)
 source=p.read_text(encoding='utf8')
 if META in source or 'id="staging-visual-marker"' in source:raise ValueError('staging generated file already marked: '+str(p))
 if '<head>' in source:
  source=source.replace('<head>','<head>\n'+META,1)
 elif '<head ' in source:
  source=re.sub(r'<head\s[^>]*>',lambda m:m.group(0)+'\n'+META,source,count=1)
 else:raise ValueError('HTML head not found: '+str(p))
 if '</head>' not in source:raise ValueError('Missing head closure: '+str(p))
 source=source.replace('</head>',STYLE+'\n</head>',1)
 m=re.search(r'<body(?:\s[^>]*)?>',source,re.I)
 if not m:raise ValueError('Missing body opening: '+str(p))
 badge=f'<div class="staging-visual-marker" role="status">STAGING <small>{sha}</small></div>'
 source=source[:m.end()]+'\n'+badge+source[m.end():]
 p.write_text(source,encoding='utf8')
 return source
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--sha',required=True);a.add_argument('--dir',default='docs/staging')
 args=a.parse_args()
 if not re.fullmatch(r'[0-9a-f]{7,40}',args.sha):raise SystemExit('BLOCKER: invalid staging commit')
 folder=Path(args.dir)
 if folder.as_posix()!='docs/staging':raise SystemExit('BLOCKER: refuse non-staging directory')
 expected=['index.html','this-week.html','purchase-preview.html','release-history.html']
 for name in expected:
  p=folder/name
  if not p.is_file():raise SystemExit('BLOCKER: missing stage page '+name)
  content=stage(p,args.sha[:7])
  assert content.count(META)==1 and content.count('class="staging-visual-marker"')==1
 print('PASS_FAMILY_STAGE_NO_INDEX_VISUAL_BADGE',len(expected),args.sha[:7])

