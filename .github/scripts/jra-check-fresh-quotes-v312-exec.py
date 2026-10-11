#!/usr/bin/env python3
"""Fail-closed, independent freshness audit of all strategy candidate odds."""
import argparse, datetime as dt,hashlib,json,subprocess
from pathlib import Path
def utc(s):
 return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(dt.timezone.utc)
def require(test,message):
 if not test:raise SystemExit('BLOCKER JRA FRESH ODDS: '+message)
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--input',required=True)
 p.add_argument('--fresh-seconds',type=int,default=600)
 p.add_argument('--max-spread-seconds',type=int,default=180)
 args=p.parse_args()
 d=json.loads(Path(args.input).read_text())
 now=dt.datetime.now(dt.timezone.utc)
 require(now<utc(d['race_context']['start_at']),'official race already started')
 quotes=d.get('market_quotes',[])
 require(quotes,'no odds')
 earliest=min(utc(q['observed_at']) for q in quotes)
 latest=max(utc(q['observed_at']) for q in quotes)
 require((now-earliest).total_seconds()>=0,'odds capture is from the future')
 require((now-earliest).total_seconds()<=args.fresh_seconds,
   'any exact ticket quote older than '+str(args.fresh_seconds)+' seconds')
 require((latest-earliest).total_seconds()<=args.max_spread_seconds,'markets captured in mixed windows')
 require(all(utc(q['observed_at'])<utc(d['race_context']['start_at']) for q in quotes),
   'post-race prices cannot be used for a prereace prediction')
 require(all(q.get('quote_verified') is True for q in quotes),'unverified odds item present')
 require(all(q.get('source_capture_path') and q.get('source_capture_sha256') for q in quotes),
   'an inherited/unproven quote survived the full refresh')
 evidence={}
 for q in quotes:
  path=q['source_capture_path']
  require(path.startswith('e2e_validation/quote-evidence/') and '..' not in path,'unsafe quote evidence path')
  require(Path(path).exists(),'evidence file missing '+path)
  evidence[path]=q['source_capture_sha256']
 for path,digest in evidence.items():
  require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,'source evidence SHA mismatch '+path)
  evidence_object=json.loads(Path(path).read_text())
  require(utc(evidence_object['observed_at'])>=earliest and utc(evidence_object['observed_at'])<=latest,
    'evidence observed_at not in coherent price window')
 assert len(quotes)==len({(q['type'],tuple(q['selection'])) for q in quotes}), 'duplicate market quotes'
 print('PASS FULL_FRESH_ODDS',d['race_id'],'quotes',len(quotes),'sources',len(evidence),
   'earliest',earliest.isoformat(),'latest',latest.isoformat(),
   'age_seconds',round((now-earliest).total_seconds(),3),
   'spread_seconds',round((latest-earliest).total_seconds(),3))
if __name__=='__main__':main()
