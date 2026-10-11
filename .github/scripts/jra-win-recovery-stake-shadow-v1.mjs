// Optional STEP2 staking research, separate from the SHA-frozen v3.12 formal
// forecast. Never reprice past bets or mutate a sealed final_bets array.
// Minimize modeled net-loss probability, not "make every winner profitable".
import {ticketKey, oddsFloor, evaluateStrategy} from './jra-strategy-engine-v39.mjs';

export const RECOVERY_STAKE_POLICY = Object.freeze({
  budget_yen:6000,
  yen_step:100,
  max_win_stake_yen:1200,
  min_nonloss_gain:0.01,
  max_low_scenario_net_loss_increase:0.02,
  max_expected_profit_sacrifice_ratio:0.10,
  max_expected_profit_sacrifice_yen:200,
  max_low_scenario_expected_profit_sacrifice_yen:200,
  max_rounds:4
});
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const profit=(s,scenario)=>s.expected_payout_yen_scenarios[scenario]-s.total_stake_yen;
const near=(a,b)=>Math.abs(a-b)<=1e-8;
const fmtKey=x=>ticketKey(x.type,x.selection);
const winRows=lines=>lines.filter(x=>x.type==='単勝'&&
  x.quote_verified===true&&oddsFloor(x.market_odds)!==null);

function stats(lines,scenario,frame,race){
 return evaluateStrategy(lines,scenario,frame,race);
}

export function optimizeWinStakeForRecovery({
 selected_lines,outcome_distributions,frame_map,race_context,
 budget_yen=6000,policy=RECOVERY_STAKE_POLICY
}){
 if(!Array.isArray(selected_lines)||!Array.isArray(outcome_distributions?.central)||
   !Array.isArray(outcome_distributions?.low)||!Array.isArray(outcome_distributions?.high)||
   !race_context||!frame_map)throw Error('stake sizing BLOCKER: full independent prestart outcomes required');
 if(!Number.isInteger(budget_yen)||budget_yen<100||budget_yen>6000||
   budget_yen%100)throw Error('stake sizing BLOCKER: budget must be 100..6000 in 100-yen units');
 const original=selected_lines.map(x=>({...x}));
 const ids=new Set();
 for(const x of original){
  const k=fmtKey(x);
  if(ids.has(k))throw Error('stake sizing BLOCKER: duplicated final ticket');
  ids.add(k);
  if(!Number.isInteger(x.stake_yen)||x.stake_yen<100||x.stake_yen%100||
      oddsFloor(x.market_odds)===null||x.quote_verified!==true)
   throw Error('stake sizing BLOCKER: ticket requires verified odds and 100-yen stake');
 }
 const stake=original.reduce((a,x)=>a+x.stake_yen,0);
 if(stake>budget_yen)throw Error('stake sizing BLOCKER: baseline exceeds budget');
 if(!original.length)return {
   selected_lines:[],total_stake_yen:0,algorithm:'win_recovery_staking_shadow_v1',
   activated:false,reason:'no_selected_bets',optimizer_audit:{original_stake_yen:0,new_stake_yen:0}};
 const base=stats(original,outcome_distributions,frame_map,race_context);
 const baselineProfit=profit(base,'central'),baseLow=profit(base,'low');
 const floor=Math.max(0.000000001,
   baselineProfit-Math.min(policy.max_expected_profit_sacrifice_yen,
                          Math.max(0,baselineProfit)*policy.max_expected_profit_sacrifice_ratio));
 const lowFloor=baseLow-policy.max_low_scenario_expected_profit_sacrifice_yen;
 const baselineRecovery=1-base.loss_probability_scenarios.central;
 const eligible=winRows(original).filter(x=>x.probabilities?.central*oddsFloor(x.market_odds)>1);
 const winBreakEven=winRows(original).map(x=>{
   const other=stake-x.stake_yen;
   const odds=oddsFloor(x.market_odds);
   const target=Math.max(100,Math.ceil(other/(odds-1)/100)*100);
   return {ticket_key:fmtKey(x),actual_market_odds_conservative:odds,
     modeled_win_probability:x.probabilities?.central??null,
     current_stake_yen:x.stake_yen,
     win_only_break_even_stake_yen:target,
     attainable_under_single_ticket_cap:target<=policy.max_win_stake_yen,
     note:'Conservative isolated-win threshold; actual portfolio recovery uses joint finish distributions'};
 });
 let current=original, metrics=base, rounds=0, evaluated=0;
 // Fixed ticket selection; only add 100-yen steps to positively priced win bets.
 // Evaluate the ENTIRE cross-type portfolio for every proposed stake.
 if(baselineProfit>0&&eligible.length){
  const ticketIds=new Set(eligible.map(fmtKey));
  for(let round=0;round<policy.max_rounds;round++){
   let best=null;
   for(let index=0;index<current.length;index++){
    const row=current[index],id=fmtKey(row);
    if(!ticketIds.has(id))continue;
    const otherStake=current.reduce((a,b,i)=>a+(i===index?0:b.stake_yen),0);
    const max=Math.min(policy.max_win_stake_yen,budget_yen-otherStake);
    for(let amount=row.stake_yen+100;amount<=max;amount+=100){
      const trial=current.map((x,i)=>i===index?{...x,stake_yen:amount}:x);
      const m=stats(trial,outcome_distributions,frame_map,race_context);evaluated++;
      const earned=profit(m,'central');
      if(earned+1e-8<floor||profit(m,'low')+1e-8<lowFloor)continue;
      if(m.loss_probability_scenarios.low>
        base.loss_probability_scenarios.low+policy.max_low_scenario_net_loss_increase+1e-8)continue;
      const gain=(1-m.loss_probability_scenarios.central)-baselineRecovery;
      if(gain<policy.min_nonloss_gain-1e-8)continue;
      const candidate={trial,m,gain,earned,spent:m.total_stake_yen,key:id};
      if(!best||candidate.gain>best.gain+1e-8||
         (near(candidate.gain,best.gain)&&
           (candidate.earned>best.earned+1e-8||
            (near(candidate.earned,best.earned)&&candidate.spent<best.spent)||
            (near(candidate.earned,best.earned)&&candidate.spent===best.spent&&candidate.key<best.key))))
        best=candidate;
    }
   }
   if(!best||best.gain<((1-metrics.loss_probability_scenarios.central)-baselineRecovery)+1e-8)
     break;
   current=best.trial;metrics=best.m;rounds++;
  }
 }
 const changed=current.some((x,i)=>x.stake_yen!==original[i].stake_yen);
 // The proposed change has one independently auditable number per final ticket.
 const adjusted=current.map((x,i)=>{
   const p=original[i];
   const ratio=x.stake_yen/p.stake_yen;
   if(ratio===1)return {...x};
   return {...x,
     expected_profit_yen:finite(p.expected_profit_yen)?p.expected_profit_yen*ratio:p.expected_profit_yen,
     expected_profit_yen_scenarios:p.expected_profit_yen_scenarios?
       Object.fromEntries(Object.entries(p.expected_profit_yen_scenarios).map(([k,v])=>[k,v*ratio])):undefined
   };
 });
 if(adjusted.reduce((n,x)=>n+x.stake_yen,0)!==metrics.total_stake_yen||
   adjusted.some((x,i)=>fmtKey(x)!==fmtKey(original[i]))||
   metrics.total_stake_yen>budget_yen)
   throw Error('stake sizing BLOCKER: budget or immutable ticket identity mismatch');
 if(changed&&((1-metrics.loss_probability_scenarios.central)-baselineRecovery<
    policy.min_nonloss_gain-1e-8||profit(metrics,'central')<floor-1e-8))
   throw Error('stake sizing BLOCKER: risk/recovery improvement policy violated');
 return {
  algorithm:'win_recovery_staking_shadow_v1',
  activated:false,
  reason:changed?'modeled_nonloss_probability_increased':'no_safe_material_recovery_improvement',
  selected_lines:adjusted,
  total_stake_yen:metrics.total_stake_yen,
  hit_probability_scenarios:metrics.hit_probability_scenarios,
  loss_probability_scenarios:metrics.loss_probability_scenarios,
  expected_net_profit_yen_scenarios:Object.fromEntries(['low','central','high'].map(s=>[s,profit(metrics,s)])),
  optimizer_audit:{
    baseline_total_stake_yen:stake,proposed_total_stake_yen:metrics.total_stake_yen,
    baseline_modeled_recovery_probability:baselineRecovery,
    proposed_modeled_recovery_probability:1-metrics.loss_probability_scenarios.central,
    hit_probability_unchanged:near(base.hit_probability_scenarios.central,
                                   metrics.hit_probability_scenarios.central),
    baseline_expected_profit_yen:baselineProfit,
    proposed_expected_profit_yen:profit(metrics,'central'),
    baseline_lower_scenario_expected_profit_yen:baseLow,
    proposed_lower_scenario_expected_profit_yen:profit(metrics,'low'),
    baseline_loss_probability_low:base.loss_probability_scenarios.low,
    proposed_loss_probability_low:metrics.loss_probability_scenarios.low,
    required_expected_profit_floor_yen:floor,
    selected_line_count_unchanged:adjusted.length===original.length,
    only_win_ticket_amount_changed:adjusted.every((x,i)=>
      x.type==='単勝'||x.stake_yen===original[i].stake_yen),
    budget_unused_yen:budget_yen-metrics.total_stake_yen,
    trials_evaluated:evaluated,improvement_rounds:rounds,
    win_break_even_thresholds:winBreakEven,
    optimality:'deterministic_limited_neighborhood_not_global',
    base_probability_model_calibrated:false,
    odds_used_as_observed_at_freeze_only:true
  }
 };
}
