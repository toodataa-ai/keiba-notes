import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
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
   // Historical v3.6 prereace predictions use a documented compact evaluation
   // schema, not the newer status/candidate/assessed_at fields. Preserve the original
   // archived files byte-for-byte and validate the exact known Git blobs separately.
   const legacy=Object.freeze({
     'e2e_validation/predictions/2026-10-10-mimuro-stakes/v3.6-20261010-prestart.json':'05f803f17f9d07d03b7e8e9498ccfa345703874b',
     'e2e_validation/predictions/2026-10-10-saudi-arabia-royal-cup/v3.6-20261010-prestart.json':'1827c6244e3b5194e8f6c1fec7cae2b8b6082fca'
   });
   const relative=path.relative(root,filename).split(path.sep).join('/');
   if(data.prompt_version==='v3.6' && Object.hasOwn(legacy,relative)){
     checks.push(relative);
     const sha=execFileSync('git',['hash-object',relative],{encoding:'utf8'}).trim();
     if(sha!==legacy[relative]){errors.push(relative+': archived v3.6 Git blob differs from original');continue;}
     const rows=data.bet_type_evaluations;
     if(!Array.isArray(rows)||rows.length!==policy.race_local_types.length||
        new Set(rows.map(x=>x.type)).size!==policy.race_local_types.length||
        policy.race_local_types.some(type=>!rows.some(x=>x.type===type))){
       errors.push(relative+': compact historical eight-ticket-type ledger incomplete');continue;
     }
     const post=Date.parse(data.race_context?.start_at);
     for(const row of rows){
       const quote=Array.isArray(row.market_odds)?row.market_odds[0]:row.market_odds;
       const at=Date.parse(row.observed_at);
       if(!Array.isArray(row.best_selection)||row.best_selection.length===0||
         !(typeof quote==='number'&&quote>1)||!Number.isFinite(at)||
         !(at<post)||!row.source_url?.startsWith('https://')||
         !(typeof row.base_probability==='number'&&row.base_probability>=0&&row.base_probability<=1)||
         !(typeof row.base_ev==='number'&&Number.isFinite(row.base_ev))||
         Math.abs(row.base_ev-quote*row.base_probability)>0.0001 ||
         !Number.isInteger(row.generated)||!Number.isInteger(row.priced)||row.priced<1||row.generated<row.priced){
           errors.push(relative+': corrupted archived compact evaluation for '+row.type);
       }
     }
     const bets=data.final_bets||[];
     if(!Array.isArray(bets)||!bets.length||
        bets.some(b=>!rows.some(x=>x.type===b.type&&JSON.stringify(x.best_selection)===JSON.stringify(b.selection)&&
          Math.abs(x.market_odds-b.market_odds_at_decision)<1e-7))){
       errors.push(relative+': archived final_bets differ from compact priced evaluations');
     }
     const fixed=Date.parse(data.final_bets_fixed_at);
     if(!Number.isFinite(fixed)||fixed>=post)errors.push(relative+': archived prereace bet freeze is not before post');
     continue;
   }
   const match=/^v3\.(\d+)(?:$|[.-])/.exec(String(data.prompt_version||''));
   if(!(match&&Number(match[1])>=3)||/^v[4-9]\./.test(String(data.prompt_version||''))===false&&match===null)continue;
   checks.push(path.relative(root,filename));
   const is34=/^v3\.(?:[4-9]|[1-9][0-9]+)$|^v[4-9]\./.test(String(data.prompt_version||''));
   const requiredTypes=is34?policy.race_local_types:names;
   const entries=data.bet_type_evaluations;
   if(!Array.isArray(entries)||entries.length!==requiredTypes.length){errors.push(filename+': exactly '+requiredTypes.length+' bet_type_evaluations required');continue;}
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
   for(const required of requiredTypes)if(!got.has(required))errors.push(filename+': missing type '+required);
   if(is34&&got.has('WIN5')) errors.push(filename+': WIN5 explicitly excluded from v3.4+');
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
console.log('Bet-type coverage OK: '+checks.length+' predictions checked (v3.3: 9 historical types, v3.4+: 8 local types); WIN5 excluded from new predictions');
