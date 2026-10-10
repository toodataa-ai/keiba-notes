import assert from 'node:assert/strict';
import {validateV38} from './validate-jra-strategy-v38.mjs';
const TYPES=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'];
const at='2026-10-11T09:00:00+09:00',freeze='2026-10-11T09:05:00+09:00',source='https://example.org/synthetic-odds';
const pts={low:[.46,.28,.16,.10],central:[.40,.32,.18,.10],high:[.34,.35,.20,.11]};
const seq=[[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]];
const key=s=>JSON.stringify(s);
const prob=(a,sc)=>{const p=pts[sc],[x,y,z]=a.map(v=>p[v-1]);return x*y/(1-x)*z/(1-x-y);};
const copy=x=>JSON.parse(JSON.stringify(x));
const odds=[50,55,60,65,70,75];
const triples=seq.map((sel,i)=>{
 const ps=Object.fromEntries(Object.keys(pts).map(sc=>[sc,prob(sel,sc)]));
 const o=odds[i];
 return {type:'三連単',selection:sel,source_url:source,observed_at:at,assessed_at:at,
   market_odds:o,probability_method:'full-field PL conditional ordering with three explicit scenarios',
   probability_scenarios:ps,break_even_probability:1/o,
   ev_scenarios:Object.fromEntries(Object.keys(ps).map(sc=>[sc,ps[sc]*o])),
   ability_reason:'Synthetic pre-race ability/order logic',risk_reason:'Synthetic scenario stress',
   eligibility:'eligible',decision_reason:'Evidence-price candidate eligible'};
});
const otherType=t=>['単勝','複勝'].includes(t)?[1]:['馬連','馬単','ワイド','枠連'].includes(t)?[1,2]:[1,2,3];
const others=TYPES.filter(t=>t!=='三連単').map(type=>({
 type,selection:otherType(type),source_url:null,observed_at:null,assessed_at:at,market_odds:null,
 probability_method:null,probability_scenarios:null,break_even_probability:null,ev_scenarios:null,
 ability_reason:'Synthetic STEP1 assessment',risk_reason:'No real price in synthetic test',
 eligibility:'unpriced',decision_reason:'Excluded due to no quote'
}));
const line=t=>({type:t.type,selection:t.selection,stake_yen:100,market_odds:t.market_odds,source_url:t.source_url,
 observed_at:t.observed_at,probability_scenarios:copy(t.probability_scenarios)});
function strategy(id,kind,def,selections) {
 const list=selections.map(sel=>line(triples.find(t=>key(t.selection)===key(sel))));
 const S=100*list.length;
 const sum=(sc,what)=>list.reduce((v,l)=>v+(what==='p'?l.probability_scenarios[sc]:l.probability_scenarios[sc]*l.stake_yen*l.market_odds),0);
 const hit=Object.fromEntries(Object.keys(pts).map(sc=>[sc,sum(sc,'p')]));
 const payout=Object.fromEntries(Object.keys(pts).map(sc=>[sc,sum(sc,'payout')]));
 return {strategy_id:id,type:'三連単',strategy_kind:kind,definition:def,generated_ticket_count:list.length,lines:list,
  eligibility:'eligible',total_stake_yen:S,hit_probability_scenarios:hit,expected_payout_yen_scenarios:payout,
  roi_scenarios:Object.fromEntries(Object.keys(pts).map(sc=>[sc,payout[sc]/S])),
  full_loss_probability_scenarios:Object.fromEntries(Object.keys(pts).map(sc=>[sc,1-hit[sc]])),
  decision_reason:'Synthetic budget, scenario sensitivity and comparable alternatives reviewed'};
}
function selected(data,st) {
 data.purchase_strategy_evaluations.push(st);
 data.selected_strategy_id=st.strategy_id;data.best_strategy_id=st.strategy_id;data.best_bet_id='B01';
 data.final_bets=st.lines.map((l,i)=>({id:'B'+String(i+1).padStart(2,'0'),type:l.type,
   selection:l.selection,stake_yen:l.stake_yen,market_odds:l.market_odds,source_url:l.source_url,observed_at:l.observed_at}));
 data.total_stake_yen=st.total_stake_yen;
 return data;
}
function sample(){
 const representative=triples[0];
 const rows=TYPES.map(type=>type==='三連単'?{
    type,status:'evaluated',candidate:{selection:representative.selection,label:'1→2→3',kind:'horse_numbers'},
    market_odds:representative.market_odds,source_url:source,observed_at:at,assessed_at:at,
    probability:representative.probability_scenarios.central,probability_method:representative.probability_method,
    ev_multiple:representative.ev_scenarios.central,decision:'buy',reason:'Scenario evidence'
  }:{type,status:'unpriced',candidate:null,market_odds:null,source_url:null,observed_at:null,assessed_at:at,
  probability:null,probability_method:null,ev_multiple:null,decision:'pass',reason:'Synthetic unavailable market'});
 const comparison=[...others,...triples];
 const audit=TYPES.map(type=>{
   const count=comparison.filter(x=>x.type===type),priced=count.filter(x=>typeof x.market_odds==='number').length;
   return {type,generated_count:count.length,priced_count:priced,
    shortfall_reason:count.length<({'三連複':3,'三連単':3}[type]||2)?'Synthetic evidence scope':null,
    price_shortfall_reason:priced<({'三連複':3,'三連単':3}[type]||2)?'No external prices in isolated test':null};
 });
 return {prompt_version:'v3.8',race_context:{venue:'東京',race_no:11,start_at:'2026-10-11T15:45:00+09:00'},
 market_coverage_status:'incomplete',market_coverage_snapshot_at:at,bet_type_evaluations:rows,
 purchase_gate:{scope:'race_local_8types',local_coverage_status:'partial',candidates:[{
  type:'三連単',selection:representative.selection,quote_verified:true,source_url:source,observed_at:at,
  probability_assessed:true,probability_method:representative.probability_method,uncertainty_assessed:true,
  ability_reason:'Synthetic evidence',edge_reason:'Price vs break-even',risk_reason:'Scenario downside',
  eligibility:'eligible',reason:'Audited'}]},
 probability_model_audit:{status:'complete',model:'full-field ordering',primary_source:'https://example.org/jra-synthetic',
  source_observed_at:at,calibrated:false,runners:[1,2,3,4].map(i=>({horse_number:i,
    win_probability:pts.central[i-1],evidence:'Synthetic nine-axis inputs',source_url:'https://example.org/jra-synthetic'})),
  scenarios:['low','central','high'].map(sc=>({name:sc,assumption:'Synthetic pace/going '+sc,candidate_hit_probability:prob(seq[0],sc)}))},
 ticket_candidate_comparisons:comparison,ticket_candidate_search_audit:audit,
 purchase_strategy_evaluations:[],purchase_decision:'buy',purchase_reason_code:'bought',purchase_budget_yen:3000,
 final_bets:[],total_stake_yen:0,final_bets_fixed_at:freeze};
}
const multi=()=>strategy('S01','trifecta_two_key_multi',{axis:[1,2],partners:[3]},seq);
const formation=()=>strategy('S02','trifecta_formation',{first:[1,2],second:[1,2],third:[3]},[[1,2,3],[2,1,3]]);
const box=()=>strategy('S03','trifecta_box',{horses:[1,2,3]},seq);
const solo=()=>strategy('S04','single',{selection:[1,2,3]},[[1,2,3]]);
function valid(name,d){const errors=validateV38(d);assert.deepEqual(errors,[],name+': '+errors.join('; '));console.log('PASS '+name);}
function invalid(name,d,fragment){const errors=validateV38(d);assert(errors.some(x=>x.includes(fragment)),name+': '+errors.join('; '));console.log('PASS '+name+' (correctly rejected)');}
valid('two-key multi: 6 distinct ordered tickets, aggregate ROI',selected(sample(),multi()));
valid('two-place formation: 2 valid disjoint ordered tickets',selected(sample(),formation()));
valid('three-horse box: 6 distinct ordered tickets',selected(sample(),box()));
valid('legacy-style single selection remains possible',selected(sample(),solo()));
const m=selected(sample(),multi());
let x=copy(m);x.purchase_strategy_evaluations[0].expected_payout_yen_scenarios.central+=100;
invalid('reject ROI built with incorrect aggregate payout',x,'expected payout not sum');
x=copy(m);x.final_bets[0].selection=[1,2,4];invalid('reject a settlement-unsafe substituted selection',x,'does not exactly match');
x=copy(m);x.final_bets[1].selection=x.final_bets[0].selection;invalid('reject duplicate purchases',x,'duplicate final_bet');
x=copy(m);x.purchase_strategy_evaluations[0].lines[2].market_odds=null;
invalid('unverified component quote disqualifies full multi',x,'unpriced lines cannot');
x=copy(m);x.purchase_budget_yen=500;invalid('budget must apply to entire strategy',x,'exceeds budget cap');
x=copy(m);x.final_bets_fixed_at='2026-10-11T16:00:00+09:00';invalid('freeze after start forbidden',x,'frozen before post');
x=copy(m);x.purchase_strategy_evaluations[0].definition.partners.push(4);
invalid('reject missing expanded multi counterpart tickets',x,'expanded combinations/count mismatch');
x=copy(m);x.purchase_strategy_evaluations[0].hit_probability_scenarios.low=1.1;
invalid('cannot sum marginal probabilities as if independent',x,'hit probability sum incorrect');
console.log('v3.8 strategy portfolio synthetic tests: success');
