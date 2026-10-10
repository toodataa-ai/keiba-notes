import assert from 'node:assert/strict';
import {validateMultiCandidate35} from './validate-multi-candidate-v35.mjs';
const TYPES=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'];
const at='2026-10-11T09:00:00+09:00';
const source='https://example.org/test-market/trifecta';
const sel=[5,3,9];
const probability={low:.009,central:.016,high:.025};
function pricedTrifecta(a,odds,eligibility='ineligible'){
 return {type:'三連単',selection:a,source_url:source,observed_at:at,assessed_at:at,market_odds:odds,
 probability_method:'pre-race full-field PL conditional finish with three evidence scenarios',
 probability_scenarios:probability,break_even_probability:1/odds,ev_scenarios:{low:probability.low*odds,central:probability.central*odds,high:probability.high*odds},
 ability_reason:'Pre-race nine-axis assessment supports order possibility',risk_reason:'Price and pace/going uncertainty reviewed',
 eligibility,decision_reason:eligibility==='eligible'?'Low, central and high scenario compared; acceptable research risk':'Another combination more attractive'};
}
function sample(){
 const tri=pricedTrifecta(sel,160,'eligible');
 const rows=TYPES.map(type=>type==='三連単'?{
  type,status:'evaluated',candidate:{selection:sel,label:'5→3→9',kind:'horse_numbers'},market_odds:160,source_url:source,observed_at:at,assessed_at:at,probability:.016,
  probability_method:tri.probability_method,ev_multiple:2.56,decision:'buy',reason:'Conditional order evidenced'
 }:{type,status:'unpriced',candidate:null,market_odds:null,source_url:null,observed_at:null,assessed_at:at,probability:null,probability_method:null,ev_multiple:null,decision:'pass',reason:'Synthetic no-market case'});
 const comparisons=[...TYPES.filter(x=>x!=='三連単').map((type,i)=>({
  type,selection:(['三連複'].includes(type)?[1,3,5]:['馬単','馬連','枠連','ワイド'].includes(type)?[1,3]:[1]),
  source_url:null,observed_at:null,assessed_at:at,market_odds:null,probability_method:null,probability_scenarios:null,
  break_even_probability:null,ev_scenarios:null,ability_reason:'Candidate score assessed from known grades',
  risk_reason:'No quoted market price available',eligibility:'unpriced',decision_reason:'Not promoted without odds'
 })),tri,pricedTrifecta([5,9,3],125),pricedTrifecta([3,5,9],110)];
 const search=TYPES.map(type=>{
  const xs=comparisons.filter(x=>x.type===type),priced_count=xs.filter(x=>typeof x.market_odds==='number').length;
  return {type,generated_count:xs.length,priced_count,
    shortfall_reason:xs.length<({'三連複':3,'三連単':3}[type]||2)?'No independent supported additional STEP1 combinations in fixture':null,
    price_shortfall_reason:priced_count<({'三連複':3,'三連単':3}[type]||2)?'Source unavailable in synthetic test fixture':null};
 });
 return {
  prompt_version:'v3.5',race_context:{venue:'東京',race_no:11,start_at:'2026-10-11T15:45:00+09:00'},
  market_coverage_status:'incomplete',market_coverage_snapshot_at:at,bet_type_evaluations:rows,
  purchase_gate:{scope:'race_local_8types',local_coverage_status:'partial',candidates:[{
    type:'三連単',selection:sel,quote_verified:true,source_url:source,observed_at:at,probability_assessed:true,
    probability_method:tri.probability_method,uncertainty_assessed:true,
    ability_reason:'Actual course/pace evidence',edge_reason:'3 alternative pace scenarios and price break-even compared',
    risk_reason:'Uncalibrated uncertainty acknowledged',eligibility:'eligible',reason:'Trifecta qualifies on same standard as singles'
  }]},
  probability_model_audit:{
   status:'complete',model:'full-field conditional ordering',primary_source:'https://jra.go.jp/example',source_observed_at:at,calibrated:false,
   runners:[{horse_number:5,win_probability:.4,evidence:'9 axis score',source_url:'https://jra.go.jp/example'},{horse_number:3,win_probability:.35,evidence:'9 axis course',source_url:'https://jra.go.jp/example'},{horse_number:9,win_probability:.25,evidence:'9 axis speed',source_url:'https://jra.go.jp/example'}],
   scenarios:[{name:'front',assumption:'front runners',candidate_hit_probability:.009},{name:'central',assumption:'balanced',candidate_hit_probability:.016},{name:'late',assumption:'late speed',candidate_hit_probability:.025}]
  },ticket_candidate_comparisons:comparisons,ticket_candidate_search_audit:search,
  purchase_decision:'buy',purchase_reason_code:'bought',best_bet_id:'B01',final_bets:[{id:'B01',type:'三連単',selection:sel,stake_yen:100,reason:'Evidence and risk compared'}],
  total_stake_yen:100,final_bets_fixed_at:'2026-10-11T09:05:00+09:00'
 };
}
const copy=x=>JSON.parse(JSON.stringify(x));
function valid(label,x){const errors=validateMultiCandidate35(x);assert.deepEqual(errors,[],label+': '+errors.join('; '));console.log('PASS '+label)}
function invalid(label,x,part){const errors=validateMultiCandidate35(x);assert(errors.some(x=>x.includes(part)),label+': expected '+part+' but got '+errors.join('; '));console.log('PASS '+label+' (correctly rejected)')}
const base=sample();
valid('three grounded trifecta candidates; best bet may be ordered trifecta despite uncalibrated model',base);
let c=copy(base);c.purchase_decision='pass';c.purchase_reason_code='risk_high';c.final_bets=[];c.best_bet_id=null;c.total_stake_yen=0;valid('trifecta can be passed for explicit risk rather than automatically or missing information',c);
c=copy(base);c.final_bets[0].selection=[3,5,9];invalid('do not silently substitute other ordered trifecta',c,'final_bet not in eligible');
c=copy(base);const best=c.ticket_candidate_comparisons.find(x=>x.type==='三連単'&&JSON.stringify(x.selection)===JSON.stringify(sel));
best.market_odds=null;best.ev_scenarios=null;best.eligibility='unpriced';invalid('priced triplets must never use estimated odds',c,'representative source/price mismatch');
c=copy(base);c.ticket_candidate_comparisons.find(x=>x.type==='三連単').observed_at='2026-10-11T09:30:00+09:00';invalid('exact quote time must match summary',c,'representative source/price mismatch');
c=copy(base);c.ticket_candidate_comparisons=c.ticket_candidate_comparisons.filter(x=>x.type!=='三連単'||JSON.stringify(x.selection)===JSON.stringify(sel));c.ticket_candidate_search_audit.find(x=>x.type==='三連単').generated_count=1;c.ticket_candidate_search_audit.find(x=>x.type==='三連単').priced_count=1;c.ticket_candidate_search_audit.find(x=>x.type==='三連単').shortfall_reason=null;c.ticket_candidate_search_audit.find(x=>x.type==='三連単').price_shortfall_reason=null;
invalid('must research multiple trifecta combinations or document why impossible',c,'missing documented reason');
c=copy(base);c.ticket_candidate_comparisons.push({...c.ticket_candidate_comparisons.at(-1),type:'WIN5'});invalid('WIN5 remains out of scope',c,'invalid type or WIN5');
console.log('v3.5 synthetic multi-ticket comparison tests: success');
