// v3.11: bounded risk-aware overlay; frozen v3.10 exact profit baseline is never modified.
// Do not claim global multi-objective optimality: this deterministic neighbourhood search is audited.
import {buildTicketUniverse,optimizePurchasePortfolio} from './jra-portfolio-optimizer-v310.mjs';
import {ticketKey,matches,evaluateStrategy} from './jra-strategy-engine-v39.mjs';
const SC=['low','central','high'];
const key=t=>ticketKey(t.type,t.selection);
const round=x=>Math.round(x*1e9)/1e9;
const EPS=1e-9;
export const BALANCE_POLICY=Object.freeze({
  max_expected_profit_sacrifice_ratio:0.10,
  max_expected_profit_sacrifice_yen:200,
  max_net_loss_probability_increase:0.02,
  minimum_hit_probability_gain:0.01,
  max_rounds:3,
  max_proposals_per_round:12
});
function stats(items,args){
  if(!items.length)return {total_stake_yen:0,hit_probability_scenarios:null,expected_payout_yen_scenarios:null,
    roi_scenarios:null,full_loss_probability_scenarios:null,loss_probability_scenarios:null,
    expected_net_profit_yen_scenarios:null};
  const s=evaluateStrategy(items,args.outcome_distributions,args.frame_map,args.race_context);
  s.expected_net_profit_yen_scenarios=Object.fromEntries(SC.map(sc=>[sc,round(s.expected_payout_yen_scenarios[sc]-s.total_stake_yen)]));
  return s;
}
export function optimizeBalancedPortfolio(args){
  const baseline=optimizePurchasePortfolio(args);
  const {all,audit}=buildTicketUniverse({...args,max_ticket_stake_yen:args.max_ticket_stake_yen??100});
  const baselineStats=stats(baseline.selected_lines,args);
  const baselineProfit=baselineStats.expected_net_profit_yen_scenarios?.central??0;
  const baseHit=baselineStats.hit_probability_scenarios?.central??0;
  const baseLoss=baselineStats.loss_probability_scenarios?.central??0;
  const sacrifice=Math.min(baselineProfit*BALANCE_POLICY.max_expected_profit_sacrifice_ratio,
    BALANCE_POLICY.max_expected_profit_sacrifice_yen);
  const floor=Math.max(EPS,baselineProfit-sacrifice);
  const byKey=new Map(all.map(t=>[key(t),t]));
  let selection=[...baseline.selected_lines],current=baselineStats,rounds=0,evaluations=0;
  // Selection data are pure pre-start probabilities and individually sourced market quotes.
  const states=args.outcome_distributions.central;
  const probs=Float64Array.from(states.map(x=>x.probability));
  const flags=new Map();
  for(const t of all){
    const f=new Uint8Array(states.length);
    for(let i=0;i<states.length;i++)
      if(matches(t,states[i].finish,args.frame_map,args.race_context))f[i]=1;
    flags.set(key(t),f);
  }
  if(baselineProfit>EPS){
    for(let iteration=0;iteration<BALANCE_POLICY.max_rounds;iteration++){
      const active=new Set(selection.map(key));
      const counts=new Uint16Array(states.length);
      for(const t of selection){const bits=flags.get(key(t));for(let i=0;i<bits.length;i++)counts[i]+=bits[i];}
      const options=[],currentHit=current.hit_probability_scenarios.central;
      for(const candidate of all){
        const candidateKey=key(candidate);
        if(active.has(candidateKey))continue;
        // An extreme negative-value ticket cannot be rescued solely by higher hit probability.
        if(candidate.expected_profit_yen < -sacrifice)continue;
        const addBits=flags.get(candidateKey);
        const removals=selection.length>=args.budget_yen/100?[...selection]:[null,...selection];
        for(const removed of removals){
          const newStake=current.total_stake_yen+candidate.stake_yen-(removed?.stake_yen??0);
          if(newStake>args.budget_yen||newStake<=0)continue;
          const profit=(current.expected_net_profit_yen_scenarios?.central??0)+candidate.expected_profit_yen-(removed?.expected_profit_yen??0);
          if(profit+EPS<floor)continue;
          const removeBits=removed?flags.get(key(removed)):null;
          let hit=0;
          for(let i=0;i<states.length;i++){
            if(counts[i]-(removeBits?.[i]??0)+addBits[i]>0)hit+=probs[i];
          }
          if(hit<=currentHit+0.000001)continue;
          options.push({candidate,removed,hit,profit,newStake});
        }
      }
      options.sort((a,b)=>b.hit-a.hit||b.profit-a.profit||
        key(a.candidate).localeCompare(key(b.candidate))||
        (a.removed?key(a.removed):'').localeCompare(b.removed?key(b.removed):''));
      let best=null,bestScore=-Infinity;
      for(const x of options.slice(0,BALANCE_POLICY.max_proposals_per_round)){
        const trial=selection.filter(t=>!x.removed||key(t)!==key(x.removed)).concat(x.candidate).sort((a,b)=>key(a).localeCompare(key(b)));
        const m=stats(trial,args);evaluations++;
        const profit=m.expected_net_profit_yen_scenarios.central;
        const hit=m.hit_probability_scenarios.central,loss=m.loss_probability_scenarios.central;
        if(profit+EPS<floor||profit<=0||loss>baseLoss+BALANCE_POLICY.max_net_loss_probability_increase+EPS)continue;
        const score=hit+0.30*(baseLoss-loss);
        const tie=best?score>bestScore+EPS||
          (Math.abs(score-bestScore)<=EPS&&(hit>best.m.hit_probability_scenarios.central+EPS||
          (Math.abs(hit-best.m.hit_probability_scenarios.central)<=EPS&&profit>best.m.expected_net_profit_yen_scenarios.central+EPS))):true;
        if(tie){best={trial,m};bestScore=score;}
      }
      if(!best||best.m.hit_probability_scenarios.central<=currentHit+EPS)break;
      selection=best.trial;current=best.m;rounds++;
    }
  }
  // Require a material gain; otherwise the exact expected-profit baseline wins.
  if(!selection.length||!baseline.selected_lines.length||
    (current.hit_probability_scenarios.central-baseHit)<BALANCE_POLICY.minimum_hit_probability_gain-EPS){
    selection=[...baseline.selected_lines];current=baselineStats;rounds=0;
  }
  const selectedKeys=new Set(selection.map(key));
  const excluded=all.filter(t=>!selectedKeys.has(key(t))).map(t=>({
    key:key(t),type:t.type,selection:t.selection,market_odds:t.market_odds,
    probability:t.probabilities?.central,expected_profit_yen:t.expected_profit_yen,
    reason_code:t.expected_profit_yen<=0?'nonpositive_individual_expected_profit':
      'not_selected_by_balanced_portfolio',
    reason:t.expected_profit_yen<=0?
      '個別期待利益が0円以下。ヘッジ効果も購入セットの制約内で採用されなかった。':
      '期待利益・集合的中率・実損率・予算の同時制約では最終集合から外れた。'
  }));
  const selectedHedges=selection.filter(t=>t.expected_profit_yen<=0).map(t=>key(t));
  const selectedCount=selection.length;
  const built={...baseline,...current,
    algorithm:'bounded_risk_neighbourhood_v1',
    objective:'maximize_union_hit_with_profit_floor_and_loss_risk_guard',
    selected_lines:selection,
    purchase_decision:selectedCount?'buy':'pass',
    purchase_reason_code:selectedCount?'bought':baseline.purchase_reason_code,
    optimizer_audit:{...audit,eligible_count:all.filter(t=>t.expected_profit_yen>0).length,
      selected_count:selectedCount,budget_unused_yen:args.budget_yen-current.total_stake_yen,
      expected_net_profit_yen:round(current.expected_net_profit_yen_scenarios?.central??0),
      lower_scenario_expected_net_profit_yen:round(current.expected_net_profit_yen_scenarios?.low??0),
      considered_excluded:excluded,positive_edge_not_selected:excluded.filter(t=>t.expected_profit_yen>0).map(t=>t.key),
      balanced_selection:{optimality:'heuristic_risk_neighbourhood_not_global',
        baseline_is_exact_profit_optimum:true,baseline_expected_profit_yen:round(baselineProfit),
        baseline_hit_probability:round(baseHit),baseline_net_loss_probability:round(baseLoss),
        expected_profit_floor_yen:round(floor),expected_profit_sacrifice_yen:round(Math.max(0,baselineProfit-(current.expected_net_profit_yen_scenarios?.central??0))),
        hit_probability_gain:round((current.hit_probability_scenarios?.central??0)-baseHit),
        net_loss_probability_change:round((current.loss_probability_scenarios?.central??0)-baseLoss),
        selection_rounds:rounds,correlated_portfolios_evaluated:evaluations,
        selected_nonpositive_individual_tickets:selectedHedges,
        not_a_promise_of_real_world_probability:true,
        policy:BALANCE_POLICY}
    }
  };
  if(!selectedCount){built.expected_net_profit_yen_scenarios=null;}
  return built;
}
