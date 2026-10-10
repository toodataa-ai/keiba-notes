// v3.10 purchase-only, deterministic 0/1 budget optimizer (not a probability-model change).
// Each candidate ticket is a pre-generated, independently verified market line.
// Default 100-yen-per-line stake makes diversity possible without invented scaling.
import {TYPES,ticketKey,oddsFloor,matches,evaluateStrategy} from './jra-strategy-engine-v39.mjs';
const SC=['low','central','high'];
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const validTime=x=>typeof x==='string'&&Number.isFinite(Date.parse(x));
const nonempty=x=>typeof x==='string'&&x.trim().length>0;
const close=(x,y)=>Math.abs(x-y)<=Math.max(1e-7,Math.abs(y)*1e-8);
const rounded=n=>Math.round(n*1e9)/1e9;
const must=(p,m)=>{if(!p)throw Error(m);};
const ordered=(a,b)=>a.key.localeCompare(b.key,'en');
function verifyOutcomes(outcomes){
 for(const sc of SC){
  const rows=outcomes?.[sc];
  must(Array.isArray(rows)&&rows.length>0,'missing '+sc+' joint outcomes');
  const seen=new Set();let sum=0;
  for(const o of rows){
   must(Array.isArray(o.finish)&&o.finish.length===3&&new Set(o.finish).size===3&&
    o.finish.every(n=>Number.isInteger(n)&&n>0)&&finite(o.probability)&&o.probability>=0&&o.probability<=1,'invalid joint outcome '+sc);
   const k=JSON.stringify(o.finish);
   must(!seen.has(k),'duplicate joint outcome '+sc);seen.add(k);sum+=o.probability;
  }
  must(close(sum,1),'joint outcome mass not normalized '+sc);
 }
}
function assessLine(line,scenarios,frameMap,race){
 const quote=oddsFloor(line.market_odds);
 must(quote!==null,'cannot assess without actual market quote');
 const probabilities={};
 for(const sc of SC){
  let p=0;
  for(const outcome of scenarios[sc])if(matches(line,outcome.finish,frameMap,race))p+=outcome.probability;
  probabilities[sc]=rounded(p);
 }
 return {
  probabilities,
  ev_multiple:rounded(probabilities.central*quote),
  expected_profit_yen:rounded((probabilities.central*quote-1)*line.stake_yen),
  expected_profit_yen_scenarios:Object.fromEntries(SC.map(sc=>[sc,rounded((probabilities[sc]*quote-1)*line.stake_yen)]))
 };
}
export function buildTicketUniverse({strategies,outcome_distributions,frame_map,race_context,freeze_at,max_ticket_stake_yen=100}){
 must(Array.isArray(strategies),'strategies must be array');
 must(validTime(freeze_at),'freeze timestamp required');
 must(validTime(race_context?.start_at)&&Date.parse(freeze_at)<Date.parse(race_context.start_at),'must freeze before post');
 verifyOutcomes(outcome_distributions);
 must(Number.isInteger(max_ticket_stake_yen)&&max_ticket_stake_yen>=100&&max_ticket_stake_yen%100===0,'invalid per-ticket stake cap');
 const candidates=new Map(),audit={strategy_count:strategies.length,lines_observed:0,unique_tickets:0,duplicates_collapsed:0,unpriced_or_unverified:0,unsupported_or_unoffered:0,positive_edge_count:0,nonpositive_edge_count:0};
 for(const st of strategies){
  must(nonempty(st.strategy_id),'strategy id missing');
  for(const line of st.lines||[]){
   audit.lines_observed++;
   if(!TYPES.includes(line.type)||!race_context?.offered_types?.includes(line.type)){
    audit.unsupported_or_unoffered++;continue;
   }
   let key;
   try{key=ticketKey(line.type,line.selection)}catch{audit.unsupported_or_unoffered++;continue;}
   if(line.quote_verified!==true||oddsFloor(line.market_odds)===null||!validTime(line.observed_at)||
     !nonempty(line.source_url)||line.market_selection_id!==key||Date.parse(line.observed_at)>Date.parse(freeze_at)){
      audit.unpriced_or_unverified++;continue;
   }
   must(Number.isInteger(line.stake_yen)&&line.stake_yen>=100&&line.stake_yen%100===0,'invalid original ticket stake');
   // Ignore increased allocations unless a separate explicit fixed 100-yen multiplier decision is audited.
   if(line.stake_yen>max_ticket_stake_yen){audit.unsupported_or_unoffered++;continue;}
   if(candidates.has(key)){
    const x=candidates.get(key);
    must(JSON.stringify(x.selection)===JSON.stringify(line.selection),'conflicting selection normalization');
    must(x.stake_yen===line.stake_yen&&JSON.stringify(x.market_odds)===JSON.stringify(line.market_odds)&&
      x.observed_at===line.observed_at&&x.source_url===line.source_url,
      'same ticket quoted inconsistently between strategy sources');
    if(!x.origin_strategy_ids.includes(st.strategy_id))x.origin_strategy_ids.push(st.strategy_id);
    audit.duplicates_collapsed++;continue;
   }
   const prepared={key,type:line.type,selection:line.selection,stake_yen:line.stake_yen,
     market_odds:line.market_odds,market_selection_id:key,source_url:line.source_url,
     observed_at:line.observed_at,quote_verified:true,origin_strategy_ids:[st.strategy_id]};
   Object.assign(prepared,assessLine(prepared,outcome_distributions,frame_map,race_context));
   candidates.set(key,prepared);
 }
 }
 const all=[...candidates.values()].sort(ordered);
 audit.unique_tickets=all.length;
 audit.positive_edge_count=all.filter(t=>t.expected_profit_yen>0).length;
 audit.nonpositive_edge_count=all.filter(t=>t.expected_profit_yen<=0).length;
 return {all,audit};
}
// Exact 0/1 integer knapsack. Aim = max CENTRAL expected net profit,
// never highest ROI or payout, with secondary lower-scenario profit and lower stake.
// No arbitrary investment of unspent cash and no retrospective outcome awareness.
export function optimizePurchasePortfolio(args){
 const budget=args.budget_yen??6000;
 must(Number.isInteger(budget)&&budget>=100&&budget%100===0,'budget needs 100-yen units');
 must(budget<=6000||args.budget_source==='user_override','budget >6000 not authorized');
 const {all,audit}=buildTicketUniverse({...args,max_ticket_stake_yen:args.max_ticket_stake_yen??100});
 const eligible=all.filter(t=>t.expected_profit_yen>0);
 const excluded=all.filter(t=>t.expected_profit_yen<=0).map(t=>({key:t.key,reason:'nonpositive modeled central expected net profit'}));
 const capacity=budget/100,dp=Array(capacity+1).fill(null);
 dp[0]={profit:0,low_profit:0,spent:0,keys:[]};
 // Descending weight capacity prevents re-using a ticket twice.
 for(const t of eligible){
  const w=t.stake_yen/100;
  for(let k=capacity;k>=w;k--){
   const prev=dp[k-w];if(!prev)continue;
   const candidate={profit:prev.profit+t.expected_profit_yen,
    low_profit:prev.low_profit+t.expected_profit_yen_scenarios.low,
    spent:prev.spent+t.stake_yen,keys:[...prev.keys,t.key]};
   const old=dp[k];
   if(!old||candidate.profit>old.profit+1e-8||
     (close(candidate.profit,old.profit)&&candidate.low_profit>old.low_profit+1e-8)||
     (close(candidate.profit,old.profit)&&close(candidate.low_profit,old.low_profit)&&candidate.keys.join('|')<old.keys.join('|')))
     dp[k]=candidate;
  }
 }
 const optimum=dp.filter(Boolean).reduce((best,p)=>!best||
  p.profit>best.profit+1e-8||
  (close(p.profit,best.profit)&&p.low_profit>best.low_profit+1e-8)||
  (close(p.profit,best.profit)&&close(p.low_profit,best.low_profit)&&p.spent<best.spent)?p:best,null);
 const selected=optimum.keys.map(k=>all.find(t=>t.key===k));
 const totals=selected.length?evaluateStrategy(selected,args.outcome_distributions,args.frame_map,args.race_context):
  {total_stake_yen:0,hit_probability_scenarios:null,expected_payout_yen_scenarios:null,roi_scenarios:null,full_loss_probability_scenarios:null,loss_probability_scenarios:null};
 const selectedKeys=new Set(optimum.keys);
 return {
  algorithm:'exact_zero_one_knapsack_v1',objective:'maximize_central_expected_net_profit_yen',
  budget_yen:budget,purchase_decision:selected.length?'buy':'pass',
  purchase_reason_code:selected.length?'bought':all.length?'no_value':'insufficient_local_information',
  selected_lines:selected,
  optimizer_audit:{...audit,eligible_count:eligible.length,selected_count:selected.length,
   considered_excluded:excluded,positive_edge_not_selected:eligible.filter(t=>!selectedKeys.has(t.key)).map(t=>t.key),
   expected_net_profit_yen:rounded(optimum.profit),lower_scenario_expected_net_profit_yen:rounded(optimum.low_profit),
   budget_unused_yen:budget-totals.total_stake_yen,
   selection_objective_note:'Maximum total central net expected profit under budget, no compulsory spending; per ticket amount fixed before optimization'},
  ...totals
 };
}
