// Synthetic deterministic fixtures ONLY; never treated as real race data or actual odds.
import assert from 'node:assert/strict';
import {TYPES,MODES,expandStrategy,ticketKey} from './jra-strategy-engine-v39.mjs';
import {fullFieldOutcomes,assemble} from './jra-prestart-pipeline-v310.mjs';
import {validateV310} from './validate-jra-portfolio-v310.mjs';
const deep=x=>JSON.parse(JSON.stringify(x));
const fixed='2030-10-11T08:00:00+09:00',planAt='2030-10-11T08:01:00+09:00';
const quoteAt='2030-10-11T08:05:00+09:00',freeze='2030-10-11T08:10:00+09:00';
const synthetic='https://example.org/synthetic-only-not-a-real-market';
const keys={
 単勝:{selection:[1]},複勝:{selection:[1]},枠連:{selection:[1,2]},
 馬連:{selection:[1,2]},馬単:{selection:[1,2]},ワイド:{selection:[1,2]},
 三連複:{selection:[1,2,3]},三連単:{selection:[1,2,3]}
};
function fixture(){
 const runners=Array.from({length:9},(_,i)=>({horse_number:i+1,horse_name:'TEST'+(i+1),
  mark:i===0?'◎':i===1?'○':i===2?'▲':'△',
  win_probability:1/9,factor_grades:Array(9).fill('A'),
  evidence:'Synthetic independently fixed nine factor grades and all horse evidence',
  source_url:synthetic}));
 const strategies=TYPES.map((type,i)=>({strategy_id:'S'+String(i+1).padStart(2,'0'),type,strategy_kind:'single',
  definition:keys[type],ability_reason:'Independent pre-price rank and track condition evidence',
  risk_reason:'No historic calibration; conditional ordering scenario risk remains',
  decision_reason:'Synthetic prequote representative analysis'}));
 const additional=[
  {type:'馬連',strategy_kind:'key_wheel',definition:{key:1,partners:[2,3,4]}},
  {type:'三連複',strategy_kind:'two_key_wheel',definition:{axes:[1,2],partners:[3,4]}},
  {type:'三連単',strategy_kind:'two_key_multi',definition:{axes:[1,2],partners:[3,4]}},
  {type:'ワイド',strategy_kind:'box',definition:{horses:[1,2,3]}}];
 for(const [i,s] of additional.entries())strategies.push({...s,strategy_id:'SX'+i,
  ability_reason:'Synthetic prequote ordering',risk_reason:'Sensitive to model assumptions',decision_reason:'synthetic combination portfolio'});
 const used=new Set(strategies.map(s=>s.type+':'+s.strategy_kind));
 const mode_exclusions=TYPES.flatMap(type=>MODES[type].filter(mode=>!used.has(type+':'+mode))
  .map(mode=>({type,mode,reason:'Not in bounded predetermined synthetic shortlist',
   evidence:'Pre-price ranked horse group intentionally excludes this mode'})));
 const prices={単勝:30,複勝:7,枠連:75,馬連:110,馬単:230,ワイド:35,三連複:390,三連単:1850};
 const odds=new Map();
 for(const s of strategies)for(const l of expandStrategy(s.type,s.strategy_kind,s.definition)){
  const key=ticketKey(l.type,l.selection);
  if(!odds.has(key))odds.set(key,{race_id:'2030-10-11-test-race',type:l.type,selection:l.selection,
   market_selection_id:key,market_odds:prices[l.type],observed_at:quoteAt,
   source_url:synthetic,source_capture_sha256:'a'.repeat(64),quote_verified:true});
 }
 return {prompt_version:'v3.10',race_id:'2030-10-11-test-race',
  race_context:{venue:'東京',race_no:11,start_at:'2030-10-11T15:45:00+09:00',sale_field_size:9,
   place_paid_positions:3,offered_types:TYPES,official_source_url:synthetic},
  frame_map:Object.fromEntries(runners.map((r,i)=>[r.horse_number,Math.min(i+1,8)])),
  step1:{fixed_at:fixed,primary_source:synthetic,no_odds_used_to_change_marks:true,calibrated:false,runners},
  scenario_factors:{
   low:{assumption:'Synthetic low pace favor affects runner 2',by_horse:Object.fromEntries(runners.map(r=>[r.horse_number,r.horse_number===2?1.15:1]))},
   high:{assumption:'Synthetic high pace favor affects runner 1',by_horse:Object.fromEntries(runners.map(r=>[r.horse_number,r.horse_number===1?1.2:1]))}},
  strategy_plan_fixed_at:planAt,strategies,mode_exclusions,market_quotes:[...odds.values()],
  input_source:'synthetic test only'};
}
const check=(name,input,part)=>{assert.throws(()=>assemble(input,freeze,'a'.repeat(40)),new RegExp(part),name);console.log('PASS rejected '+name)};
const raw=fixture();
const dists=fullFieldOutcomes(raw.step1.runners,raw.scenario_factors);
for(const sc of ['low','central','high']){
 assert.equal(dists[sc].length,9*8*7);
 assert(Math.abs(dists[sc].reduce((a,b)=>a+b.probability,0)-1)<1e-9);
}
for(const r of raw.step1.runners){
 const p=dists.central.filter(o=>o.finish[0]===r.horse_number).reduce((a,b)=>a+b.probability,0);
 assert(Math.abs(p-r.win_probability)<1e-9);
}
const sealed=assemble(raw,freeze,'a'.repeat(40));
assert.deepEqual(validateV310(sealed),[]);
assert.equal(sealed.purchase_budget_yen,6000);
assert(sealed.final_bets.length>1,'multiple strategies may be selected');
assert(sealed.final_bets.length*100===sealed.total_stake_yen);
assert(sealed.total_stake_yen<=6000);
assert.equal(sealed.strategy_coverage_audit.length,8);
assert.equal(sealed.market_quote_audit.unused.length,0);
const pending=assemble(raw,freeze);
assert.equal(pending.proof_commit,null);
assert.equal(pending.stage,'pending_git_proof');
console.log('PASS 9-runner three-scenario complete universe; 8-type combinations; exact portfolio; pending/sealed proof');
let p=deep(raw);p.market_quotes=p.market_quotes.filter(x=>x.type!=='三連単');const partial=assemble(p,freeze,'a'.repeat(40));
assert.equal(partial.strategy_coverage_audit.length,8);
assert(partial.market_quote_audit.missing_individual_lines>0);
assert.deepEqual(validateV310(partial),[]);
console.log('PASS partial market quotes do not stop independent eligible ticket processing');
p=deep(raw);p.market_quotes=[];check('no live price is not a value pass',p,'no independently verified exact odds');
p=deep(raw);p.market_quotes[0].market_odds=null;check('no invented odds',p,'quote unverifiable');
p=deep(raw);p.market_quotes[0].observed_at='2030-10-11T16:00:00+09:00';check('late price',p,'quote after freeze');
p=deep(raw);p.market_quotes[0].market_selection_id='単勝:[9]';check('selection precision',p,'market key');
p=deep(raw);p.market_quotes[0].source_capture_sha256=null;check('missing page capture hash',p,'capture content');
p=deep(raw);p.market_quotes.push({...p.market_quotes[0],market_odds:2.5});check('same ticket price conflict',p,'conflicting price');
p=deep(raw);p.step1.runners[0].win_probability=.3;check('no model from arbitrary probabilities',p,'unnormalized');
p=deep(raw);p.step1.no_odds_used_to_change_marks=false;check('independence of STEP1',p,'independence');
p=deep(raw);p.mode_exclusions.pop();check('no forgotten mode',p,'missing mode audit');
p=deep(raw);p.step1.runners[0].factor_grades.pop();check('nine axes for every horse',p,'all nine grades');
assert.throws(()=>assemble(raw,'2030-10-11T16:00:00+09:00'),'no post-start freezing');
console.log('PASS JRA v3.10 new pipeline tests finished');
