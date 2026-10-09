import fs from 'node:fs';
import path from 'node:path';
const root=process.cwd();
const policy=JSON.parse(fs.readFileSync(path.join(root,'docs/data/bet_type_coverage_policy_v1.json'),'utf8'));
const names=[...policy.race_local_types,...policy.cross_race_types];
const status=new Set(policy.statuses);
const errors=[],checks=[];
const base=path.join(root,'e2e_validation','predictions');
if(fs.existsSync(base)){
 for(const race of fs.readdirSync(base,{withFileTypes:true})){
  if(!race.isDirectory()) continue;
  const folder=path.join(base,race.name);
  for(const name of fs.readdirSync(folder)){
   if(!name.endsWith('.json')) continue;
   const filename=path.join(folder,name);
   let data;
   try{data=JSON.parse(fs.readFileSync(filename,'utf8'));}catch(e){errors.push(filename+': malformed JSON '+e.message);continue;}
   if(!/^v3\.[3-9](?:$|\.)|^v[4-9]\./.test(String(data.prompt_version||''))) continue;
   checks.push(path.relative(root,filename));
   const entries=data.bet_type_evaluations;
   if(!Array.isArray(entries)||entries.length!==names.length){errors.push(filename+': exactly '+names.length+' bet_type_evaluations required');continue;}
   const got=new Set();
   for(const e of entries){
    if(!e||typeof e!=='object'){errors.push(filename+': invalid row');continue;}
    if(got.has(e.type)) errors.push(filename+': duplicated type '+e.type);
    got.add(e.type);
    for(const field of policy.required_evaluation_fields) if(!(field in e))errors.push(filename+': '+e.type+' missing '+field);
    if(!status.has(e.status))errors.push(filename+': '+e.type+' invalid status '+e.status);
    if(e.status==='evaluated'){
     if(e.type==='WIN5')errors.push(filename+': WIN5 lacks confirmed pre-race fixed odds; use an appropriate separate status');
     if(!e.candidate||!e.source_url||!e.observed_at||!e.assessed_at||!e.probability_method)errors.push(filename+': '+e.type+' evaluated without candidate/source/timestamps/model');
     if(!(typeof e.market_odds==='number'&&e.market_odds>1 || Array.isArray(e.market_odds)&&e.market_odds.length===2&&e.market_odds.every(v=>typeof v==='number'&&v>1)))errors.push(filename+': '+e.type+' invalid market_odds');
     if(typeof e.probability!=='number'||e.probability<0||e.probability>1)errors.push(filename+': '+e.type+' invalid probability');
    } else {
     if(typeof e.reason!=='string'||!e.reason.trim())errors.push(filename+': '+e.type+' missing non-evaluated reason');
     if(e.status==='unpriced'&&e.ev_multiple!==null)errors.push(filename+': '+e.type+' unpriced requires ev_multiple=null');
    }
   }
   for(const required of names)if(!got.has(required))errors.push(filename+': missing type '+required);
   if(!['complete','incomplete'].includes(data.market_coverage_status))errors.push(filename+': market_coverage_status must be complete/incomplete');
   if(!data.market_coverage_snapshot_at)errors.push(filename+': missing market_coverage_snapshot_at');
   const unevaluatedLocal=entries.filter(e=>policy.race_local_types.includes(e.type)&&e.status!=='evaluated'&&e.status!=='not_offered');
   if(data.market_coverage_status==='complete'&&unevaluatedLocal.length)errors.push(filename+': marked complete although local ticket types lack coverage');
   const finalBets=Array.isArray(data.final_bets)?data.final_bets:[];
   for(const bet of finalBets){
    const row=entries.find(e=>e.type===bet.type);
    if(!row||row.status!=='evaluated')errors.push(filename+': final_bets contains unpriced/unassessed type '+bet.type);
   }
  }
 }
}
if(errors.length){console.error('Bet-type coverage validation FAILED:',errors.join('\n- '));process.exit(1);}
console.log('Bet-type coverage OK: '+checks.length+' v3.3+ predictions checked; '+names.length+' mandatory types');
