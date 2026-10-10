import fs from 'node:fs';
import path from 'node:path';
import {validateMultiCandidate35} from './validate-multi-candidate-v35.mjs';
import {TYPES,MODES,MIXED_MODES,ticketKey,expandStrategy,evaluateStrategy,oddsFloor} from './jra-strategy-engine-v39.mjs';

const nonempty=x=>typeof x==='string'&&x.trim().length>0;
const time=x=>nonempty(x)&&Number.isFinite(Date.parse(x));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const near=(a,b)=>finite(a)&&Math.abs(a-b)<=Math.max(1e-6,Math.abs(b)*1e-6);
const SCENARIOS=['low','central','high'];
export const isV39=v=>v==='v3.9';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

export function validateV39(data){
 const errors=[],add=s=>errors.push(s);
 if(!isV39(data.prompt_version))return errors;
 // The v3.4 and v3.5 analysis/market summaries are validated without imposing their old single-bet limit.
 const projected={...data,prompt_version:'v3.7',purchase_decision:'pass',best_bet_id:null,
   purchase_reason_code:(data.purchase_gate?.candidates||[]).some(c=>c.eligibility==='eligible')?'risk_high':'insufficient_local_information',
   final_bets:[],total_stake_yen:0};
 errors.push(...validateMultiCandidate35(projected).map(x=>'legacy analytical input: '+x));
 const race=data.race_context||{};
 if(!time(race.start_at))add('race post timestamp required');
 if(!Number.isInteger(race.sale_field_size)||race.sale_field_size<2) add('official sale field size required');
 if(!Array.isArray(race.offered_types))add('official offered eight types required');
 else if(race.offered_types.some(x=>!TYPES.includes(x)))add('invalid or WIN5 offered type');
 if(race.sale_field_size>=8&&race.place_paid_positions!==3)add('8+ horse races pay 3 place positions');
 if(race.sale_field_size>=5&&race.sale_field_size<=7&&race.place_paid_positions!==2)add('5-7 horse races pay 2 place positions');
 if(race.sale_field_size<5&&race.offered_types?.includes('複勝'))add('place not sold with fewer than 5');
 if(race.sale_field_size<4&&race.offered_types?.some(t=>['ワイド','三連複','三連単'].includes(t)))add('wide/trio/trifecta not sold with fewer than 4');
 if(race.sale_field_size<3&&race.offered_types?.some(t=>['馬連','馬単'].includes(t)))add('quinella/exacta not sold with fewer than 3');
 if(race.sale_field_size<9&&race.offered_types?.includes('枠連')&&race.same_frame_sale_exception_confirmed!==true)add('frame quinella sold below 9 requires official exception proof');
 if(race.sale_field_size>=5&&!race.offered_types?.includes('複勝'))add('place omitted despite eligible field');
 const runners=data.probability_model_audit?.runners;
 if(!Array.isArray(runners)||runners.length<3)add('full-field probability runners required');
 const horseIds=new Set((runners||[]).map(r=>r.horse_number));
 if(race.sale_field_size!==horseIds.size&&race.sale_field_size>0)add('sale field and probability runner count differ');
 if(!data.model_assumptions?.includes('no_dead_heat'))add('outcome model must state no_dead_heat scenario limitation');
 const frameMap=data.frame_map||{};
 if(race.offered_types?.includes('枠連')){
   for(const n of horseIds){
     const fr=frameMap[String(n)];
     if(!Number.isInteger(fr)||fr<1||fr>8)add('official frame_map missing horse '+n);
   }
 }
 const dists=data.outcome_distributions;
 if(!dists||typeof dists!=='object')add('full joint outcome distributions required');
 else {
   for(const sc of SCENARIOS){
     const arr=dists[sc];
     if(!Array.isArray(arr)||arr.length===0){add('missing '+sc+' joint outcomes');continue;}
     let sum=0;const seen=new Set();
     for(const o of arr){
       if(!Array.isArray(o.finish)||o.finish.length!==3||new Set(o.finish).size!==3||o.finish.some(n=>!horseIds.has(n))||!finite(o.probability)||o.probability<0||o.probability>1){add('invalid '+sc+' outcome');continue;}
       const key=JSON.stringify(o.finish);
       if(seen.has(key))add('duplicate '+sc+' outcome');seen.add(key);sum+=o.probability;
     }
     if(Math.abs(sum-1)>0.00001)add('unnormalized '+sc+' joint outcomes');
   }
   if(SCENARIOS.every(sc=>Array.isArray(dists[sc]))){
     const sets=SCENARIOS.map(sc=>new Set(dists[sc].map(o=>JSON.stringify(o.finish))));
     for(const k of sets[0])if(sets.some(s=>!s.has(k)))add('outcome support differs by scenario');
   }
 }
 const coverage=data.strategy_coverage_audit;
 if(!Array.isArray(coverage)||coverage.length!==8||TYPES.some((t,i)=>coverage[i]?.type!==t)) add('all eight bet type strategy coverage rows required');
 const strategies=data.purchase_strategy_evaluations;
 if(!Array.isArray(strategies)||!strategies.length){add('purchase_strategy_evaluations missing');return errors;}
 const ids=new Set(),candidates=new Map();
 for(const [i,st] of strategies.entries()){
   const loc='strategy['+i+']',type=st.type,mode=st.strategy_kind;
   if(!nonempty(st.strategy_id)||ids.has(st.strategy_id))add(loc+' duplicate/missing ID');
   ids.add(st.strategy_id);
   if(!(type==='mixed'&&MIXED_MODES.includes(mode))&&!(TYPES.includes(type)&&MODES[type]?.includes(mode))){
     add(loc+' type/mode mismatch');continue;
   }
   if(!nonempty(st.ability_reason)||!nonempty(st.decision_reason)||!nonempty(st.risk_reason))add(loc+' missing analysis rationale');
   let expected=[];
   try{expected=expandStrategy(type,mode,st.definition)}catch(e){add(loc+' expansion invalid: '+e.message);continue;}
   const lines=st.lines;
   if(!Array.isArray(lines)){add(loc+' lines missing');continue;}
   if(st.generated_ticket_count!==expected.length||lines.length!==expected.length)add(loc+' generated count mismatch');
   const expectedKeys=new Set(expected.map(t=>ticketKey(t.type,t.selection))),seen=new Set();
   let priced=true,stakes=0,quoteValid=true;
   for(const [j,l] of lines.entries()){
     const lLoc=loc+'.line['+j+']';
     let k;
     try{k=ticketKey(l.type,l.selection)}catch(e){add(lLoc+' invalid ticket: '+e.message);continue;}
     if(seen.has(k))add(loc+' duplicated priced ticket');seen.add(k);
     if(!expectedKeys.has(k))add(loc+' expanded line mismatch');
     if(!Number.isInteger(l.stake_yen)||l.stake_yen<100||l.stake_yen%100!==0)add(lLoc+' stake must be >=100 and multiple of 100');
     stakes+=l.stake_yen||0;
     if(!horseIds.has(l.selection?.[0])&&l.type!=='枠連')add(lLoc+' horse not in STEP1 runners');
     if(l.type!=='枠連'&&l.selection?.some(n=>!horseIds.has(n)))add(lLoc+' includes unregistered horse');
     if(race.offered_types&&!race.offered_types.includes(l.type))add(lLoc+' not officially offered');
     if(oddsFloor(l.market_odds)===null){priced=false;continue;}
     if(l.quote_verified!==true||!nonempty(l.source_url)||!time(l.observed_at)||!nonempty(l.market_selection_id))quoteValid=false;
     if(time(l.observed_at)&&time(race.start_at)&&Date.parse(l.observed_at)>=Date.parse(race.start_at))add(lLoc+' quote after post');
     if(nonempty(l.market_selection_id)&&l.market_selection_id!==k)add(lLoc+' market selection quote mismatch');
     if(l.type==='枠連'&&l.selection?.[0]===l.selection?.[1]){
       const count=Object.values(frameMap).filter(v=>v===l.selection[0]).length;
       if(count<2)add(lLoc+' same-frame ticket without two horses');
     }
   }
   if(seen.size!==expectedKeys.size||[...expectedKeys].some(k=>!seen.has(k)))add(loc+' full formation/wheel set not expanded');
   if(st.total_stake_yen!==stakes)add(loc+' total stake mismatch');
   if(!['eligible','ineligible','unpriced','probability_unavailable'].includes(st.eligibility))add(loc+' invalid status');
   if(!priced||!quoteValid){
     if(st.eligibility==='eligible')add(loc+' cannot be eligible without all exact real quotes');
     for(const field of ['roi_scenarios','hit_probability_scenarios','expected_payout_yen_scenarios','full_loss_probability_scenarios','loss_probability_scenarios'])
       if(st[field]!==null)add(loc+' unpriced metrics must be null '+field);
     continue;
   }
   try{
     const computed=evaluateStrategy(lines,dists,frameMap,race);
     for(const sc of SCENARIOS)for(const field of ['hit_probability_scenarios','expected_payout_yen_scenarios','roi_scenarios','full_loss_probability_scenarios','loss_probability_scenarios']){
       if(!near(st[field]?.[sc],computed[field][sc]))add(loc+' joint portfolio '+field+' incorrect '+sc);
     }
   }catch(e){add(loc+' cannot evaluate joint outcome: '+e.message)}
   candidates.set(st.strategy_id,st);
 }
 for(const item of coverage||[]){
   if(!TYPES.includes(item.type))continue;
   const declared=item.modes||{};
   const expected=MODES[item.type]||[];
   for(const mode of expected){
     const v=declared[mode];
     if(!v||!['evaluated','unpriced','insufficient_evidence','not_offered','over_budget'].includes(v.status)){
       add('coverage not accounted for '+item.type+' / '+mode);continue;
     }
     if(v.status==='evaluated'&&!strategies.some(st=>st.type===item.type&&st.strategy_kind===mode)){
       add('coverage claims evaluated without strategy '+item.type+' / '+mode);
     }
     if(v.status!=='evaluated'&&!nonempty(v.reason))add('coverage skip reason missing '+item.type+' / '+mode);
   }
   if(Object.keys(declared).some(x=>!expected.includes(x)))add('unknown coverage mode '+item.type);
 }
 const bets=Array.isArray(data.final_bets)?data.final_bets:[];
 if(!Array.isArray(data.final_bets))add('final_bets missing');
 const amount=bets.reduce((s,x)=>s+(finite(x.stake_yen)?x.stake_yen:0),0);
 if(amount!==data.total_stake_yen)add('final stakes do not reconcile');
 if(data.purchase_decision==='pass'){
   if(!['no_value','risk_high','insufficient_local_information'].includes(data.purchase_reason_code))add('invalid pass reason');
   if(data.selected_strategy_id!==null||data.best_strategy_id!==null||data.best_bet_id!==null||bets.length||data.total_stake_yen!==0)add('pass must have no purchased strategy and 0 stake');
 }else if(data.purchase_decision==='buy'){
   if(data.purchase_reason_code!=='bought')add('buy needs bought reason code');
   if(!nonempty(data.selected_strategy_id)||data.best_strategy_id!==data.selected_strategy_id)add('must choose exactly one best strategy');
   const selected=candidates.get(data.selected_strategy_id);
   if(!selected||selected.eligibility!=='eligible')add('selected strategy lacks complete eligibility / odds');
   if(data.probability_model_audit?.status!=='complete')add('full model evidence required');
   const budget=data.purchase_budget_yen===undefined?3000:data.purchase_budget_yen;
   if(!Number.isInteger(budget)||budget<100||budget%100!==0)add('budget must use >=100 yen increments');
   if(budget>3000&&data.budget_source!=='user')add('budget increase requires user authorization');
   if(amount>budget)add('portfolio exceeds race budget');
   if(!time(data.final_bets_fixed_at)||time(race.start_at)&&Date.parse(data.final_bets_fixed_at)>=Date.parse(race.start_at))add('final bets not frozen before start');
   if(!nonempty(data.best_bet_id)||!bets.some(x=>x.id===data.best_bet_id))add('legacy best_bet_id must point to a selected line');
   if(selected){
     if(selected.lines.length!==bets.length)add('selected strategy missing expanded final bets');
     const byKey=new Map(selected.lines.map(l=>[ticketKey(l.type,l.selection),l])),seen=new Set(),bids=new Set();
     for(const bet of bets){
       let k;try{k=ticketKey(bet.type,bet.selection)}catch(e){add('invalid final bet selection');continue;}
       if(seen.has(k)||bids.has(bet.id))add('duplicate final bets or IDs');seen.add(k);bids.add(bet.id);
       const line=byKey.get(k);
       if(!line||bet.stake_yen!==line.stake_yen||!same(bet.market_odds,line.market_odds)||bet.source_url!==line.source_url||bet.observed_at!==line.observed_at||bet.market_selection_id!==line.market_selection_id)add('final bet differs from exact strategy line');
       if(time(line?.observed_at)&&time(data.final_bets_fixed_at)&&Date.parse(line.observed_at)>Date.parse(data.final_bets_fixed_at))add('quote recorded after frozen final bets');
     }
   }
 }else add('purchase_decision must be buy/pass');
 return errors;
}

if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(new URL(import.meta.url).pathname)){
 const base='e2e_validation/predictions',errors=[];let n=0;
 if(fs.existsSync(base))for(const folder of fs.readdirSync(base,{withFileTypes:true})){
  if(!folder.isDirectory())continue;
  for(const file of fs.readdirSync(path.join(base,folder.name)).filter(x=>x.endsWith('.json'))){
    const filePath=path.join(base,folder.name,file),obj=JSON.parse(fs.readFileSync(filePath,'utf8'));
    if(!isV39(obj.prompt_version))continue;n++;
    for(const e of validateV39(obj))errors.push(filePath+': '+e);
  }
 }
 if(errors.length){console.error(errors.join('\n'));process.exit(1);}
 console.log('v3.9 purchase-only all-eight-type strategies OK: '+n+' new formal predictions');
}
