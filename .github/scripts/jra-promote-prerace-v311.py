#!/usr/bin/env python3
"""Safely replace only JRA's CURRENT public record with a newer sealed pre-post report.
Archived snapshots, proofs, prior JSON/PDFs, settlement/reviews are never rewritten.
All actual time checks use the GitHub runner's UTC clock; no CLI time override.
"""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import fitz

ROOT=Path('.')
INDEX=ROOT/'docs/data/races.json'
LOG=ROOT/'docs/data/jra_publication_revision_log.json'
POLICY=ROOT/'docs/data/jra_prerace_overwrite_policy_v1.json'
TEMPLATE=ROOT/'docs/data/jra-v311-parallel-2026-10-11.json'

def need(ok,msg):
    if not ok: raise RuntimeError('BLOCKER JRA PRE-POST PROMOTION: '+msg)

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def utc_time(s):
    x=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    need(x.tzinfo is not None,'timestamp lacks timezone: '+s)
    return x.astimezone(dt.timezone.utc)

def utc_now(): return dt.datetime.now(dt.timezone.utc)

def git_text(*args):
    return subprocess.check_output(['git',*args],text=True,encoding='utf-8',max_output_bytes=100_000_000) if False else subprocess.check_output(['git',*args],text=True,encoding='utf-8')

def check_proof(snap_path,proof,formal,race_start):
    need(isinstance(proof,str) and len(proof)==40 and all(x in '0123456789abcdef' for x in proof),'invalid proof SHA')
    prior=load_source_at_commit(proof,snap_path)
    need(prior.get('stage')=='pending_git_proof' and prior.get('proof_commit') is None,'not a genuine prereace snapshot')
    seal=copy.deepcopy(prior);seal['stage']='formal_prestart';seal['proof_commit']=proof
    need(seal==formal,'immutable proof snapshot does not match the sealed formal prediction')
    commit_utc=utc_time(git_text('show','-s','--format=%cI',proof).strip())
    need(commit_utc<race_start,'proof commit after race start')

def load_source_at_commit(sha,path):
    need(path.startswith('e2e_validation/snapshots/') and '..' not in path,'unsafe snapshot path')
    raw=git_text('show',sha+':'+path)
    return json.loads(raw)

def local_path(prefix,p):
    need(isinstance(p,str) and p.startswith(prefix) and '..' not in p and not p.startswith('/'),'unsafe referenced artifact '+repr(p))
    q=ROOT/'docs'/p
    need(q.is_file(),'report artifact missing '+str(q))
    return q

def hashfile(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    manifest=Path(sys.argv[1]) if len(sys.argv)>1 else TEMPLATE
    need(manifest.is_file(),'revision manifest absent')
    policy=load(POLICY)
    need(policy['allow_prestart_canonical_replacement'] is True and policy['no_replacement_after_post'] is True,
         'official policy not enabled')
    root=load(INDEX)
    prevlog=load(LOG) if LOG.exists() else {'schema_version':1,'policy_id':policy['policy_id'],'revisions':[]}
    need(prevlog.get('schema_version')==1 and isinstance(prevlog.get('revisions'),list),'revision journal invalid')
    audit=load(manifest)
    need(audit.get('original_v310_immutable') is True,'input must preserve historical evidence')
    rows=audit.get('races')
    need(isinstance(rows,list) and rows,'no approved newer predictions')
    seen=set();revisions=[]
    for ref in rows:
        slug=ref['race_id']
        need(slug not in seen,'duplicate race in revision manifest '+slug);seen.add(slug)
        match=[r for r in root['races'] if r.get('id')==slug]
        need(len(match)==1,'exactly one current official race entry required '+slug)
        old=match[0]
        need(old['status']=='predicted' and old.get('scope')=='jra-main' and not any(k in old for k in ('result','review','performance','settlements')),
            'race is completed or otherwise ineligible for prereace update '+slug)
        need(ref['prompt_version']=='v3.11','supported validated new version must be v3.11')
        pred_path=ref['prediction_path']
        need(pred_path.startswith('e2e_validation/predictions/'+slug+'/') and '..' not in pred_path,'invalid new prediction source')
        pred=load(pred_path)
        ctx=pred['race_context']
        race_start=utc_time(ctx['start_at'])
        need(utc_now()<race_start,'race post passed; no modifications allowed '+slug)
        need(ctx['date']==old['date'] and ctx['venue']==old['venue'] and ctx['race_name']==old['race'],
             'race identity/context mismatch '+slug)
        need(pred['race_id']==slug and pred['prompt_version']=='v3.11' and pred['stage']=='formal_prestart',
             'new prediction must be a sealed formal v3.11 original '+slug)
        need(pred['proof_commit']==ref['proof_commit'],'proof mismatch '+slug)
        frozen=utc_time(pred['final_bets_fixed_at'])
        need(frozen<race_start and frozen>utc_time(old['final_bets_fixed_at']),'new freeze must postdate previous and precede post '+slug)
        need(utc_time(pred['step1_fixed_at'])<=frozen,'STEP1 not fixed before purchase '+slug)
        need(pred['purchase_budget_yen']==6000 and pred['total_stake_yen']<=6000,'stake cap exceeded '+slug)
        need(pred['market_quote_audit']['verified']>0,'no independently sourced odds '+slug)
        check_proof(ref['snapshot_path'],ref['proof_commit'],pred,race_start)
        html=local_path('reports/',ref['report'])
        pdf=local_path('pdfs/',ref['pdf'])
        need(ref['report'].endswith('-v311.html') and ref['pdf'].endswith('-v311.pdf'),
             'not the audited v3.11 revision reports')
        with fitz.open(pdf) as doc:
            count=len(doc)
        need(count==ref['pdf_pages'] and count>=ctx['sale_field_size']+8,'rendered PDF page count mismatch')
        subprocess.run([sys.executable,'.github/scripts/validate-jra-pdf-content-v311.py',
                '--html',str(html),'--pdf',str(pdf),'--prediction',pred_path],check=True)
        marks={col:next((f"{r['horse_number']} {r['horse_name']}" for r in pred['step1_ranking'] if r['mark']==mark),None)
               for col,mark in [('win','◎'),('second','○'),('third','▲')]}
        need(all(marks.values()),'unsealed or incomplete marks '+slug)
        # A replacement changes the ONE public source of truth. Every previous original
        # remains addressable through immutable historical artifacts and this audit journal.
        fresh=copy.deepcopy(old)
        fresh.update(prompt_version='v3.11',report=ref['report'],pdf=ref['pdf'],
            pdf_mode='full',full_report_pages=count,field_size=ctx['sale_field_size'],
            marks=marks,bets=[b['type']+' '+'-'.join(map(str,b['selection'])) for b in pred['final_bets']],
            purchase_decision=pred['purchase_decision'],purchase_reason_code=pred['purchase_reason_code'],
            total_stake_yen=pred['total_stake_yen'],final_bets=pred['final_bets'],
            final_bets_fixed_at=pred['final_bets_fixed_at'],step1_fixed_at=pred['step1_fixed_at'],
            e2e_prediction=pred_path,proof_commit=pred['proof_commit'],purchase_budget_yen=6000)
        if fresh==old:
            print('CURRENT_ALREADY_LATEST',slug);continue
        need(not any(z.get('race_id')==slug and z.get('new',{}).get('proof_commit')==ref['proof_commit']
                     for z in prevlog['revisions']),'revision journal replay/double-add '+slug)
        revisions.append({'race_id':slug,'old':copy.deepcopy(old),'new':fresh,
            'prior_prediction_preserved':old.get('e2e_prediction'),'old_pdf_preserved':old.get('pdf'),
            'new_pdf_sha256':hashfile(pdf),'new_html_sha256':hashfile(html)})
    need(revisions,'no new revisions eligible; refusing an empty publication commit')
    # Recheck cutoff just before writing anything. All revisions share this transaction.
    for x in revisions:
        ref=next(z for z in rows if z['race_id']==x['race_id'])
        need(utc_now()<utc_time(load(ref['prediction_path'])['race_context']['start_at']),
             'race started while validation was running '+x['race_id'])
    for x in revisions:
        idx=next(i for i,z in enumerate(root['races']) if z['id']==x['race_id'])
        need(root['races'][idx]==x['old'],'inconsistent baseline prior to write')
        root['races'][idx]=x['new']
        prevlog['revisions'].append({'race_id':x['race_id'],
          'promoted_at_utc':utc_now().isoformat(),
          'old_canonical':x['old'],
          'new_canonical':{
             'prompt_version':x['new']['prompt_version'],
             'report':x['new']['report'],'pdf':x['new']['pdf'],
             'e2e_prediction':x['new']['e2e_prediction'],
             'proof_commit':x['new']['proof_commit'],
             'final_bets_fixed_at':x['new']['final_bets_fixed_at']},
          'pdf_sha256':x['new_pdf_sha256'],'html_sha256':x['new_html_sha256'],
          'immutable_prior_prediction':x['prior_prediction_preserved'],
          'immutable_prior_pdf':x['old_pdf_preserved']})
    root['updated_at']=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='milliseconds')
    INDEX.write_text(json.dumps(root,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    LOG.write_text(json.dumps(prevlog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('JRA_CANONICAL_REVISED',[(x['race_id'],x['new']['prompt_version'],x['new']['pdf']) for x in revisions])

if __name__=='__main__':
    try:main()
    except Exception as e:print('JRA_PROMOTION_BLOCKER:',str(e),file=sys.stderr);sys.exit(1)
