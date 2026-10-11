#!/usr/bin/env python3
"""Live 2026-10-11 JRA fixture adapter. Scrapes primary JRA form and actual (non-predicted)
Sportnavi odds, then emits v3.10 audited prereace inputs. Never fetches race results.
The fixed, pre-market STEP1 marks are loaded from the immutable prior research file.
No odds are used for ranking, factor grades, weight generation, or strategy planning."""
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT=Path('.')
DATE='2026-10-11'
PREVIEW=Path('docs/research/2026-10-11-jra-main-step1-preview-v310.json')
RACES=[
 dict(slug='2026-10-11-ireland-trophy',venue='東京',name='アイルランドトロフィー',race_no=11,
      start_at='2026-10-11T15:45:00+09:00',race_code='2605040411',
      official='https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0105202604041120261011/CE',
      surface='芝',distance_m=1800),
 dict(slug='2026-10-11-uzumasa-stakes',venue='京都',name='太秦ステークス',race_no=11,
      start_at='2026-10-11T15:30:00+09:00',race_code='2608040411',
      official='https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604041120261011/AC',
      surface='ダート',distance_m=1800)]
PATHS={'tfw':'単勝・複勝・枠連','ur':'馬連','wide':'ワイド','ut':'馬単','sf':'三連複','st':'三連単'}
from urllib.parse import urlparse
JST=ZoneInfo('Asia/Tokyo')
session=requests.Session()
session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; JRA live prerace audit; contact: GitHub repository toodataa-ai/keiba-notes)'})
def now():
 return datetime.now(JST).isoformat(timespec='milliseconds')
def require(cond,msg):
 if not cond:raise RuntimeError('BLOCKER: '+msg)
def load(url):
 r=session.get(url,timeout=25);r.raise_for_status()
 require(len(r.content)>1500,'empty remote HTML '+url)
 return r.content,BeautifulSoup(r.content,'html.parser')
def text(x):
 return re.sub(r'\s+',' ',x.get_text(' ',strip=True)).strip()
def intmatch(regex,s,default=None):
 m=re.search(regex,s)
 return int(m.group(1)) if m else default
def past_from(cell,dist,surface,venue):
 t=text(cell)
 m=re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日',t)
 where=(t[m.end():].strip().split(' ')[0] if m else '')
 d=re.search(r'(\d{3,4})(芝|ダ)',t)
 finish=intmatch(r'(\d+)\s*着',t)
 klass='G1' if 'GⅠ' in t or 'G1' in t else 'G2' if 'GⅡ' in t or 'G2' in t else 'G3' if 'GⅢ' in t or 'G3' in t else 'OP' if 'OP' in t or 'L ' in t else '3勝' if '3勝' in t else 'other'
 stamps=re.search(r'(\d+:\d+\.\d+)',t)
 date='%04d-%02d-%02d'%tuple(map(int,m.groups())) if m else None
 return dict(date=date,course=where,distance_m=int(d.group(1)) if d else None,
             surface=('芝' if d and d.group(2)=='芝' else 'ダート' if d else None),finish=finish,
             class_name=klass,time=stamps.group(1) if stamps else None,
             same_condition=(where==venue and d and int(d.group(1))==dist and ((d.group(2)=='芝' and surface=='芝') or (d.group(2)=='ダ' and surface=='ダート'))),
             source_excerpt=t[:260])
def official_form(race):
 raw,soup=load(race['official'])
 tables=soup.select('table')
 require(tables,'official JRA form table missing')
 rows=tables[0].select('tr')
 data={}
 for tr in rows:
  no=tr.select_one('td.num');horse=tr.select_one('td.horse');jockey=tr.select_one('td.jockey')
  if not (no and horse and jockey):continue
  n=intmatch(r'(\d+)',text(no));require(n is not None,'invalid official horse number')
  name=text(horse).split(' ')[0]
  parts=text(jockey)
  kg=re.search(r'(\d{2}(?:\.\d)?)\s*kg',parts)
  past=[past_from(p,race['distance_m'],race['surface'],race['venue']) for p in tr.select('td.past')]
  data[n]=dict(number=n,name=name,jockey=parts,weight_kg=float(kg.group(1)) if kg else None,
               past=past,source_url=race['official'])
 require(len(data)>=9,'official racing form unexpectedly few horses')
 require('良' in text(tables[0]) or '稍重' in text(tables[0]) or '重' in text(tables[0]),'official going unavailable')
 m=re.search(r'(?:芝|ダート)\s*(良|稍重|重|不良)',text(tables[0]))
 return data,m.group(1) if m else '未確認',hashlib.sha256(raw).hexdigest()
def odds_value(value):
 raw=value.strip().replace(',','')
 if any(x in raw for x in ('****','---','取消','除外','99999.9')):return None
 m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?',raw)
 if not m:return None
 a=float(m.group(1));b=float(m.group(2)) if m.group(2) else None
 if a<=1:return None
 return [a,b] if b and b>=a else a
def rows(table):
 for tr in table.select('tr'):
  cells=tr.find_all(['th','td'],recursive=False)
  yield [text(c) for c in cells]
def parse_odds(kind,soup):
 res={}
 tables=soup.select('table')
 if kind=='tfw':
  require(len(tables)>=2,'single/place/frame tables missing')
  for row in list(rows(tables[0]))[1:]:
   if len(row)<5:continue
   try:frame,no=int(row[0]),int(row[1])
   except ValueError:continue
   res[('単勝',(no,))]=odds_value(row[3])
   res[('複勝',(no,))]=odds_value(row[4])
   res[('_frame',(no,))]=frame
  for t in tables[1:]:
   rr=list(rows(t))
   if not rr:continue
   try:first=int(rr[0][0])
   except (ValueError,IndexError):continue
   for row in rr[1:]:
    if len(row)<2:continue
    try:no=int(row[0])
    except ValueError:continue
    res[('枠連',tuple(sorted([first,no])))]=odds_value(row[1])
 elif kind in ('ur','wide','ut','sf'):
  kindType={'ur':'馬連','wide':'ワイド','ut':'馬単','sf':'三連複'}[kind]
  for t in tables:
   rr=list(rows(t))
   if not rr:continue
   h=[int(n) for n in re.findall(r'\d+',rr[0][0])]
   if len(h)!=(2 if kind=='sf' else 1):continue
   for row in rr[1:]:
    if len(row)<2:continue
    try:horse=int(row[0])
    except ValueError:continue
    sel=h+[horse]
    if kind in ('ur','wide','sf'):sel.sort()
    res[(kindType,tuple(sel))]=odds_value(row[1])
 elif kind=='st':
  for t in tables:
   for row in list(rows(t))[1:]:
    if len(row)<2:continue
    sel=[int(n) for n in re.findall(r'\d+',row[0])]
    if len(sel)!=3:continue
    res[('三連単',tuple(sel))]=odds_value(row[1])
 return {k:v for k,v in res.items() if v is not None}
def rating_for(p,prev,grade):
 score={'A+':5,'A':4,'B+':3,'B':2,'B-':1,'C':0}[grade]
 cp=[x for x in p if x.get('same_condition')]
 good=[x for x in p if x.get('finish') and x['finish']<=3]
 first=p[0] if p else {}
 distgood=[x for x in p if x.get('distance_m')==1800 and x.get('surface')==prev['surface'] and x.get('finish') and x['finish']<=3]
 grades=['A','A','B','B','B','B','B-','B','B']
 grades[0]='B+' if prev['weight_kg']<=55 else 'B'
 grades[1]='B+' if good and p and p[0].get('finish') and p[0]['finish']<=3 else 'B'
 grades[2]='A' if good and first.get('surface')==prev['surface'] else 'B'
 grades[3]='B+' if first.get('date') and first['date']>='2026-08-01' else 'B-' if first.get('date') and first['date']<'2026-06-01' else 'B'
 grades[4]='A+' if cp and any(x.get('finish') and x['finish']<=3 for x in cp) else 'A' if distgood else 'B'
 grades[5]='B' # pedigree compatibility not established, never pretend evidence
 grades[6]='B-' # workout not independently observed (uncertainty, NOT bad form)
 grades[7]='B' # jockey course-adjusted statistics not independently observed
 grades[8]=grade
 return grades,cp,good
def strategies(top,frame):
 from itertools import combinations
 T=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単']
 modes={'単勝':['single','multiple_singles'],'複勝':['single','multiple_singles'],
        '枠連':['single','box','key_wheel','formation'],
        '馬連':['single','box','key_wheel','formation'],
        '馬単':['single','box','key_wheel_first','key_wheel_second','key_wheel_multi','formation'],
        'ワイド':['single','box','key_wheel','formation'],
        '三連複':['single','box','one_key_wheel','two_key_wheel','formation'],
        '三連単':['single','box','formation','one_key_fixed','two_key_fixed','one_key_multi','two_key_multi']}
 a=top[:6];a1,a2,a3,a4,a5,a6=a
 frames=list(dict.fromkeys(frame[n] for n in top))[:6]
 require(len(frames)>=4,'insufficient unique frame numbers')
 configs=[]
 for kind in ['単勝','複勝']:
  configs += [(kind,'single',{'selection':[a1]}),(kind,'multiple_singles',{'horses':a[:5]})]
 for kind in ['枠連','馬連','ワイド']:
  b=frames if kind=='枠連' else a
  configs += [(kind,'single',{'selection':[b[0],b[1]]}),(kind,'box',{'horses':b[:5]}),
    (kind,'key_wheel',{'key':b[0],'partners':b[1:6]}),
    (kind,'formation',{'slots':[b[:2],b[2:5]]})]
 b=a
 configs += [('馬単','single',{'selection':[a1,a2]}),('馬単','box',{'horses':a[:5]})]
 for mode in ['key_wheel_first','key_wheel_second','key_wheel_multi']:
  configs.append(('馬単',mode,{'key':a1,'partners':a[1:6]}))
 configs += [('馬単','formation',{'slots':[[a1,a2],[a2,a3,a4,a5]]})]
 configs += [('三連複','single',{'selection':[a1,a2,a3]}),
  ('三連複','box',{'horses':a[:6]}),
  ('三連複','one_key_wheel',{'key':a1,'partners':a[1:6]}),
  ('三連複','two_key_wheel',{'axes':[a1,a2],'partners':a[2:6]}),
  ('三連複','formation',{'slots':[[a1,a2],[a2,a3,a4],[a3,a4,a5,a6]]})]
 configs += [('三連単','single',{'selection':[a1,a2,a3]}),
  ('三連単','box',{'horses':a[:5]}),
  ('三連単','formation',{'slots':[[a1,a2],[a2,a3,a4],[a3,a4,a5,a6]]}),
  ('三連単','one_key_fixed',{'key':a1,'position':1,'partners':a[1:6]}),
  ('三連単','two_key_fixed',{'axes':[a1,a2],'positions':[1,2],'partners':a[2:6]}),
  ('三連単','one_key_multi',{'key':a1,'partners':a[1:6]}),
  ('三連単','two_key_multi',{'axes':[a1,a2],'partners':a[2:6]})]
 return [dict(strategy_id='S%02d'%(i+1),type=t,strategy_kind=m,definition=d,
    ability_reason='STEP1固定順位上位と同条件実績/展開根拠による価格非参照の事前候補',
    risk_reason='先行競合・馬場変動・未校正勝率および多点数の資金損失',
    decision_reason='発走前に事前計画。最終採否は正確な個別オッズを取得後に決定') for i,(t,m,d) in enumerate(configs)]
def build(race,preview):
 require(datetime.now(JST).isoformat()<race['start_at'],'already past post time')
 official,going,officialsha=official_form(race)
 old={h['number']:h for h in preview['horses']}
 require(set(official)==set(old),'JRA official roster differs from frozen pre-market STEP1')
 scored=[]
 for no,h in sorted(official.items()):
  prior=old[no]
  require(h['name']==prior['name'],'horse number-to-name mismatch '+str(no))
  require(h['weight_kg']==prior['weight_kg'],'weight/roster changed '+str(no))
  p=h['past'];grades,cp,good=rating_for(p,dict(weight_kg=h['weight_kg'],surface=race['surface']),prior['overall_grade'])
  scored.append(dict(horse_number=no,horse_name=h['name'],mark=prior['mark'],overall_grade=prior['overall_grade'],
    factor_grades=grades,weight_kg=h['weight_kg'],jockey=h['jockey'],
    evidence=prior['judgement']+'。JRA前走：'+(p[0]['source_excerpt'][:145] if p else '出走歴未取得'),
    source_url=race['official'],past_performances=p,
    workout_data_status='unavailable',jockey_course_stats_status='unavailable'))
 # The following mapping is an explicitly uncalibrated score-to-probability proxy,
 # not a market-odds inverse and not a verified hit rate. Central is stable for each run.
 gradew={'A+':5.3,'A':3.7,'B+':2.55,'B':1.65,'B-':1.0,'C':0.6}
 markw={'◎':1.18,'○':1.12,'▲':1.08,'△':1.0,'×':0.90}
 vals=[gradew[h['overall_grade']]*markw[h['mark']] for h in scored]
 total=sum(vals)
 for h,w in zip(scored,vals):h['win_probability']=w/total
 fixed_at=now()
 rank=sorted(scored,key=lambda h:({'◎':0,'○':1,'▲':2,'△':3,'×':4}[h['mark']],-gradew[h['overall_grade']],h['horse_number']))
 top=[h['horse_number'] for h in rank]
 # Need official horse-number / frame-number, obtain separately from t/f/w page.
 # This first read is for official numbered frame confirmation and no odds access
 # for strategy selection. Only frame mapping is used here; price-bearing fields are ignored.
 # Prefer JRA official frame cell; when absent use the official conventional 8-frame assignment
 # for 14 and 16 runners, cross-check with market race card AFTER plan generated.
 n=len(scored)
 expected_frame_16=[1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8]
 expected_frame_14=[1,2,3,3,4,4,5,5,6,6,7,7,8,8]
 require(n in (14,16),'unsupported field size requires official frame parser audit')
 frame={h['horse_number']:(expected_frame_16 if n==16 else expected_frame_14)[h['horse_number']-1] for h in scored}
 st=strategies(top,frame)
 plan_at=now()
 require(plan_at<=race['start_at'],'no time to snapshot before post')
 # Snapshot price catalogs AFTER STEP1 and strategy plan have been created.
 market={}
 captures=[]
 race_dir=Path('e2e_validation/quote-evidence')/race['slug']
 race_dir.mkdir(parents=True,exist_ok=True)
 for part in PATHS:
  url='https://sports.yahoo.co.jp/keiba/race/odds/'+part+'/'+race['race_code']+'?ninki=0'
  raw,soup=load(url);captured_at=now()
  items=parse_odds(part,soup)
  require(items,'odds source parsed zero selections '+url)
  for key,odds in items.items():
   if key[0]=='_frame':
    require(frame[key[1][0]]==odds,'frame mismatch from JRA convention for horse '+str(key))
  items={k:v for k,v in items.items() if k[0]!='_frame'}
  update=re.search(r'20\d\d/\d\d/\d\d\s+\d\d:\d\d\s*更新',text(soup))
  capture=dict(source_url=url,observed_at=captured_at,source_last_updated=update.group(0) if update else 'not provided',
    source_html_sha256=hashlib.sha256(raw).hexdigest(),source_bytes=len(raw),
    entries=[dict(type=k[0],selection=list(k[1]),market_odds=v) for k,v in sorted(items.items())])
  target=race_dir/(part+'.json')
  payload=json.dumps(capture,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
  target.write_bytes(payload)
  digest=hashlib.sha256(payload).hexdigest()
  captures.append(dict(path=str(target),sha=digest,source=url,count=len(items),timestamp=captured_at))
  for k,v in items.items():market[k]=(v,url,captured_at,target,digest)
  print('CAPTURE',race['slug'],part,'priced',len(items),'html',len(raw),'at',captured_at,flush=True)
 # Import the canonical JS expander list via a local Node subprocess; do not maintain
 # a separate Python copy of the trading strategy expansion rules.
 import subprocess
 js='''import {expandStrategy} from "./.github/scripts/jra-strategy-engine-v39.mjs";import fs from "node:fs";const a=JSON.parse(fs.readFileSync(0,"utf8"));process.stdout.write(JSON.stringify(a.map(x=>{try{return expandStrategy(x.type,x.strategy_kind,x.definition)}catch(e){throw Error(x.type+' '+x.strategy_kind+' '+e.message)}}))));'''
 p=subprocess.run(['node','--input-type=module','-e',js],input=json.dumps(st,ensure_ascii=False),encoding='utf-8',capture_output=True)
 require(p.returncode==0,'canonical strategy expansion failed: '+p.stderr[-2000:])
 selection_universe=set()
 for group in json.loads(p.stdout):
  for l in group:
   k=(l['type'],tuple(l['selection']))
   if k[0] in ('馬連','ワイド','枠連','三連複'):k=(k[0],tuple(sorted(k[1])))
   selection_universe.add(k)
 quotes=[]
 for t,sel in sorted(selection_universe):
  q=market.get((t,sel))
  if not q:continue
  price,url,at,target,digest=q
  quotes.append(dict(race_id=race['slug'],type=t,selection=list(sel),market_selection_id=t+':'+json.dumps(list(sel),separators=(',',':')),
    market_odds=price,source_url=url,observed_at=at,source_capture_path=str(target),source_capture_sha256=digest,
    quote_verified=True))
 require(quotes,'no real odds match any prereace planned ticket')
 factors={}
 for label,mult in [('low',.82),('high',1.18)]:
  x={}
  for h in scored:
   direct=any(p['same_condition'] and p['finish'] is not None and p['finish']<=3 for p in h['past_performances'])
   x[str(h['horse_number'])]=mult if direct else (2-mult)
  factors[label]=dict(assumption='JRA同競馬場同距離直近4走の好走馬に対する相対上振れ／下振れ18%の仮定。未校正の感応度シナリオ',by_horse=x)
 inp=dict(prompt_version='v3.10',race_id=race['slug'],race_context=dict(date=DATE,venue=race['venue'],race_no=race['race_no'],
    race_name=race['name'],start_at=race['start_at'],surface=race['surface'],distance_m=race['distance_m'],
    official_source_url=race['official'],official_form_sha256=officialsha,
    official_going=going,going_observed_at=fixed_at,sale_field_size=len(scored),place_paid_positions=3,
    offered_types=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単']),
  frame_map={str(k):v for k,v in frame.items()},
  step1=dict(fixed_at=fixed_at,primary_source=race['official'],no_odds_used_to_change_marks=True,
    marks_source='docs/research/2026-10-11-jra-main-step1-preview-v310.json',
    probability_method='uncalibrated published frozen overall grade × immutable mark hierarchy normalized; zero market involvement',
    calibrated=False,runners=scored),
  scenario_factors=factors,strategy_plan_fixed_at=plan_at,strategies=st,
  mode_exclusions=[],market_quotes=quotes,input_source='Official JRA form and pre-market frozen mark research; independently scraped current Sportnavi JRA middle odds; records are not calibrated')
 target=Path('e2e_validation/inputs')/(race['slug']+'.json')
 target.parent.mkdir(parents=True,exist_ok=True)
 require(not target.exists(),'existing prereace input is immutable: '+str(target))
 target.write_text(json.dumps(inp,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('INPUT_READY',race['slug'],'runners',len(scored),'strategies',len(st),'unique planned lines',len(selection_universe),
       'priced planned lines',len(quotes),'market snapshot files',len(captures),'going',going,'fixed_at',fixed_at,flush=True)
 return str(target),captures
if __name__=='__main__':
 preview=json.loads(PREVIEW.read_text(encoding='utf-8'))
 output=[]
 for race in RACES:
  r=next((x for x in preview['races'] if x['id']==race['slug']),None)
  require(r is not None,'missing frozen prereace STEP1 research '+race['slug'])
  output.append(build(race,r))
 Path('/tmp/jra-v310-actual-input-manifest.json').write_text(json.dumps([{'input':a,'captures':b} for a,b in output],ensure_ascii=False))
 print('DONE_PRERACE_INPUTS',len(output),flush=True)
