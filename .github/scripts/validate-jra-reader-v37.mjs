import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';

const read=(p)=>fs.readFileSync(p,'utf8');
const latest=JSON.parse(read('docs/data/latest_prompt.json'));
const history=JSON.parse(read('docs/data/prompt_history.json'));
const manifest=JSON.parse(read('e2e_validation/manifests/v3.7.json'));
const promptPath='競馬予想_完全版プロンプト_v3.7.txt';
const prompt=read(promptPath);
const policy=JSON.parse(read('docs/data/jra_pdf_layout_policy_v1.json'));
const css=fs.readFileSync('docs/assets/jra-pdf-reader-v1.css');
const errors=[];
if(!['v3.7','v3.8','v3.9','v3.10'].includes(latest.version)||(latest.version==='v3.7'&&latest.path!==promptPath)) errors.push('latest pointer is not v3.7');
if(!history.entries.some(x=>x.version==='v3.7'&&x.path===promptPath)) errors.push('v3.7 history missing');
if(manifest.prompt_version!=='v3.7'||manifest.components.length!==15) errors.push('unexpected manifest schema/component count');
for(let i=0;i<=6;i++) if(!prompt.includes('[LAY-0'+i+']')) errors.push('missing [LAY-0'+i+']');
for(const item of ['WIN5','v3.6','A4','1頭','CSS','PDF','GitHub','WeasyPrint','validator'].filter(x=>x!=='validator')){
 if(!prompt.includes(item))errors.push('missing rule marker '+item);
}
if(!prompt.includes('validate-jra-pdf-layout.py'))errors.push('validator not referenced');
const digest=createHash('sha256').update(css).digest('hex');
if(digest!==policy.style_sha256) errors.push('CSS fingerprint differs from approved policy');
if(policy.layout_id!=='jra-reader-v1'||policy.effective_jra_race_date_from!=='2026-10-11')errors.push('layout applicability was changed');
if(manifest.components.at(-1)?.path!==promptPath)errors.push('v3.7 prompt must be last manifest component');
for(const component of manifest.components){
 if(!fs.existsSync(component.path)){errors.push('missing '+component.path);continue;}
 const actual=execFileSync('git',['hash-object',component.path],{encoding:'utf8'}).trim();
 if(actual!==component.git_blob_sha)errors.push('SHA mismatch '+component.path);
}
if(errors.length){console.error('v3.7 PDF layout contract INVALID\n- '+errors.join('\n- '));process.exit(1);}
console.log('PASS v3.7: 15 SHA-pinned components, canonical CSS and fail-closed PDF rules');
