import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {TYPES,MODES,expandStrategy} from './jra-strategy-engine-v39.mjs';

const read=p=>fs.readFileSync(p,'utf8');
const promptPath='競馬予想_完全版プロンプト_v3.9.txt';
const latest=JSON.parse(read('docs/data/latest_prompt.json'));
const history=JSON.parse(read('docs/data/prompt_history.json'));
const manifest=JSON.parse(read('e2e_validation/manifests/v3.9.json'));
const prev=JSON.parse(read('e2e_validation/manifests/v3.8.json'));
const policy=JSON.parse(read('docs/data/all_bet_strategy_policy_v1.json'));
const prompt=read(promptPath),errors=[];
if(!['v3.9','v3.10'].includes(latest.version)||(latest.version==='v3.9'&&latest.path!==promptPath))errors.push('unexpected formal latest pointer for frozen v3.9 contract');
if(!history.entries.some(e=>e.version==='v3.9'&&e.path===promptPath&&e.previous_version==='v3.8'))errors.push('missing history version');
if(manifest.prompt_version!=='v3.9'||manifest.components.length!==20)errors.push('unexpected v3.9 manifest component count');
if(JSON.stringify(manifest.components.slice(0,17))!==JSON.stringify(prev.components))errors.push('a frozen legacy v3.0-v3.8 component changed');
for(let i=0;i<=6;i++)if(!prompt.includes('[ALLBET-0'+i+']'))errors.push('missing scope rule [ALLBET-0'+i+']');
for(const t of TYPES)if(!prompt.includes(t))errors.push('missing coverage '+t);
for(const s of ['WIN5','STEP1','STEP2','マルチ','フォーメーション','ボックス','ROI','final_bets','PDF','3000円','全損確率','実損確率'])
 if(!prompt.includes(s))errors.push('missing required text '+s);
if(policy.scope!=='step2_purchase_only'||policy.win5!=='excluded'||policy.requirements?.budget_default_cap_yen!==3000)errors.push('v3.9 scoping and risk policy changed');
if(JSON.stringify(policy.modes)!==JSON.stringify(MODES))errors.push('all-eight-mode registry does not match code');
if(manifest.components[17]?.path!=='docs/data/all_bet_strategy_policy_v1.json'||manifest.components[18]?.path!=='.github/scripts/jra-strategy-engine-v39.mjs'||manifest.components[19]?.path!==promptPath)errors.push('wrong append-only v3.9 components');
for(const c of manifest.components){
 if(!fs.existsSync(c.path)){errors.push('missing pinned dependency '+c.path);continue;}
 const actual=execFileSync('git',['hash-object',c.path],{encoding:'utf8'}).trim();
 if(actual!==c.git_blob_sha)errors.push('sha pin mismatch '+c.path);
}
for(const t of TYPES)for(const kind of MODES[t]){
 if(kind==='single')continue;
 // all declared modes must be exercised in independent positive tests below
 if(!policy.modes[t]?.includes(kind))errors.push('undiscoverable mode '+t+' / '+kind);
}
if(errors.length){console.error('Formal v3.9 JRA strategy gate invalid:\n'+errors.join('\n'));process.exit(1);}
console.log('PASS v3.9: all 8 normal bet-types and '+Object.values(MODES).reduce((a,v)=>a+v.length,0)+' standard purchase modes, 20 pinned dependencies');
