// Audit appendix-only v3.12 readiness without permitting draft to replace canonical v3.11.
// This is NOT a release signal. A separate migration of version-specific v3.11 CI is required.
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const old=read('e2e_validation/manifests/v3.11.json');
const next=read('e2e_validation/manifests/v3.12.json');
const latest=read('docs/data/latest_prompt.json');
const errors=[];
if(next.prompt_version!=='v3.12')errors.push('v3.12 manifest version missing');
const oldPart=next.components.slice(0,old.components.length);
if(JSON.stringify(old.components)!==JSON.stringify(oldPart))errors.push('v3.11 component list changed or reordered');
if(next.components.length<old.components.length+12)errors.push('missing v3.12 required additions');
if(!['v3.11','v3.12'].includes(latest.version))errors.push('unexpected canonical pointer while v3.12 staged');
if(latest.version==='v3.12'&&latest.path!=='競馬予想_完全版プロンプト_v3.12.txt')
 errors.push('v3.12 canonical prompt mismatched path');
for(const x of next.components){
 if(!fs.existsSync(x.path)){errors.push('file missing: '+x.path);continue;}
 const hash=execFileSync('git',['hash-object',x.path],{encoding:'utf8'}).trim();
 if(hash!==x.git_blob_sha)errors.push('git blob SHA mismatch '+x.path);
}
for(const needle of ['[ODDS-12]','[SET-12]','[PDF-12]','[SAFE-12]']){
 if(!fs.readFileSync('競馬予想_完全版プロンプト_v3.12.txt','utf8').includes(needle))
  errors.push('prompt lacks '+needle);
}
if(errors.length){console.error('V312 STAGING BLOCKER:\n'+errors.join('\n'));process.exit(1);}
console.log('PASS: all '+next.components.length+' SHA pins verified, v3.11 unchanged, canonical pointer '+latest.version);
