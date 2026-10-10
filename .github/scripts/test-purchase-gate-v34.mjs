import assert from 'node:assert/strict';
import {validateV34, isV34OrLater} from './validate-purchase-gate-v34.mjs';

const types=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単','WIN5'];
const stamp='2026-10-11T08:00:00+09:00';
function sample(){
 const data={
   prompt_version:'v3.4',
   race_context:{venue:'東京',race_no:11,start_at:'2026-10-11T15:45:00+09:00'},
   market_coverage_status:'incomplete',market_coverage_snapshot_at:stamp,
   bet_type_evaluations:types.map(t=>({
     type:t,status:t==='単勝'?'evaluated':t==='WIN5'?'separate_event_pending':'unpriced',
     candidate:t==='単勝'?{selection:[5],label:'5'}:null,
     market_odds:t==='単勝'?5.6:null,
     source_url:t==='単勝'?'https://example.org/market/5':null,
     observed_at:t==='単勝'?stamp:null,
     assessed_at:stamp,probability:t==='単勝'?0.24:null,
     probability_method:t==='単勝'?'scenario-informed, uncalibrated':null,
     ev_multiple:t==='単勝'?1.344:null,decision:'pass',reason:'unpriced where unavailable'
   })),
   purchase_gate:{
     scope:'race_local_8types',local_coverage_status:'partial',
     win5_status:'separate_event_pending',
     candidates:[{
       type:'単勝',selection:[5],quote_verified:true,
       source_url:'https://example.org/market/5',observed_at:stamp,
       probability_assessed:true,uncertainty_assessed:true,
       ability_reason:'Pre-market STEP1 fixed course and ability evidence',
       edge_reason:'Price comparison over multiple uncertainty scenarios, not point EV alone',
       risk_reason:'Possible odds movement, scratch and scenario uncertainty reviewed',
       eligibility:'eligible',reason:'Specific priced candidate, evidence/risk examined'
     }]
   },
   purchase_decision:'buy',purchase_reason_code:'bought',best_bet_id:'B01',
   total_stake_yen:100,final_bets_fixed_at:'2026-10-11T08:05:00+09:00',
   final_bets:[{id:'B01',type:'単勝',selection:[5],stake_yen:100,reason:'ability and price'}]
 };
 return data;
}
function valid(name,obj){const errors=validateV34(obj);assert.deepEqual(errors,[],name+': '+errors.join('; '));console.log('PASS '+name);}
function invalid(name,obj,fragment){const errors=validateV34(obj);assert(errors.some(x=>x.includes(fragment)),name+': expected '+fragment+' in '+errors.join('; '));console.log('PASS '+name+' (rejected unsafe case)');}
assert(isV34OrLater('v3.4'));assert(isV34OrLater('v4.0'));assert(!isV34OrLater('v3.3'));
valid('partial market + WIN5 incomplete can still buy verified local single win',sample());
{
 const x=sample();x.purchase_decision='pass';x.purchase_reason_code='no_value';x.best_bet_id=null;x.final_bets=[];x.total_stake_yen=0;
 valid('fully assessed local candidate passed for low value, not called missing data',x);
}
{
 const x=sample();x.purchase_decision='pass';x.purchase_reason_code='risk_high';x.best_bet_id=null;x.final_bets=[];x.total_stake_yen=0;
 valid('candidate exists but uncertainty too high',x);
}
{
 const x=sample();x.purchase_gate.candidates[0].eligibility='ineligible';x.purchase_gate.candidates[0].reason='missing sufficient risk evidence';x.purchase_gate.candidates[0].quote_verified=false;
 x.purchase_decision='pass';x.purchase_reason_code='insufficient_local_information';x.best_bet_id=null;x.final_bets=[];x.total_stake_yen=0;
 valid('no eligible local candidate may be information-insufficient',x);
}
{
 const x=sample();x.purchase_decision='pass';x.purchase_reason_code='insufficient_local_information';x.best_bet_id=null;x.final_bets=[];x.total_stake_yen=0;
 invalid('reject mechanical info-pass when eligible local bet exists',x,'insufficient_local_information invalid');
}
{
 const x=sample();x.purchase_gate.candidates[0].quote_verified=false;
 invalid('do not buy unverified market',x,'eligible without independently checked quote');
}
{
 const x=sample();x.final_bets[0].type='三連単';
 invalid('cannot buy unassessed ticket',x,'final_bet not in eligible');
}
{
 const x=sample();x.purchase_gate.candidates[0].selection=[7];
 invalid('must match evaluated exact selection',x,'selection mismatch');
}
{
 const x=sample();x.purchase_gate.candidates[0].source_url='https://example.org/different';
 invalid('secondary quote trace must match',x,'market source/timestamp differ');
}
{
 const x=sample();x.final_bets_fixed_at='2026-10-11T15:45:00+09:00';
 invalid('never fix after race post',x,'fixed at or after post');
}
{
 const x=sample();x.market_coverage_status='complete';x.purchase_gate.local_coverage_status='complete';
 invalid('cannot claim coverage complete with unpriced types',x,'market marked complete');
}
console.log('v3.4 purchase gate synthetic test suite passed');
