import assert from 'node:assert/strict';
import {makeV39Sample} from './test-jra-strategy-v39.mjs';
import {expandStrategy,ticketKey,evaluateStrategy} from './jra-strategy-engine-v39.mjs';
import {optimizePurchasePortfolio} from './jra-portfolio-optimizer-v310.mjs';
import {validateV310} from './validate-jra-portfolio-v310.mjs';
const copy=x=>JSON.parse(JSON.stringify(x));
const at='2026-10-11T09:00:00+09:00';
const source='https://example.org/synthetic-market';
function addStrategy(data,id,type,kind,definition,odds){
 const raw=expandStrategy(type,kind,definition);
 const lines=raw.map((x,i)=>({...x,stake_yen:100,market_odds:typeof odds==='function'?odds(i):odds,
  source_url:source,observed_at:at,market_selection_id:ticketKey(x.type,x.selection),quote_verified:true}));
 const metrics=evaluateStrategy(lines,data.outcome_distributions,data.frame_map,data.race_context);
 const st={strategy_id:id,type,strategy_kind:kind,definition,generated_ticket_count:lines.length,lines,
   eligibility:'eligible',ability_reason:'Synthetic frozen STEP1 grounded multi-type candidate',
   risk_reason:'Joint correlated scenario losses assessed',decision_reason:'Eligible fully priced synthetic candidates',...metrics};
 data.purchase_strategy_evaluations.push(st);
 if(type!=='mixed')data.strategy_coverage_audit.find(x=>x.type===type).modes[kind]={status:'evaluated'};
 return st;
}
function build({large=false}={}){
 const data=makeV39Sample();
 data.prompt_version='v3.10';data.purchase_budget_yen=6000;data.proof_commit='test-pre-start-github-commit-proof';
 // Retain the v3.9 horse/market/ordering inputs and its original quinella wheel.
 addStrategy(data,'S02','ワイド','key_wheel',{key:1,partners:[2,3]},16);
 addStrategy(data,'S03','単勝','single',{selection:[1]},12);
 addStrategy(data,'S04','三連単','single',{selection:[1,2,3]},700);
 // Intentional overlap: original S01 quinella-wheel tickets repeated in another formation.
 const duplicate=addStrategy(data,'S05','馬連','formation',{slots:[[1],[2,3]]},i=>i===0?60:55);
 // Source / timestamp and odds must be identical for deduplication, not silently best-priced.
 for(const l of duplicate.lines){
   const original=data.purchase_strategy_evaluations[0].lines.find(x=>ticketKey(x.type,x.selection)===ticketKey(l.type,l.selection));
   if(original){l.market_odds=original.market_odds;l.source_url=original.source_url;l.observed_at=original.observed_at;}
 }
 Object.assign(duplicate,evaluateStrategy(duplicate.lines,data.outcome_distributions,data.frame_map,data.race_context));
 if(large)addStrategy(data,'S06','三連単','box',{horses:[1,2,3,4,5]},750);
 const optimal=optimizePurchasePortfolio({
  budget_yen:6000,strategies:data.purchase_strategy_evaluations,outcome_distributions:data.outcome_distributions,
  frame_map:data.frame_map,race_context:data.race_context,freeze_at:data.final_bets_fixed_at
 });
 data.purchase_decision=optimal.purchase_decision;
 data.purchase_reason_code=optimal.purchase_reason_code;
 const portfolio_id='P01';
 data.purchase_portfolio_selection={...optimal,portfolio_id};
 data.selected_strategy_id=optimal.purchase_decision==='buy'?portfolio_id:null;
 data.best_strategy_id=optimal.purchase_decision==='buy'?portfolio_id:null;
 data.final_bets=optimal.selected_lines.map((l,i)=>({id:'B'+String(i+1).padStart(2,'0'),
  type:l.type,selection:l.selection,stake_yen:l.stake_yen,market_odds:l.market_odds,
  source_url:l.source_url,observed_at:l.observed_at,market_selection_id:l.market_selection_id}));
 data.best_bet_id=optimal.purchase_decision==='buy'?'B01':null;
 data.total_stake_yen=optimal.total_stake_yen;
 return data;
}
const valid=(name,data)=>{const errs=validateV310(data);assert.deepEqual(errs,[],name+': '+errs.join('; '));console.log('PASS '+name)};
const invalid=(name,data,part)=>{const errs=validateV310(data);assert(errs.some(x=>x.includes(part)),name+': '+errs.join('; '));console.log('PASS rejects '+name)};
const small=build();
valid('cross-type optimum combines quinella, wide, win and trifecta in 6000 budget',small);
assert(small.purchase_portfolio_selection.selected_lines.length>=4,'must permit multiple type/strategy tickets');
assert(new Set(small.purchase_portfolio_selection.selected_lines.map(x=>x.type)).size>=3,'cross-type chosen');
assert(small.purchase_portfolio_selection.optimizer_audit.duplicates_collapsed>=2,'overlapping formation deduplicated');
assert(small.total_stake_yen<6000,'never spend remaining budget without eligible extra lines');
const large=build({large:true});
valid('select optimal subset of more than 60 profitable tickets under 6000 yen',large);
assert.equal(large.total_stake_yen,6000,'should use 60 distinct profitable tickets when more exist');
assert(large.purchase_portfolio_selection.optimizer_audit.positive_edge_not_selected.length>0,'must audit ignored profitable surplus');
let d=copy(small);d.total_stake_yen=6100;invalid('hard cap on final stake',d,'final portfolio stake');
d=copy(small);d.final_bets[1].selection=[1,9];invalid('selected ticket substitution',d,'purchased ticket differs');
d=copy(small);d.final_bets[1].selection=d.final_bets[0].selection;invalid('duplicate final ticket',d,'duplicate purchased line/id');
d=copy(small);d.purchase_portfolio_selection.roi_scenarios.central+=.1;invalid('invented portfolio return',d,'correlated metric mismatch');
d=copy(small);d.purchase_portfolio_selection.selected_lines.pop();invalid('omit line from selected portfolio',d,'portfolio selected line count');
d=copy(small);d.final_bets_fixed_at='2026-10-11T16:00:00+09:00';invalid('freezing bets after post',d,'must be frozen pre-start');
d=copy(small);d.purchase_portfolio_selection.optimizer_audit.expected_net_profit_yen+=100;invalid('wrong maximum profit',d,'optimizer objective');
d=copy(small);d.purchase_budget_yen=3000;invalid('obsolete three-thousand-yen cap',d,'budget must be 6000');
// A standalone strategy can be unpriced while other independently verified ones remain eligible.
d=copy(small);d.purchase_strategy_evaluations[2].lines[0].market_odds=null;
d.purchase_strategy_evaluations[2].eligibility='unpriced';
for(const k of ['hit_probability_scenarios','expected_payout_yen_scenarios','roi_scenarios','full_loss_probability_scenarios','loss_probability_scenarios'])d.purchase_strategy_evaluations[2][k]=null;
invalid('must recalculate optimum if a quoted candidate turns unpriced',d,'portfolio line differs');
const noValue=build();
for(const st of noValue.purchase_strategy_evaluations){
 for(const l of st.lines)l.market_odds=2;
 Object.assign(st,evaluateStrategy(st.lines,noValue.outcome_distributions,noValue.frame_map,noValue.race_context));
}
const opt0=optimizePurchasePortfolio({
 budget_yen:6000,strategies:noValue.purchase_strategy_evaluations,outcome_distributions:noValue.outcome_distributions,
 frame_map:noValue.frame_map,race_context:noValue.race_context,freeze_at:noValue.final_bets_fixed_at
});
assert.equal(opt0.purchase_decision,'pass');
assert.equal(opt0.total_stake_yen,0);
noValue.purchase_portfolio_selection={...opt0,portfolio_id:'P01'};
noValue.purchase_decision='pass';noValue.purchase_reason_code='no_value';
noValue.best_bet_id=null;noValue.best_strategy_id=null;noValue.selected_strategy_id=null;
noValue.final_bets=[];noValue.total_stake_yen=0;
valid('no positive value => correct explicit zero-budget pass',noValue);
assert.throws(()=>optimizePurchasePortfolio({budget_yen:6100,strategies:small.purchase_strategy_evaluations,
 outcome_distributions:small.outcome_distributions,frame_map:small.frame_map,race_context:small.race_context,freeze_at:small.final_bets_fixed_at}),/6000/);
console.log('v3.10 exact portfolio optimization tests passed');
