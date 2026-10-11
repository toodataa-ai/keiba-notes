// Post-race replay of immutable PRESTART inputs: no finished-order/settlement reads.
// Reports changed stake proposals only; never edits historical predictions.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {optimizeWinStakeForRecovery} from './jra-win-recovery-stake-shadow-v1.mjs';
import {evaluateStrategy} from './jra-strategy-engine-v39.mjs';
const SC=['low','central','high'];
const files=[
 'e2e_validation/predictions/2026-10-11-ireland-trophy/v3.12-rerun38113832729-attempt1.json',
 'e2e_validation/predictions/2026-10-11-uzumasa-stakes/v3.12-rerun38113827050-attempt2.json'
];
const reports=[];
for(const file of files){
 const text=fs.readFileSync(file,'utf8'),data=JSON.parse(text);
 assert.equal(data.prompt_version,'v3.12');
 assert.equal(data.stage,'formal_prestart');
 assert(Date.parse(data.final_bets_fixed_at)<Date.parse(data.race_context.start_at));
 assert.equal(data.purchase_budget_yen,6000);
 const initial=data.purchase_portfolio_selection.selected_lines;
 const base=evaluateStrategy(initial,data.outcome_distributions,data.frame_map,data.race_context);
 const result=optimizeWinStakeForRecovery({
  selected_lines:initial,outcome_distributions:data.outcome_distributions,
  frame_map:data.frame_map,race_context:data.race_context,budget_yen:6000
 });
 const final=evaluateStrategy(result.selected_lines,data.outcome_distributions,data.frame_map,data.race_context);
 const calc=(s,scenario)=>s.expected_payout_yen_scenarios[scenario]-s.total_stake_yen;
 const record={
  race_id:data.race_id,source_immutable_prediction:file,
  replay_mode:'prestart_only_shadow_counterfactual_no_final_result_usage',
  base_bets:initial.length,proposed_bets:result.selected_lines.length,
  base_total_yen:base.total_stake_yen,proposed_total_yen:final.total_stake_yen,
  baseline_central_expected_profit_yen:calc(base,'central'),
  proposed_central_expected_profit_yen:calc(final,'central'),
  baseline_central_hit_probability:base.hit_probability_scenarios.central,
  proposed_central_hit_probability:final.hit_probability_scenarios.central,
  baseline_central_nonloss_probability:1-base.loss_probability_scenarios.central,
  proposed_central_nonloss_probability:1-final.loss_probability_scenarios.central,
  baseline_low_net_loss_probability:base.loss_probability_scenarios.low,
  proposed_low_net_loss_probability:final.loss_probability_scenarios.low,
  conservative_live_quote_win_adjustments:result.selected_lines.filter((x,i)=>x.type==='単勝').map(x=>{
    const was=initial.find(y=>y.type===x.type&&JSON.stringify(y.selection)===JSON.stringify(x.selection));
    return {horse_number:x.selection[0],observed_odds:x.market_odds,base_yen:was.stake_yen,proposed_yen:x.stake_yen};
  }),
  trials:result.optimizer_audit?.trials_evaluated||0,
  improvement_rounds:result.optimizer_audit?.improvement_rounds||0
 };
 assert(record.proposed_total_yen<=6000);
 assert.equal(record.base_bets,record.proposed_bets);
 assert.equal(record.baseline_central_hit_probability,record.proposed_central_hit_probability);
 assert(record.proposed_low_net_loss_probability<=record.baseline_low_net_loss_probability+0.02000001);
 assert(result.selected_lines.every((x,i)=>x.type==='単勝'||x.stake_yen===initial[i].stake_yen));
 assert(result.selected_lines.every((x,i)=>x.type===initial[i].type&&JSON.stringify(x.selection)===JSON.stringify(initial[i].selection)));
 assert.equal(fs.readFileSync(file,'utf8'),text,'immutable source file changed');
 reports.push(record);
 console.log('LIVE_RACE_PRESTART_REPLAY',JSON.stringify(record));
}
fs.mkdirSync('jra-v313-replay-artifacts',{recursive:true});
fs.writeFileSync('jra-v313-replay-artifacts/prestart-stakes-comparison.json',
 JSON.stringify({schema_version:1,scope:'historical_prestart_only_shadows',runs:reports},null,2)+'\n');
console.log('PASS 2 sealed prestart real-race stake comparisons with immutable sources');
