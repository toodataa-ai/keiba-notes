#!/usr/bin/env python3
"""Prepare a user-approved JRA UI-only release/rollback; NEVER edit race data or formal bets.
Run in an Actions checkout of main AFTER one immutable approval request was pushed.
The runner must commit and deploy only allow-listed UI and version ledger files."""
import json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ALLOWED={'docs/index.html','docs/this-week.html','docs/data/jra-site-ui-history.json'}
LEDGER=Path('docs/data/jra-site-ui-history.json')
STAGE='origin/staging/jra-ui-v101-three-plus-ana'
def git(*args):
 return subprocess.check_output(['git',*args],text=True).strip()
def fail(x):raise SystemExit('JRA_UI_RELEASE_BLOCKER: '+str(x))
def version(v):
 if not isinstance(v,str) or not re.fullmatch(r'v\d+\.\d{2}',v):fail('invalid version label')
 return v
def source(ref,path):
 try:return subprocess.check_output(['git','show',ref+':'+path])
 except subprocess.CalledProcessError:fail('missing tagged/staged source file '+ref+':'+path)
def main(request):
 p=Path(request)
 if (not p.as_posix().startswith('docs/site-release-requests/') or
     p.suffix!='.json' or not p.is_file()):fail('unsafe approval request path')
 req=json.loads(p.read_text(encoding='utf8'))
 if req.get('kind')!='jra_site_ui_explicit_approval_v1':fail('explicit approval request kind missing')
 mode=req.get('mode')
 if mode not in ('release','rollback'):fail('unsupported mode')
 target=version(req.get('target_version'))
 if not req.get('approval_note') or len(req['approval_note'].strip())<10:
  fail('human confirmation note required')
 old=json.loads(LEDGER.read_text(encoding='utf8')) if LEDGER.is_file() else {
  'schema_version':1,'current_version':'v1.00','versions':[],
  'events':[],'scope':'JRA SITE PRESENTATION ONLY; all race originals and data excluded'}
 if old['current_version']==target:fail('same version already live; no duplicate release')
 when=datetime.now(timezone.utc).isoformat()
 if mode=='release':
  if target!='v1.01':fail('only reviewed v1.01 candidate is currently allowed')
  # This is SITE-ONLY. The three+ana prototype stays explicitly labelled
  # as shadow and cannot be promoted to formal final_bets by this UI gate.
  ref=git('rev-parse',STAGE)
  if req.get('expected_staging_sha')!=ref:fail('staging changed after user approval')
  if old['current_version']!='v1.00':fail('v1.01 must build from v1.00')
  baseline=git('rev-parse','HEAD')
  if not old['versions']:
   old['versions'].append({'version':'v1.00','tag':'jra-site-v1.00','sha_at_release':baseline,
      'description':'Original pre-staging production HTML','last_deployed_at':None})
  for file in ('docs/index.html','docs/this-week.html'):
   raw=source(STAGE,file).decode('utf8')
   if 'special-2026-10-11-tokyo12.html' in raw:fail('temporary 12R still linked')
   raw=raw.replace('正式版 v1.00 ／ ステージング v1.01（未公開）','正式版 v1.01')
   raw=raw.replace('href="staging/release-history.html"','href="release-history.html"')
   Path(file).write_text(raw,encoding='utf8')
  old['versions'].append({'version':target,'tag':'jra-site-'+target,
    'source_staging_sha':ref,'description':'Compact research preview, remove 12R links, release navigation',
    'last_deployed_at':when})
  old['current_version']=target
  old['events'].append({'at':when,'action':'release','version':target,
    'approved_request':p.as_posix(),'stage_sha':ref})
 else:
  if not any(x['version']==target for x in old['versions']):fail('requested rollback tag was never recorded')
  tag='jra-site-'+target
  try:git('rev-parse','refs/tags/'+tag)
  except subprocess.CalledProcessError:fail('missing immutable rollback tag '+tag)
  for file in ('docs/index.html','docs/this-week.html'):
   Path(file).write_bytes(source(tag,file))
  old['current_version']=target
  old['events'].append({'at':when,'action':'rollback','version':target,
    'approved_request':p.as_posix(),'immutable_source_tag':tag})
 LEDGER.parent.mkdir(parents=True,exist_ok=True)
 LEDGER.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 # Don't stage the approval request itself: already exists on main and is immutable.
 changed=set(git('diff','--name-only').splitlines())
 if not changed or not changed.issubset(ALLOWED):fail('unexpected non-presentation change '+str(changed))
 print('JRA_UI_RELEASE_PREPARED',mode,target,sorted(changed))
 print('JRA_UI_PREPARED_SOURCE_TAG',('jra-site-v1.00' if mode=='release' else 'none'))
if __name__=='__main__':
 if len(sys.argv)!=2:fail('one request path required')
 main(sys.argv[1])

