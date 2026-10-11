import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const latest=read('docs/data/latest_prompt.json'),hist=read('docs/data/prompt_history.json');
const old=read('e2e_validation/manifests/v3.10.json');
const manifest=read('e2e_validation/manifests/v3.11.json');
const p='競馬予想_完全版プロンプト_v3.11.txt';
const prompt=fs.readFileSync(p,'utf8'),errors=[];
if(latest.version!=='v3.11'||latest.path!==p)errors.push('latest pointer must resolve v3.11');
if(manifest.prompt_version!=='v3.11')errors.push('manifest version mismatch');
if(JSON.stringify(manifest.components.slice(0,old.components.length))!==JSON.stringify(old.components))
  errors.push('frozen v3.10 SHA pins changed');
const added=manifest.components.slice(old.components.length);
if(added.length<9)errors.push('required v3.11 additive components not pinned');
const mandatory=['docs/data/jra_balanced_portfolio_policy_v1.json',
 '.github/scripts/jra-balanced-optimizer-v311.mjs',
 '.github/scripts/jra-prestart-pipeline-v311.mjs',
 '.github/scripts/validate-jra-portfolio-v311.mjs',
 '.github/scripts/jra-render-live-v311.py',
 '.github/scripts/validate-jra-pdf-content-v311.py',
 '.github/scripts/test-jra-balanced-v311.mjs',
 '.github/scripts/test-jra-prestart-pipeline-v311.mjs',p];
for(const x of mandatory)if(!added.some(e=>e.path===x))errors.push('missing pinned component '+x);
for(const {path,git_blob_sha} of manifest.components){
 if(!fs.existsSync(path)){errors.push('missing '+path);continue;}
 if(execFileSync('git',['hash-object',path],{encoding:'utf8'}).trim()!==git_blob_sha)
   errors.push('SHA pin mismatch '+path);
}
if(!hist.entries.some(e=>e.version==='v3.11'&&e.previous_version==='v3.10'&&e.path===p))errors.push('history entry missing');
for(const marker of ['[BAL-00]','[BAL-01]','[BAL-02]','[BAL-03]','[BAL-04]','[BAL-05]',
 'STEP1','6,000円','集合的中率','実損確率','ページ数','上限なし','不採用','proof_commit'])
 if(!prompt.includes(marker))errors.push('prompt missing '+marker);
const policy=read('docs/data/jra_balanced_portfolio_policy_v1.json');
if(policy.effective_prompt_version!=='v3.11'||policy.budget_yen!==6000||
 policy.outputs.max_pdf_pages!==null||policy.outputs.auto_paginate_all_candidates!==true)
 errors.push('unlimited PDF pagination and 6000 yen policy mismatch');
if(errors.length){console.error('BLOCKED v3.11 canonical prompt:\n'+errors.join('\n'));process.exit(1);}
console.log('PASS: v3.11 is additive to immutable prior 23 SHA pins, dynamic PDF is unlimited, STEP1 preserved');
