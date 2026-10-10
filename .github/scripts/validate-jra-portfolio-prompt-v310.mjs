import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const read=p=>fs.readFileSync(p,'utf8');
const latest=JSON.parse(read('docs/data/latest_prompt.json'));
const hist=JSON.parse(read('docs/data/prompt_history.json'));
const current=JSON.parse(read('e2e_validation/manifests/v3.10.json'));
const legacy=JSON.parse(read('e2e_validation/manifests/v3.9.json'));
const policy=JSON.parse(read('docs/data/jra_portfolio_6000_policy_v1.json'));
const promptPath='競馬予想_完全版プロンプト_v3.10.txt';
const prompt=read(promptPath),errors=[];
if(latest.version!=='v3.10'||latest.path!==promptPath)errors.push('latest prompt is not canonical v3.10');
if(!hist.entries.some(x=>x.version==='v3.10'&&x.path===promptPath&&x.previous_version==='v3.9'))errors.push('missing v3.10 history entry');
if(current.prompt_version!=='v3.10'||current.components.length!==23)errors.push('expected 23 SHA-pinned components');
if(JSON.stringify(current.components.slice(0,20))!==JSON.stringify(legacy.components))errors.push('v3.0-v3.9 canonical components were changed');
if(current.components[20]?.path!=='docs/data/jra_portfolio_6000_policy_v1.json'||
 current.components[21]?.path!=='.github/scripts/jra-portfolio-optimizer-v310.mjs'||
 current.components[22]?.path!==promptPath)errors.push('v3.10 new component order invalid');
for(let i=0;i<=6;i++)if(!prompt.includes('[OPT-0'+i+']'))errors.push('missing purchase-only rule [OPT-0'+i+']');
for(const marker of ['STEP1','WIN5','6,000円','期待純利益','ナップサック','複数券種','final_bets','proof_commit','PDF'])
 if(!prompt.includes(marker))errors.push('v3.10 contract marker missing '+marker);
if(policy.scope!=='step2_purchase_only'||policy.optimization?.budget_yen!==6000||
  policy.optimization?.per_line_stake_yen!==100||policy.optimization?.one_selected_strategy_only!==false||
  policy.optimization?.algorithm!=='exact_zero_one_knapsack_v1')errors.push('v3.10 portfolio defaults or scope drifted');
for(const part of current.components){
 if(!fs.existsSync(part.path)){errors.push('missing pinned '+part.path);continue;}
 const actual=execFileSync('git',['hash-object',part.path],{encoding:'utf8'}).trim();
 if(actual!==part.git_blob_sha)errors.push('Git SHA mismatch '+part.path);
}
if(errors.length){console.error('v3.10 portfolio prompt invalid:\n'+errors.join('\n'));process.exit(1);}
console.log('PASS v3.10: 6000 yen cross-type portfolio optimizer; prior 20 components byte-identical, purchase-only');
