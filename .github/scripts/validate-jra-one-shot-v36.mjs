import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';

const root=process.cwd();
const latest=JSON.parse(fs.readFileSync('docs/data/latest_prompt.json','utf8'));
const v36='競馬予想_完全版プロンプト_v3.6.txt';
const prompt=fs.readFileSync(v36,'utf8');
const manifest=JSON.parse(fs.readFileSync('e2e_validation/manifests/v3.6.json','utf8'));
const history=JSON.parse(fs.readFileSync('docs/data/prompt_history.json','utf8'));
const issues=[];
const requireText=(name,needle)=>{if(!prompt.includes(needle))issues.push(name+': missing '+needle);};
for(let i=0;i<=6;i++)requireText('run contract',`[RUN-0${i}]`);
for(const type of ['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'])requireText('8-ticket types',type);
for(const phrase of ['WIN5','発走前','STEP1','STEP2','final_bets','proof_commit','HTML','PDF','Git blob SHA','買う/見送り','snapshot','旧PDF'].filter(x=>x!=='snapshot'))requireText('run proof and integrity',phrase);
if(!prompt.includes('一切予想しない')&&!prompt.includes('予想しない'))issues.push('WIN5 exclusion must be explicit');
if(prompt.length>5200)issues.push('v3.6 one-shot delta exceeds 5200 characters: avoid re-copying v3.0-v3.5');
if(!Array.isArray(manifest.components)||manifest.components.length<12)issues.push('v3.6 manifest must preserve all v3.5 components');
else for(const part of manifest.components){
  const p=path.join(root,part.path);
  if(!fs.existsSync(p)){issues.push('missing component '+part.path);continue;}
  const actual=execFileSync('git',['hash-object',part.path],{cwd:root,encoding:'utf8'}).trim();
  if(actual!==part.git_blob_sha)issues.push('component SHA mismatch '+part.path);
}
if(manifest.components?.at(-1)?.path!==v36)issues.push('last manifest component must be v3.6');
if(manifest.prompt_version!=='v3.6')issues.push('manifest wrong version');
if(!['v3.5','v3.6','v3.7'].includes(latest.version))issues.push('unexpected latest pointer '+latest.version);
if(latest.version==='v3.6'){
  if(latest.path!==v36)issues.push('latest pointer does not target canonical v3.6');
  const h=history.entries?.find(x=>x.version==='v3.6');
  if(!h||h.path!==v36)issues.push('v3.6 formal history missing');
}
if(issues.length){console.error('One-shot JRA contract INVALID:\n- '+issues.join('\n- '));process.exit(1);}
console.log(`v3.6 one-shot JRA contract verified: ${prompt.length} chars, 8 local tickets, no WIN5, proof-first, ${manifest.components.length} pinned components`);
