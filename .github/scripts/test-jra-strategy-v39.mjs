import assert from 'node:assert/strict';
import {TYPES,MODES,expandStrategy,ticketKey,normalize,evaluateStrategy} from './jra-strategy-engine-v39.mjs';
import {validateV39} from './validate-jra-strategy-v39.mjs';
const source='https://example.org/synthetic-official-odds',at='2026-10-11T09:00:00+09:00',freeze='2026-10-11T09:05:00+09:00';
const cp=x=>JSON.parse(JSON.stringify(x));
const count=(type,mode,definition,expected)=>{const got=expandStrategy(type,mode,definition);assert.equal(got.length,expected,type+' '+mode);console.log('PASS '+type+' '+mode+' => '+expected)};
count('単勝','single',{selection:[1]},1);
count('単勝','multiple_singles',{horses:[1,2,3]},3);
count('複勝','multiple_singles',{horses:[1,2]},2);
count('枠連','single',{selection:[1,1]},1);
count('枠連','key_wheel',{key:1,partners:[1,2,3]},3);
count('枠連','box',{horses:[1,2,3]},3);
assert(!expandStrategy('枠連','box',{horses:[1,2]}).some(x=>x.selection[0]===x.selection[1]),'frame box must exclude doubled frame');
count('枠連','formation',{slots:[[1],[1,2]]},2);
count('馬連','key_wheel',{key:1,partners:[2,3,4]},3);
count('馬連','box',{horses:[1,2,3,4]},6);
count('馬連','formation',{slots:[[1,2],[2,3]]},3);
count('ワイド','key_wheel',{key:1,partners:[2,3]},2);
count('ワイド','box',{horses:[1,2,3]},3);
count('ワイド','formation',{slots:[[1,2],[2,3]]},3);
count('馬単','key_wheel_first',{key:1,partners:[2,3]},2);
count('馬単','key_wheel_second',{key:1,partners:[2,3]},2);
count('馬単','key_wheel_multi',{key:1,partners:[2,3]},4);
count('馬単','box',{horses:[1,2,3]},6);
count('馬単','formation',{slots:[[1,2],[2,3]]},3);
count('三連複','one_key_wheel',{key:1,partners:[2,3,4]},3);
count('三連複','two_key_wheel',{axes:[1,2],partners:[3,4]},2);
count('三連複','box',{horses:[1,2,3,4]},4);
count('三連複','formation',{slots:[[1],[2,3],[3,4]]},3);
count('三連単','one_key_fixed',{key:1,position:1,partners:[2,3,4]},6);
count('三連単','one_key_fixed',{key:1,position:2,partners:[2,3,4]},6);
count('三連単','one_key_fixed',{key:1,position:3,partners:[2,3,4]},6);
count('三連単','one_key_multi',{key:1,partners:[2,3,4]},18);
count('三連単','two_key_fixed',{axes:[1,2],positions:[1,3],partners:[3,4]},2);
count('三連単','two_key_multi',{axes:[1,2],partners:[3,4]},12);
count('三連単','box',{horses:[1,2,3,4]},24);
count('三連単','formation',{slots:[[1,2],[2,3],[3,4]]},4);
count('mixed','win_place_support',{horse:1},2);
assert.deepEqual(normalize('三連複',[3,1,2]),[1,2,3],'trio order does not matter');
const ordered=[{finish:[1,2,3],probability:.5},{finish:[2,1,3],probability:.5}];
const scenarios={low:ordered,central:ordered,high:ordered};
const frameMap={'1':1,'2':2,'3':3};
const race={sale_field_size:9,place_paid_positions:3};
const L=(type,selection,odds)=>({type,selection,stake_yen:100,market_odds:odds});
let met=evaluateStrategy([L('複勝',[1],2),L('複勝',[2],2)],scenarios,frameMap,race);
assert.equal(met.hit_probability_scenarios.central,1,'overlapping place wins must NOT sum to 2');
assert.equal(met.expected_payout_yen_scenarios.central,400,'simultaneously winning place tickets pay BOTH dividends');
assert.equal(met.roi_scenarios.central,2);
assert.equal(met.full_loss_probability_scenarios.central,0);
met=evaluateStrategy([L('馬連',[1,2],3),L('ワイド',[1,2],2.5)],scenarios,frameMap,race);
assert.equal(met.hit_probability_scenarios.central,1,'cross-ticket events correlated');
assert.equal(met.expected_payout_yen_scenarios.central,550,'winning different types are additive');
met=evaluateStrategy([L('単勝',[1],2),L('複勝',[1],[1.1,1.5])],scenarios,frameMap,race);
assert.equal(met.expected_payout_yen_scenarios.central,210,'single+place lower odds; win in half and place always');
assert.equal(met.loss_probability_scenarios.central,0.5,'winning place may still lose money overall');
// Explicit break-even calculation includes every losing line in the investment.
met=evaluateStrategy([L('三連単',[1,2,3],2),L('三連単',[2,1,3],2)],scenarios,frameMap,race);
assert.equal(met.hit_probability_scenarios.central,1);
assert.equal(met.roi_scenarios.central,1);
assert.equal(met.loss_probability_scenarios.central,0);
assert.equal(evaluateStrategy([L('馬連',[1,2],null)],scenarios,frameMap,race).roi_scenarios,null,'no fabricated odds');
assert.throws(()=>evaluateStrategy([L('馬連',[1,2],3),L('馬連',[2,1],3)],scenarios,frameMap,race),/duplicate/,'unordered re-entry prohibited');

function allOutcomes(n,scenario){
 const raw=[];
 for(let a=1;a<=n;a++)for(let b=1;b<=n;b++)for(let c=1;c<=n;c++){
  if(a===b||a===c||b===c)continue;
  const weight=1+(a===1&&scenario==='central'?.2:0)+(b===1&&scenario==='high'?.3:0);
  raw.push({finish:[a,b,c],probability:weight});
 }
 const sum=raw.reduce((s,x)=>s+x.probability,0);
 return raw.map(x=>({...x,probability:x.probability/sum}));
}
const n=9,distributions=Object.fromEntries(['low','central','high'].map(s=>[s,allOutcomes(n,s)]));
const slot=(type,selection,odds)=>{
 const k=ticketKey(type,selection);
 return {type,selection,stake_yen:100,market_odds:odds,source_url:source,observed_at:at,market_selection_id:k,quote_verified:true};
};
function strategy(){
 const type='馬連',strategy_kind='key_wheel',definition={key:1,partners:[2,3]},
 selections=expandStrategy(type,strategy_kind,definition);
 const lines=selections.map((x,i)=>slot(x.type,x.selection,[60,55][i]));
 const metrics=evaluateStrategy(lines,distributions,Object.fromEntries(Array.from({length:9},(_,i)=>[i+1,i+1===9?1:i+1])),{sale_field_size:9,place_paid_positions:3});
 return {strategy_id:'S01',type,strategy_kind,definition,generated_ticket_count:lines.length,lines,eligibility:'eligible',
   ability_reason:'Synthetic supported key and pace evidence before prices',risk_reason:'Three scenario downside reviewed',
   decision_reason:'Synthetic effective multi-line cost comparison',...metrics};
}
function sample(){
 const st=strategy(),represent=st.lines[0];
 const p=2/(9*8);
 const comparisons=TYPES.map(type=>type==='馬連'?({
  type,selection:represent.selection,source_url:source,observed_at:at,assessed_at:at,market_odds:represent.market_odds,
  probability_method:'Full-field conditional top3 model',
  probability_scenarios:{low:p,central:p,high:p},break_even_probability:1/represent.market_odds,
  ev_scenarios:{low:p*represent.market_odds,central:p*represent.market_odds,high:p*represent.market_odds},
  ability_reason:'synthetic',risk_reason:'synthetic risk',eligibility:'eligible',decision_reason:'synthetic research'
 }):({type,selection:type==='三連単'||type==='三連複'?[1,2,3]:['単勝','複勝'].includes(type)?[1]:[1,2],
  source_url:null,observed_at:null,assessed_at:at,market_odds:null,probability_method:null,probability_scenarios:null,
  break_even_probability:null,ev_scenarios:null,ability_reason:'candidate evidence',risk_reason:'no priced quotes',eligibility:'unpriced',decision_reason:'no quote'}));
 const rows=TYPES.map(type=>type==='馬連'?{
   type,status:'evaluated',candidate:{selection:represent.selection,kind:'horse_numbers',label:'1-2'},
   market_odds:represent.market_odds,source_url:source,observed_at:at,assessed_at:at,
   probability:p,probability_method:'Full-field conditional top3 model',ev_multiple:p*represent.market_odds,
   decision:'buy',reason:'Synthetic joint model'
 }:{type,status:'unpriced',candidate:null,market_odds:null,source_url:null,observed_at:null,assessed_at:at,
   probability:null,probability_method:null,ev_multiple:null,decision:'pass',reason:'Not quoted synthetic'});
 const search=TYPES.map(t=>({type:t,generated_count:1,priced_count:t==='馬連'?1:0,
   shortfall_reason:'Only one candidate price research available synthetic',
   price_shortfall_reason:'Other official prices unavailable synthetic'}));
 const coverage=TYPES.map(t=>({type:t,modes:Object.fromEntries(MODES[t].map(k=>[k,
  k==='key_wheel'&&t==='馬連'?{status:'evaluated'}:{status:'insufficient_evidence',reason:'Not enough verified preprice ability rationale in synthetic fixture'}]))}));
 const fmap=Object.fromEntries(Array.from({length:9},(_,i)=>[i+1,i+1===9?1:i+1]));
 return {
 prompt_version:'v3.9',race_context:{venue:'東京',race_no:11,start_at:'2026-10-11T15:45:00+09:00',
  sale_field_size:9,place_paid_positions:3,offered_types:TYPES},
 market_coverage_status:'incomplete',market_coverage_snapshot_at:at,
 bet_type_evaluations:rows,ticket_candidate_comparisons:comparisons,ticket_candidate_search_audit:search,
 purchase_gate:{scope:'race_local_8types',local_coverage_status:'partial',candidates:[{
  type:'馬連',selection:represent.selection,quote_verified:true,source_url:source,observed_at:at,
  probability_assessed:true,probability_method:'Full-field conditional top3 model',uncertainty_assessed:true,
  ability_reason:'Synthetic',edge_reason:'Price and probability',risk_reason:'Uncalibrated',eligibility:'eligible',reason:'Valid'}]},
 probability_model_audit:{status:'complete',calibrated:false,model:'Full field probabilities',primary_source:'https://example.org/synthetic-runners',
  source_observed_at:at,runners:Array.from({length:n},(_,i)=>({horse_number:i+1,win_probability:distributions.central.filter(o=>o.finish[0]===i+1).reduce((p,o)=>p+o.probability,0),evidence:'nine axes synth',source_url:'https://example.org/synthetic-runners'})),
  scenarios:['low','central','high'].map(s=>({name:s,assumption:'Simulated pace '+s,candidate_hit_probability:.02}))},
 frame_map:fmap,model_assumptions:['no_dead_heat','uncalibrated'],
 outcome_distributions:distributions,strategy_coverage_audit:coverage,purchase_strategy_evaluations:[st],
 purchase_decision:'buy',purchase_reason_code:'bought',selected_strategy_id:st.strategy_id,best_strategy_id:st.strategy_id,
 best_bet_id:'B01',final_bets:st.lines.map((l,i)=>({id:'B0'+(i+1),...l})),purchase_budget_yen:3000,
 total_stake_yen:st.total_stake_yen,final_bets_fixed_at:freeze};
}
const valid=(name,d)=>{const e=validateV39(d);assert.deepEqual(e,[],name+': '+e.join('; '));console.log('PASS '+name)};
const invalid=(name,d,fragment)=>{const e=validateV39(d);assert(e.some(x=>x.includes(fragment)),name+' expected '+fragment+': '+e.join('; '));console.log('PASS '+name+' rejects invalid portfolio')};
const base=sample();valid('eight-type coverage plus final two-line quinella wheel',base);
let v=cp(base);v.purchase_strategy_evaluations[0].lines[1].market_odds=null;invalid('mixed quote verification',v,'cannot be eligible without all exact real quotes');
v=cp(base);v.purchase_strategy_evaluations[0].roi_scenarios.central+=.1;invalid('bogus portfolio ROI',v,'joint portfolio roi_scenarios incorrect');
v=cp(base);v.final_bets[1].selection=[1,4];invalid('wrong final bets',v,'final bet differs from exact strategy line');
v=cp(base);v.purchase_budget_yen=100;invalid('over budget',v,'exceeds race budget');
v=cp(base);v.strategy_coverage_audit[3].modes.box.reason=null;invalid('unexplained skipped strategy',v,'coverage skip reason missing');
v=cp(base);v.final_bets_fixed_at='2026-10-11T16:00:00+09:00';invalid('late freeze',v,'not frozen before start');
v=cp(base);v.race_context.place_paid_positions=2;invalid('place eligibility error',v,'8+ horse races');
v=cp(base);v.probability_model_audit.runners[0].win_probability+=.01;invalid('do not silently change fixed STEP1 win chance',v,'central joint distribution changes frozen win probability');
console.log('PASS all bet strategies + joint payout regression cases');

// Reuse the unchanged synthetic v3.9 fixture in later-version purchase-only regression tests.
export {sample as makeV39Sample};
