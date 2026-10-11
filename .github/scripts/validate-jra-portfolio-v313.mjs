// Formal v3.13 validator: re-prove immutable exact 100-yen v3.12 selection,
// then independently recompute permissible WIN stake sizing and risk metrics.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {validateV312} from './validate-jra-portfolio-v312.mjs';
import {optimizeWinStakeForRecovery} from './jra-win-recovery-stake-shadow-v1.mjs';
import {evaluateStrategy,ticketKey} from './jra-strategy-engine-v39.mjs';
const SC=['low','central','high'];
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const near=(a,b)=>finite(a)&&finite(b)&&Math.abs(a-b)<=Math.max(0.00001,Math.abs(b)*0.000001);
const diff=(a,b)=>JSON.stringify(a)!==JSON.stringify(b);
const equalFields=(x,y,fields,errors,prefix)=>{for(const field of fields)
 if(diff(x?.[field],y?.[field]))errors.push(prefix+' mismatch '+field)};
export function validateV313(data){
 const errors=[],err=s=>errors.push(s);
 if(data?.prompt_version!=='v3.13'){err('expected v3.13 formal prediction');return errors;}
 if(data.stage!=='formal_prestart'||!(/^[a-f0-9]{40}$/.test(data.proof_commit||'')))
  err('formal stage and genuine Git proof required');
 const baseline=data.v312_balanced_baseline;
 if(!baseline||typeof baseline!=='object'){err('missing frozen original 100-yen baseline');return errors;}
 const prev={...data,prompt_version:'v3.12',
   purchase_portfolio_selection:baseline.purchase_portfolio_selection,
   final_bets:baseline.final_bets,total_stake_yen:baseline.total_stake_yen};
 errors.push(...validateV312(prev).map(e=>'v3.12 exact baseline: '+e));
 if(errors.length)return errors;
 const b=baseline.purchase_portfolio_selection;
 let proposal,metrics,old;
 try{
  proposal=optimizeWinStakeForRecovery({
   selected_lines:b.selected_lines,outcome_distributions:data.outcome_distributions,
   frame_map:data.frame_map,race_context:data.race_context,budget_yen:6000
  });
  old=b.selected_lines.length?evaluateStrategy(b.selected_lines,data.outcome_distributions,data.frame_map,data.race_context):null;
  metrics=proposal.selected_lines.length?evaluateStrategy(proposal.selected_lines,data.outcome_distributions,data.frame_map,data.race_context):null;
 }catch(e){err('independent stake-size reconstruction: '+e.message);return errors;}
 const curr=data.purchase_portfolio_selection||{};
 if(data.purchase_budget_yen!==6000||curr.budget_yen!==6000||
   proposal.total_stake_yen>6000)err('budget exceeded or was not 6000');
 if(curr.algorithm!=='v313_balanced_ticket_selection_plus_win_recovery_staking')
   err('not the official v3.13 combined optimizer');
 if(curr.objective!=='v312_ticket_selection_then_maximize_nonloss_with_profit_risk_floor')
   err('v3.13 objective does not specify bounded nonloss optimisation');
 if(data.purchase_decision!==b.purchase_decision||
   data.purchase_reason_code!==b.purchase_reason_code)err('v3.12 purchase decision was altered');
 const p=proposal.selected_lines,chosen=curr.selected_lines||[],f=data.final_bets||[];
 if(chosen.length!==p.length||f.length!==p.length)err('ticket selection count changed');
 const seen=new Set();
 for(let i=0;i<p.length;i++){
  const x=p[i],z=chosen[i]||{},y=f[i]||{},base=b.selected_lines[i];
  const k=ticketKey(x.type,x.selection);
  if(seen.has(k))err('duplicate ticket '+k);seen.add(k);
  if(ticketKey(z.type,z.selection)!==k||ticketKey(y.type,y.selection)!==k)
   err('reordered/missing final ticket '+k);
  if(x.stake_yen!==z.stake_yen||x.stake_yen!==y.stake_yen||
    x.stake_yen%100||x.stake_yen<100||x.stake_yen>1200 && x.type==='単勝')
   err('stake decision disagrees with bounded optimizer '+k);
  if(x.type!=='単勝'&&x.stake_yen!==base.stake_yen)
   err('non-WIN amount changed '+k);
  if(z.market_selection_id!==k||y.market_selection_id!==k||
     diff(z.market_odds,x.market_odds)||diff(y.market_odds,x.market_odds)||
     z.source_url!==x.source_url||y.source_url!==x.source_url||
     z.observed_at!==x.observed_at||y.observed_at!==x.observed_at)
   err('source odds provenance disagrees with frozen baseline '+k);
  const expectedId='B'+String(i+1).padStart(2,'0');
  if(y.id!==expectedId)err('final ticket IDs changed '+k);
 }
 const expected=metrics?.total_stake_yen??0;
 if(curr.total_stake_yen!==expected||data.total_stake_yen!==expected)
   err('final purchase amount mismatched independent calculation');
 if(proposal.selected_lines.length){
  for(const sc of SC){
   for(const field of ['hit_probability_scenarios','expected_payout_yen_scenarios',
    'roi_scenarios','full_loss_probability_scenarios','loss_probability_scenarios']){
     if(!near(curr[field]?.[sc],metrics[field]?.[sc]))err('risk/return metric mismatch '+field+' '+sc);
   }
   if(!near(curr.expected_net_profit_yen_scenarios?.[sc],
    metrics.expected_payout_yen_scenarios[sc]-expected))
    err('expected net profit not recomputed after sizing '+sc);
  }
 }else for(const field of ['expected_payout_yen_scenarios','roi_scenarios','hit_probability_scenarios',
    'full_loss_probability_scenarios','loss_probability_scenarios','expected_net_profit_yen_scenarios'])
  if(curr[field]!==null)err('no-buy portfolio has risk/return metrics '+field);
 const details=data.win_stake_allocation_v313;
 if(details?.algorithm!=='win_recovery_staking_shadow_v1_formally_validated'||
    details?.historical_results_not_used!==true||
    details?.preserve_v312_candidate_mode_comparisons!==true)
   err('formal WIN sizing audit/history-source separation missing');
 const changed=p.some((x,i)=>x.stake_yen!==b.selected_lines[i]?.stake_yen);
 if(details?.activated!==changed)err('sizing activation flag inconsistent');
 if(diff(details?.details,proposal.optimizer_audit))err('sizing audit/probabilities differ');
 const audit=curr.optimizer_audit||{};
 if(diff(audit.balanced_selection,b.optimizer_audit?.balanced_selection))
   err('v3.12 ticket-selection proof changed');
 if(!near(audit.budget_unused_yen,6000-expected)||
    diff(audit.win_stake_sizing,proposal.optimizer_audit))
   err('v3.13 final budget/sizing audit differs');
 if(metrics&&(!near(audit.expected_net_profit_yen,metrics.expected_payout_yen_scenarios.central-expected)||
   !near(audit.lower_scenario_expected_net_profit_yen,metrics.expected_payout_yen_scenarios.low-expected)))
   err('purchase expected profit is stale after stake sizing');
 if(old&&metrics){
  if(!near(metrics.hit_probability_scenarios.central,old.hit_probability_scenarios.central))
   err('bet hit probability changed when only stakes changed');
  const baselineProfit=old.expected_payout_yen_scenarios.central-old.total_stake_yen;
  const newProfit=metrics.expected_payout_yen_scenarios.central-expected;
  const sacrificed=Math.min(200,Math.max(0,baselineProfit)*.10);
  if(newProfit+1e-6<Math.max(1e-9,baselineProfit-sacrificed))
   err('expected profit sacrificed beyond v3.13 guard');
  if(metrics.loss_probability_scenarios.low>old.loss_probability_scenarios.low+.020001)
   err('low-scenario loss probability worsened beyond +2pp');
  if(changed&&(old.loss_probability_scenarios.central-metrics.loss_probability_scenarios.central)<.009999)
   err('did not achieve required ≥1pp improvement in nonloss probability');
 }
 return errors;
}
if(process.argv[1]&&process.argv[1].endsWith('/validate-jra-portfolio-v313.mjs')){
 const candidate=process.argv[2];
 if(!candidate)throw Error('specify ONE prestart v3.13 JSON to validate');
 const d=JSON.parse(fs.readFileSync(candidate,'utf8'));
 const errors=validateV313(d);
 if(errors.length){console.error('JRA_V313_VALIDATION_BLOCKER',errors.join('; '));process.exit(1);}
 console.log('PASS_v313_verified_WIN_100_yen_unit_and_6000_cap',d.race_id,d.total_stake_yen);
}
