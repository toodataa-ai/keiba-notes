#!/usr/bin/env python3
"""Offline release/rollback rehearsal using a temporary Git history, no production write."""
import json,subprocess,sys,tempfile
from pathlib import Path
TOOL=Path(__file__).with_name('jra-site-ui-release-v1.py').resolve()
def run(cwd,*args):
 return subprocess.check_output(args,cwd=cwd,text=True).strip()
def write(root,p,s):
 dest=root/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(s,encoding='utf8')
def main():
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);run(root,'git','init','-q');run(root,'git','checkout','-qb','main')
  run(root,'git','config','user.name','CI Site Auditor')
  run(root,'git','config','user.email','ci@example.org')
  write(root,'docs/index.html','<html>special-2026-10-11-tokyo12.html</html>')
  write(root,'docs/this-week.html','<html>special-2026-10-11-tokyo12.html</html>')
  write(root,'docs/data/races.json','{"immutable_original":true}\n')
  run(root,'git','add','.');run(root,'git','commit','-qm','original v1.00')
  base=run(root,'git','rev-parse','HEAD')
  run(root,'git','branch','staging/jra-ui-v101-three-plus-ana')
  run(root,'git','checkout','-q','staging/jra-ui-v101-three-plus-ana')
  write(root,'docs/index.html','<html>正式版 v1.00 ／ ステージング v1.01（未公開） href="staging/release-history.html"</html>')
  write(root,'docs/this-week.html','<html>staging/purchase-preview.html</html>')
  run(root,'git','commit','-qam','v1.01 staged')
  staged=run(root,'git','rev-parse','HEAD')
  run(root,'git','checkout','-q','main')
  run(root,'git','update-ref','refs/remotes/origin/staging/jra-ui-v101-three-plus-ana',staged)
  run(root,'git','tag','-a','jra-site-v1.00','-m','baseline')
  request='docs/site-release-requests/release-01.json'
  write(root,request,json.dumps({'kind':'jra_site_ui_explicit_approval_v1','mode':'release',
    'target_version':'v1.01','expected_staging_sha':staged,
    'approval_note':'Explicit user approval of stage v1.01.'}))
  run(root,sys.executable,str(TOOL),request)
  assert 'special-2026-10-11-tokyo12.html' not in (root/'docs/index.html').read_text()
  assert '正式版 v1.01' in (root/'docs/index.html').read_text()
  assert 'href="release-history.html"' in (root/'docs/index.html').read_text()
  assert json.loads((root/'docs/data/jra-site-ui-history.json').read_text())['current_version']=='v1.01'
  assert (root/'docs/data/races.json').read_text()=='{"immutable_original":true}\n'
  files=set(run(root,'git','diff','--name-only').splitlines())
  assert files=={'docs/index.html','docs/this-week.html'},files
  run(root,'git','add','docs/index.html','docs/this-week.html','docs/data/jra-site-ui-history.json')
  run(root,'git','commit','-qm','v1.01 release')
  run(root,'git','tag','-a','jra-site-v1.01','-m','v1.01 snapshot')
  request='docs/site-release-requests/rollback-01.json'
  write(root,request,json.dumps({'kind':'jra_site_ui_explicit_approval_v1','mode':'rollback',
    'target_version':'v1.00','approval_note':'Explicit user approval to restore v1.00.'}))
  run(root,sys.executable,str(TOOL),request)
  assert (root/'docs/index.html').read_text()=='<html>special-2026-10-11-tokyo12.html</html>'
  assert (root/'docs/this-week.html').read_text()=='<html>special-2026-10-11-tokyo12.html</html>'
  ledger=json.loads((root/'docs/data/jra-site-ui-history.json').read_text())
  assert ledger['current_version']=='v1.00'
  assert len(ledger['versions'])==2 and len(ledger['events'])==2
  assert (root/'docs/data/races.json').read_text()=='{"immutable_original":true}\n'
  print('PASS_SITE_RELEASE_ROLLBACK_IMMUTABLE_DATA',base,staged)
if __name__=='__main__':main()

