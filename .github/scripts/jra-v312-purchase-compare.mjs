// v3.12 STEP2-only comparative purchase-set audit and improvement search.
// STEP1, frozen historical predictions and the v3.11 baseline algorithm remain untouched.
// This is a deterministic, auditable local search, NOT a globally optimal portfolio solver.
import {buildTicketUniverse} from './jra-portfolio-optimizer-v310.mjs';
import {optimizeBalancedPortfolio} from './jra-balanced-optimizer-v311.mjs';
import {ticketKey,matches,evaluateStrategy,oddsFloor} from './jra-strategy-engine-v39.mjs';
const EPS=1e-9, SC=['low','central','high'];
const round=n=>Math.round(n*1e9)/1e9;
const key=t=>ticketKey(t.type,t.selection);
function measure(lines,args){
 if(!lines.length)return {total_stake_yen:0,hit_probability_scenarios:null,loss_probability_scenarios:null,
  full_loss_probability_scenarios:null,expected_payout_yen_scenarios:null,roi_scenarios:null,
  expected_net_profit_yen_scenarios:null};
 const x=evaluateStrategy(lines,args.outcome_distributions,args.frame_map,args.race_context);
 return {...x,expected_net_profit_yen_scenarios:Object.fromEntries(SC.map(s=>[s,round(x.expected_payout_yen_scenarios[s]-x.total_stake_yen)]))};
}
function summarize(label,lines,args,baseline=false){
 const m=measure(lines,args);
 return {label,stake_yen:m.total_stake_yen,ticket_count:lines.length,
  hit_probability_scenarios:m.hit_probability_scenarios,
  expected_net_profit_yen_scenarios:m.expected_net_profit_yen_scenarios,
  net_loss_probability_scenarios:m.loss_probability_scenarios,
  roi_scenarios:m.roi_scenarios,selected_keys:lines.map(key),baseline};
}
function winBits(lines,args){
 const states=args.outcome_distributions.central;
 const flags=new Uint8Array(states.length);
 for(const t of lines)for(let j=0;j<states.length;j++)
  if(matches(t,states[j].finish,args.frame_map,args.race_context))flags[j]=1;
 return flags;
}
function marginalOrder(lines,args){
 const ordered=[],used=new Set(),flags=new Map(lines.map(t=>[key(t),winBits([t],args)]));
 const states=args.outcome_distributions.central,covered=new Uint8Array(states.length);
 while(ordered.length<lines.length){
  let best=null,bestGain=-1;
  for(const t of lines){
   if(used.has(key(t)))continue;
   const f=flags.get(key(t));let gain=0;
   for(let i=0;i<states.length;i++)if(f[i]&&!covered[i])gain+=states[i].probability;
   if(gain>bestGain+EPS||(Math.abs(gain-bestGain)<=EPS&&best&&key(t)<key(best))){
    best=t;bestGain=gain;
   }
  }
  used.add(key(best));ordered.push(best);
  const f=flags.get(key(best));for(let i=0;i<states.length;i++)if(f[i])covered[i]=1;
 }
 return ordered;
}
export function optimizeAndCompareV312(args){
 const baseline=optimizeBalancedPortfolio(args);
 const {all}=buildTicketUniverse({...args,max_ticket_stake_yen:100});
 const b=baseline.optimizer_audit.balanced_selection;
 const baseProfit=b.baseline_expected_profit_yen;
 const floor=b.expected_profit_floor_yen;
 const allowedLoss=b.baseline_net_loss_probability+0.02;
 let selected=[...baseline.selected_lines],current=measure(selected,args);
 const stats={candidate_count:all.length,attempted_add_or_swap:0,economic_feasible:0,
  correlated_evaluated:0,risk_rejected:0,no_hit_gain:0,improvements_applied:0};
 // Full single-ticket addition and one-ticket replacement over all actual priced tickets,
 // rather than first discarding every candidate without a marginal union-hit gain.
 // Two-ticket combined swaps remain outside the heuristic's claimed coverage.
 if(baseProfit>EPS){
  for(let roundNo=0;roundNo<3;roundNo++){
   const present=new Set(selected.map(key));
   let best=null;
   for(const candidate of all){
    if(present.has(key(candidate)))continue;
    for(const removed of [null,...selected]){
     stats.attempted_add_or_swap++;
     const proposed=selected.filter(t=>!removed||key(t)!==key(removed)).concat(candidate);
     const investment=proposed.reduce((sum,t)=>sum+t.stake_yen,0);
     if(investment>args.budget_yen)continue;
     const approx=(current.expected_net_profit_yen_scenarios?.central||0)+candidate.expected_profit_yen-(removed?.expected_profit_yen||0);
     if(approx+EPS<floor||approx<=0)continue;
     stats.economic_feasible++;
     const m=measure(proposed,args);
     stats.correlated_evaluated++;
     if(m.loss_probability_scenarios.central>allowedLoss+EPS){stats.risk_rejected++;continue;}
     const gain=m.hit_probability_scenarios.central-(current.hit_probability_scenarios?.central||0);
     if(gain<=EPS){stats.no_hit_gain++;continue;}
     // Maximize union hit probability, then maximize net expected profit.
     if(!best||gain>best.gain+EPS||
       (Math.abs(gain-best.gain)<=EPS&&m.expected_net_profit_yen_scenarios.central>best.metrics.expected_net_profit_yen_scenarios.central+EPS))
       best={proposed,metrics:m,gain};
    }
   }
   if(!best)break;
   selected=best.proposed.sort((x,y)=>key(x).localeCompare(key(y)));
   current=best.metrics;
   stats.improvements_applied++;
  }
 }
 const baseHit=b.baseline_hit_probability;
 const realGain=(current.hit_probability_scenarios?.central||0)-baseHit;
 if(realGain<0.01-EPS){
  selected=[...baseline.selected_lines];current=measure(selected,args);
  stats.reverted_below_min_gain=true;
 }
 const selectedKeys=new Set(selected.map(key));
 const excluded=all.filter(t=>!selectedKeys.has(key(t))).map(t=>({
  key:key(t),type:t.type,selection:t.selection,market_odds:t.market_odds,probability:t.probabilities?.central,
  expected_profit_yen:t.expected_profit_yen,reason_code:t.expected_profit_yen<=0?
   'nonpositive_individual_expected_profit':'not_selected_by_balanced_portfolio',
  reason:t.expected_profit_yen<=0?'個別EV非正かつ集合制約内で不採用':'最終購入集合の制約・重複的中比較で不採用'}));
 const greedy=marginalOrder(selected,args);
 const subsets=[1,3,5,10].filter(n=>n<selected.length).map(n=>
  summarize('採用集合の的中寄与上位'+n+'点',greedy.slice(0,n),args));
 subsets.push(summarize('最終購入集合（全件）',selected,args));
 const strategySets=[];
 for(const st of args.strategies||[]){
  const dedup=new Map();
  for(const t of st.lines||[]){
   if(!t.quote_verified||oddsFloor(t.market_odds)===null)continue;
   dedup.set(key(t),t);
  }
  const lines=[...dedup.values()];
  if(!lines.length)continue;
  const total=lines.reduce((a,t)=>a+t.stake_yen,0);
  if(total>args.budget_yen){strategySets.push({strategy_id:st.strategy_id,type:st.type,mode:st.strategy_kind,
   status:'over_budget',ticket_count:lines.length,stake_yen:total});continue;}
  if(lines.length!==(st.lines||[]).length){
   strategySets.push({strategy_id:st.strategy_id,type:st.type,mode:st.strategy_kind,
    status:'partial_odds',ticket_count:(st.lines||[]).length,priced_count:lines.length});continue;
  }
  strategySets.push({strategy_id:st.strategy_id,type:st.type,mode:st.strategy_kind,status:'compared',
   ...summarize('方式比較',lines,args)});
 }
 const audit={
  method:'exhaustive_single_add_or_swap_from_verified_universe_three_rounds_not_global',
  comparisons_performed:stats.correlated_evaluated,
  screened:stats,
  baseline:summarize('v3.10 厳密最大期待利益解（v3.11 audit reference）',baseline.selected_lines,args,true),
  final:summarize('v3.12 最終採用集合',selected,args),
  incremental_hit_subsets:subsets,
  strategy_mode_comparisons:strategySets,
  active_constraints:{expected_profit_floor_yen:floor,max_net_loss_probability:allowedLoss,
   minimum_absolute_hit_gain:0.01,budget_yen:args.budget_yen},
  zero_trial_explanation:stats.correlated_evaluated!==0?null:(
   stats.candidate_count===selected.length?'全価格確認済み候補が既に採用集合に含まれる':
   stats.economic_feasible===0?'利益下限と購入予算の制約を満たす追加・入替候補がない':
   '実損制約などの評価条件により代替集合が見つからない'),
  limitation:'比較は券種別方式の候補と単点追加・単点入替。多点同時交換の大域最適性は証明していない。',
  not_calibrated:true
 };
 const prior=baseline.optimizer_audit;
 const portfolio={...baseline,...current,algorithm:'v312_single_swap_audited_neighbourhood',
  selected_lines:selected,optimizer_audit:{...prior,selected_count:selected.length,
   budget_unused_yen:args.budget_yen-current.total_stake_yen,
   expected_net_profit_yen:round(current.expected_net_profit_yen_scenarios?.central||0),
   considered_excluded:excluded,positive_edge_not_selected:excluded.filter(t=>t.expected_profit_yen>0).map(t=>t.key),
   v312_purchase_comparison:audit}};
 portfolio.purchase_decision=selected.length?'buy':'pass';
 portfolio.purchase_reason_code=selected.length?'bought':baseline.purchase_reason_code;
 return portfolio;
}