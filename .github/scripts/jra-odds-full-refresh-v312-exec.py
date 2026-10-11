#!/usr/bin/env python3
"""v3.12 execution-only freshness addendum (prior v3.12 model unchanged); exact v3.12 price recovery: discover genuine Sportnavi selection-form controls and
capture exact odds. Missing odds never become zero EV or guessed market quotes.
Must run before post; original prereace input is never overwritten."""
import argparse,hashlib,importlib.util,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup

TYPES={'単勝':'tfw','複勝':'tfw','枠連':'tfw','馬連':'ur',
 'ワイド':'wide','馬単':'ut','三連複':'sf','三連単':'st'}
def require(ok,msg):
 if not ok:raise RuntimeError('BLOCKER: '+msg)
def iso():return datetime.now(timezone.utc).isoformat(timespec='milliseconds')
def utc(s):return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(timezone.utc)
def canonical(t,nums):
 return (t,tuple(sorted(nums) if t in ('馬連','ワイド','枠連','三連複') else nums))
def safe_form_url(base,url):
 target=urljoin(base,url)
 a,b=urlparse(base),urlparse(target)
 require(a.scheme=='https' and a.hostname=='sports.yahoo.co.jp','Sportnavi HTTPS source required')
 require(b.scheme=='https' and b.hostname==a.hostname and b.path==a.path,
         'refuse unsourced or foreign odds form '+target)
 return target
def candidate_expansion(strategies):
 # One canonical strategy expander shared with production, no guessed formation lines.
 js='''import {expandStrategy} from "./.github/scripts/jra-strategy-engine-v39.mjs";
 import fs from "node:fs";const a=JSON.parse(fs.readFileSync(0,"utf8"));
 process.stdout.write(JSON.stringify(a.flatMap(s=>expandStrategy(s.type,s.strategy_kind,s.definition))));'''
 p=subprocess.run(['node','--input-type=module','-e',js],
     input=json.dumps(strategies,ensure_ascii=False),text=True,capture_output=True)
 require(p.returncode==0,'canonical strategy expansion failed: '+p.stderr[-900:])
 lines=json.loads(p.stdout)
 return {canonical(line['type'],line['selection']) for line in lines}
def capture(body,url,kind,parser,sink,seq):
 observed=iso();soup=BeautifulSoup(body,'html.parser')
 data=parser.parse_odds(kind,soup)
 pairs={canonical(t,sel):v for (t,sel),v in data.items() if t!='_frame'}
 if not pairs:return {},None
 doc={'source_url':url,'observed_at':observed,'source_html_sha256':hashlib.sha256(body).hexdigest(),
   'source_bytes':len(body),'source_last_updated':'not independently verified',
   'entries':[{'type':key[0],'selection':list(key[1]),'market_odds':price}
       for key,price in sorted(pairs.items())]}
 payload=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 path=sink/(kind+'-repair-'+str(seq).zfill(3)+'.json')
 require(not path.exists(),'existing quote evidence must not be overwritten: '+str(path))
 path.write_bytes(payload)
 return pairs,{'path':str(path),'sha':hashlib.sha256(payload).hexdigest(),
               'at':observed,'url':url}
def form_queries(base,soup,first_horse):
 """Only submit controls actually advertised by the current source's HTML form.
 No invented query parameters; inspect response afterwards for the exact triple."""
 for form in soup.select('form'):
  action=form.get('action') or base
  try:target=safe_form_url(base,action)
  except RuntimeError:continue
  if form.get('method','get').lower()!='get':continue
  params={}
  for x in form.select('input[name]'):
   if x.get('type','').lower() in ('hidden','text') and x.get('value') is not None:
    params[x['name']]=x['value']
  selectors=[s for s in form.select('select[name]') if s.select('option')]
  axis=None
  for s in selectors:
   opts=[(o.get('value',''),o.get_text(' ',strip=True)) for o in s.select('option')]
   matches=[v for v,label in opts if v==str(first_horse) and
     len([o for o in opts if o[0].isdigit()])>=4]
   if matches and axis is None:axis=s;params[s['name']]=matches[0]
   else:
    selected=next((o for o in s.select('option') if o.has_attr('selected')),s.select('option')[0])
    params[s['name']]=selected.get('value','')
    if any(re.search(r'1着',o.get_text(' ',strip=True)) for o in s.select('option')):
     one=next(o for o in s.select('option') if '1着' in o.get_text(' ',strip=True))
     params[s['name']]=one.get('value','')
  if axis is not None:yield target,params
def recover(input_path,output_path,evidence,refresh_all=False,max_capture_spread_seconds=180):
 original=json.loads(input_path.read_text(encoding='utf-8'))
 require(original['prompt_version']=='v3.12','requires v3.12 audited prereace input')
 require(not output_path.exists(),'never overwrite an existing v3.12 input')
 require(utc(iso())<utc(original['race_context']['start_at']),'race already started')
 require(utc(original['strategy_plan_fixed_at'])<utc(iso()),'strategy plan must precede quotes')
 expected=candidate_expansion(original['strategies'])
 present=set() if refresh_all else {canonical(q['type'],q['selection']) for q in original.get('market_quotes',[])}
 missing=expected-present
 evidence.mkdir(parents=True,exist_ok=True)
 if not missing:
  print('QUOTE_COVERAGE_ALREADY_COMPLETE',len(expected))
  output_path.write_text(json.dumps(original,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  return
 spec=importlib.util.spec_from_file_location('old_jra_collector',Path('.github/scripts/jra-gather-live-20261011-v310.py'))
 parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
 prices={};sources={}
 session=requests.Session();session.headers.update({'User-Agent':'Mozilla/5.0 JRA-quote-provenance-v312'})
 raw_urls=[q['source_url'] for q in original.get('market_quotes',[]) if q.get('source_url')]
 require(raw_urls,'no documented odds source URLs; cannot synthesize provider endpoint')
 anchor=next((u for u in raw_urls if '/race/odds/' in u),None)
 require(anchor is not None,'no documented Sportnavi base')
 first=parse_base=urlparse(anchor)
 require(first.hostname=='sports.yahoo.co.jp' and first.scheme=='https','supported odds source unavailable')
 race_code=first.path.split('/')[-1]
 base='https://sports.yahoo.co.jp/keiba/race/odds/'
 targets=sorted({TYPES[t] for t,_ in missing})
 requests_made=0
 for kind in targets:
  url=base+kind+'/'+race_code+'?ninki=0'
  if kind not in TYPES.values():continue
  response=session.get(url,timeout=25);response.raise_for_status();requests_made+=1
  require(len(response.content)>1500,'empty page '+url)
  pages=[(response.content,response.url)]
  if kind=='st':
   missing_axes=sorted({sel[0] for t,sel in missing if t=='三連単'})
   # The actual source declares new window.sn.hr.searchBox({umaban_id,
   # position_id, link_base}) and the served JS defines:
   # location.href=link_base+'?umaBan='+umaban+'&position='+position.
   # Inspect BOTH artifacts on each run; never guess query names or axis values.
   source_soup=BeautifulSoup(response.content,'html.parser')
   inline='\\n'.join(x.get_text() for x in source_soup.select('script') if 'new window.sn.hr.searchBox' in x.get_text())
   select_horse=source_soup.select_one('#js-umaBan')
   select_pos=source_soup.select_one('#js-position')
   script_src=next((x.get('src') for x in source_soup.select('script[src]')
      if '/keiba/js/pc/script.js' in (x.get('src') or '')),None)
   if 'link_base:' in inline and select_horse is not None and select_pos is not None and script_src:
    from urllib.parse import urljoin
    script_url=urljoin(response.url,script_src)
    require(urlparse(script_url).hostname=='sports.yahoo.co.jp','unsupported source JavaScript host')
    js=session.get(script_url,timeout=25);js.raise_for_status()
    require("location.href=link_base+'?umaBan='+umaban+'&position='+position" in js.text,
       'live source JS no longer documents exact umaBan and position query')
    m=re.search(r"link_base:\s*'([^']+)'",inline)
    require(m is not None,'live odds searchBox missing explicit link_base')
    action=urljoin(response.url,m.group(1))
    require(urlparse(action).hostname=='sports.yahoo.co.jp' and
      urlparse(action).path=='/keiba/race/odds/st/'+race_code,'unsafe odds link_base')
    allowed_axes={o.get('value') for o in select_horse.select('option')}
    first_option=next((o for o in select_pos.select('option')
       if '1着' in o.get_text(' ',strip=True)),None)
    require(first_option is not None and first_option.get('value'),
      'first-place position value not verified from HTML')
    first_value=first_option['value']
    print('PROVIDER_QUERY_CONTRACT',action,'umaBan + position',first_value,'axes',len(allowed_axes),flush=True)
    for axis in missing_axes:
     require(str(axis) in allowed_axes,'requested axis not in source picker: '+str(axis))
     quote_response=session.get(action,params={'umaBan':str(axis),'position':first_value},timeout=25)
     quote_response.raise_for_status()
     require(urlparse(quote_response.url).hostname=='sports.yahoo.co.jp' and
       urlparse(quote_response.url).path==urlparse(action).path,'unsafe odds request redirect')
     requests_made+=1
     pages.append((quote_response.content,quote_response.url))
     require(requests_made<=64,'too many source-defined odds requests')
   discovered=set()
   for axis in missing_axes:
    for action,params in form_queries(response.url,BeautifulSoup(response.content,'html.parser'),axis):
     key=(action,tuple(sorted(params.items())))
     if key in discovered:continue
     discovered.add(key)
     r=session.get(action,params=params,timeout=25);r.raise_for_status()
     require(urlparse(r.url).hostname=='sports.yahoo.co.jp','redirect to foreign odds host')
     requests_made+=1
     pages.append((r.content,r.url))
     require(requests_made<=64,'too many quote requests: stop before rate limit')
  if kind=='st':
   pop=session.get(base+kind+'/'+race_code+'?ninki=1',timeout=25);pop.raise_for_status()
   pages.append((pop.content,pop.url));requests_made+=1
  for seq,(body,where) in enumerate(pages,1):
   quotes,meta=capture(body,where,kind,parser,evidence,seq)
   if not quotes:continue
   for key,value in quotes.items():
    if key not in missing or key in prices:continue
    prices[key]=value;sources[key]=meta
 remaining=missing-set(prices)
 if remaining:
  sample=[t+'-'+','.join(map(str,sel)) for t,sel in sorted(remaining)[:20]]
  raise RuntimeError('BLOCKER: still missing '+str(len(remaining))+' exact odds of '+str(len(expected))+
    ' after documented source form, base and popularity queries: '+str(sample)+
    '. Do not produce formal snapshot or claim full coverage.')
 new=json.loads(json.dumps(original))
 if refresh_all:
  # The old odds catalog is used only to discover the documented provider URL.
  # Not even one historical price may survive into the new purchasing snapshot.
  new['market_quotes']=[]
  first=min(utc(v['at']) for v in sources.values())
  last=max(utc(v['at']) for v in sources.values())
  span=(last-first).total_seconds()
  require(span<=max_capture_spread_seconds,'stale cross-market capture window '+str(span)+' seconds')
  require(utc(iso())<utc(new['race_context']['start_at']),'race started during full-price refresh')
 for key in sorted(prices):
  meta=sources[key]
  require(utc(meta['at'])>utc(new['strategy_plan_fixed_at']),'recovered quote precedes strategy plan')
  require(utc(meta['at'])<utc(new['race_context']['start_at']),'recovered quote after race start')
  t,sel=key;new['market_quotes'].append({
   'race_id':new['race_id'],'type':t,'selection':list(sel),
   'market_selection_id':t+':'+json.dumps(list(sel),separators=(',',':')),
   'market_odds':prices[key],'source_url':meta['url'],'observed_at':meta['at'],
   'source_capture_path':meta['path'],'source_capture_sha256':meta['sha'],'quote_verified':True})
 require(len(new['market_quotes'])==len(expected),'market quote count mismatch; duplicates require audit')
 output_path.parent.mkdir(parents=True,exist_ok=True)
 output_path.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('QUOTE_COVERAGE_COMPLETE',len(expected),'recovered',len(prices),'source_requests',requests_made,
   'refresh_all',refresh_all,'all_prices_independently_refetched',refresh_all)
if __name__=='__main__':
 ap=argparse.ArgumentParser()
 ap.add_argument('--input',required=True);ap.add_argument('--output',required=True)
 ap.add_argument('--evidence-dir',required=True)
 ap.add_argument('--refresh-all',action='store_true',help='Forbid inherited market quotes; replace every individual exact ticket price')
 ap.add_argument('--max-capture-spread-seconds',type=int,default=180)
 args=ap.parse_args()
 try:recover(Path(args.input),Path(args.output),Path(args.evidence_dir),args.refresh_all,args.max_capture_spread_seconds)
 except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
