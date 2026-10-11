import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const read=p=>fs.readFileSync(p,'utf8');
const promptPath='競馬予想_完全版プロンプト_v3.8.txt';
const latest=JSON.parse(read('docs/data/latest_prompt.json'));
const history=JSON.parse(read('docs/data/prompt_history.json'));
const manifest=JSON.parse(read('e2e_validation/manifests/v3.8.json'));
const legacy=JSON.parse(read('e2e_validation/manifests/v3.7.json'));
const policy=JSON.parse(read('docs/data/ticket_portfolio_policy_v1.json'));
const prompt=read(promptPath),errors=[];
if(!['v3.8','v3.9','v3.10','v3.11'].includes(latest.version)||(latest.version==='v3.8'&&latest.path!==promptPath))errors.push('unexpected latest pointer for v3.8 historical contract');
if(!history.entries.some(e=>e.version==='v3.8'&&e.path===promptPath&&e.previous_version==='v3.7'))errors.push('missing formal v3.8 history');
if(manifest.prompt_version!=='v3.8'||manifest.components.length!==17)errors.push('unexpected manifest version or component count');
if(JSON.stringify(manifest.components.slice(0,15))!==JSON.stringify(legacy.components))errors.push('v3.0-v3.7 frozen prompt/CSS dependencies changed');
for(let i=0;i<=6;i++)if(!prompt.includes('[PORT-0'+i+']'))errors.push('missing purchase strategy rule PORT-0'+i);
for(const s of ['STEP1','WIN5','final_bets','2頭軸マルチ','ボックス','フォーメーション','期待回収率','PDF','v3.7','3,000円','買う/見送り'].filter(x=>x!=='買う/見送り'))
 if(!prompt.includes(s))errors.push('missing scope/risk/strategy marker '+s);
if(policy.scope!=='step2_purchase_only'||policy.rules?.budget_default_cap_yen!==3000)errors.push('policy no longer purchase-only or default cap changed');
if(manifest.components[15]?.path!=='docs/data/ticket_portfolio_policy_v1.json'||manifest.components[16]?.path!==promptPath)errors.push('manifest tail not strategy policy/prompt');
for(const component of manifest.components){
 if(!fs.existsSync(component.path)){errors.push('component missing '+component.path);continue;}
 const actual=execFileSync('git',['hash-object',component.path],{encoding:'utf8'}).trim();
 if(actual!==component.git_blob_sha)errors.push('Git blob fingerprint mismatch '+component.path);
}
if(errors.length){console.error('v3.8 strategy prompt contract INVALID:\n'+errors.join('\n'));process.exit(1);}
console.log('PASS v3.8: v3.0-v3.7 pinned components untouched; purchase-only multi-bet layer with 17 SHA-verified dependencies');
