// v3.13 JRA formal purchase-stake stage.
// SHA-frozen v3.12 STEP1, odds, and selected ticket IDs remain byte-equivalent;
// only WIN amounts may increase when whole-portfolio loss/EV guards prove value.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import {assemble as assembleV312} from './jra-prestart-pipeline-v312.mjs';
import {optimizeWinStakeForRecovery} from './jra-win-recovery-stake-shadow-v1.mjs';
import {evaluateStrategy, ticketKey} from './jra-strategy-engine-v39.mjs';
import {validateV313} from './validate-jra-portfolio-v313.mjs';
const SC=['low','central','high'];
const must=(x,m)=>{if(!x)throw Error('JRA v3.13 BLOCKER: '+m)};
const safeCopy=x=>JSON.parse(JSON.stringify(x));
const prestart=d=>Number.isFinite(Date.parse(d?.race_context?.start_at))&&Date.now()<Date.parse(d.race_context.start_at);
const yn=x=>Math.round(x*1e9)/1e9;
const referencePortfolio=d=>({
 purchase_portfolio_selection:safeCopy(d.purchase_portfolio_selection),
 final_bets:safeCopy(d.final_bets),
 total_stake_yen:d.total_stake_yen
});
export function upgradeToV313(baseline){
 must(baseline?.prompt_version==='v3.12','only an already audited v3.12 candidate may be upgraded');
 must(baseline?.purchase_budget_yen===6000,'6000 yen cap required');
 const original=safeCopy(baseline);
 const base=referencePortfolio(original);
 const initial=base.purchase_portfolio_selection.selected_lines;
 const result=optimizeWinStakeForRecovery({
  selected_lines:initial,outcome_distributions:original.outcome_distributions,
  frame_map:original.frame_map,race_context:original.race_context,budget_yen:6000
 });
 must(result.selected_lines.length===initial.length,'ticket list changed');
 const bought=result.selected_lines.length>0;
 const stats=bought?evaluateStrategy(result.selected_lines,original.outcome_distributions,original.frame_map,original.race_context):null;
 const total=stats?.total_stake_yen??0;
 must(total<=6000&&total===result.total_stake_yen,'sized portfolio exceeds budget');
 const selected=result.selected_lines.map((line,i)=>{
   must(ticketKey(line.type,line.selection)===ticketKey(initial[i].type,initial[i].selection),'purchase identity changed');
   must(line.type==='単勝'||line.stake_yen===initial[i].stake_yen,'non-win stake was altered');
   return {...line};
 });
 const selectedBets=selected.map((line,i)=>({
   id:'B'+String(i+1).padStart(2,'0'),type:line.type,selection:line.selection,
   stake_yen:line.stake_yen,market_odds:line.market_odds,source_url:line.source_url,
   observed_at:line.observed_at,market_selection_id:line.market_selection_id
 }));
 const a=base.purchase_portfolio_selection;
 const audit={...a.optimizer_audit,
   budget_unused_yen:6000-total,
   expected_net_profit_yen:stats?yn(stats.expected_payout_yen_scenarios.central-total):0,
   lower_scenario_expected_net_profit_yen:stats?yn(stats.expected_payout_yen_scenarios.low-total):0,
   win_stake_sizing:result.optimizer_audit
 };
 const portfolio={...a,
   algorithm:'v313_balanced_ticket_selection_plus_win_recovery_staking',
   objective:'v312_ticket_selection_then_maximize_nonloss_with_profit_risk_floor',
   optimizer_audit:audit,selected_lines:selected,total_stake_yen:total,
   hit_probability_scenarios:stats?.hit_probability_scenarios??null,
   expected_payout_yen_scenarios:stats?.expected_payout_yen_scenarios??null,
   roi_scenarios:stats?.roi_scenarios??null,
   full_loss_probability_scenarios:stats?.full_loss_probability_scenarios??null,
   loss_probability_scenarios:stats?.loss_probability_scenarios??null,
   expected_net_profit_yen_scenarios:stats?Object.fromEntries(SC.map(sc=>[sc,yn(stats.expected_payout_yen_scenarios[sc]-total)])):null
 };
 const metrics=st=>st?Object.fromEntries(SC.map(sc=>[sc,{
  expected_net_profit_yen:yn(st.expected_payout_yen_scenarios[sc]-st.total_stake_yen),
  hit_probability:st.hit_probability_scenarios[sc],
  nonloss_probability:1-st.loss_probability_scenarios[sc],
  net_loss_probability:st.loss_probability_scenarios[sc]
 }])):null;
 const originalStats=initial.length?evaluateStrategy(initial,original.outcome_distributions,original.frame_map,original.race_context):null;
 return {...original,
   prompt_version:'v3.13',
   v312_balanced_baseline:base,
   purchase_portfolio_selection:portfolio,final_bets:selectedBets,total_stake_yen:total,
   win_stake_allocation_v313:{
     algorithm:'win_recovery_staking_shadow_v1_formally_validated',
     activated:result.selected_lines.some((l,i)=>l.stake_yen!==initial[i].stake_yen),
     eligible_scope:'only_prestart_selected_WIN_ticket_stakes',
     source_of_odds:'original_real_verified_per_ticket_prestart_quotes',
     baseline:metrics(originalStats),selected:metrics(stats),
     details:result.optimizer_audit,
     decision_reason:result.reason,
     preserve_v312_candidate_mode_comparisons:true,
     baseline_and_candidate_metrics_separate:true,
     historical_results_not_used:true
   }
 };
}
export function assembleV313(input,freezeAt){
 must(input?.prompt_version==='v3.13','v3.13 source input required');
 must(new Date(freezeAt).getTime()<Date.parse(input.race_context?.start_at),'cannot assemble after race start');
 const previous=assembleV312({...input,prompt_version:'v3.12'},freezeAt,null);
 return upgradeToV313(previous);
}
function argVal(args,name){const i=args.indexOf(name);return i>=0?args[i+1]:null;}
function writeNew(out,data){
 must(!fs.existsSync(out),'immutable output path exists');
 fs.mkdirSync(path.dirname(out),{recursive:true});
 fs.writeFileSync(out,JSON.stringify(data,null,2)+'\n');
}
function run(){
 const args=process.argv.slice(2),output=argVal(args,'--output');
 must(output,'--output required');
 const seal=argVal(args,'--seal'),proof=argVal(args,'--proof-commit');
 if(seal){
  must(/^[0-9a-f]{40}$/.test(proof||''),'real Git proof commit SHA required');
  const snapshot=JSON.parse(execFileSync('git',['show',proof+':'+seal],{encoding:'utf8',maxBuffer:128*1024*1024}));
  must(snapshot.stage==='pending_git_proof'&&snapshot.proof_commit===null&&snapshot.prompt_version==='v3.13','source snapshot is not pending v3.13');
  const date=execFileSync('git',['show','-s','--format=%cI',proof],{encoding:'utf8'}).trim();
  must(Date.parse(date)<Date.parse(snapshot.race_context.start_at),'proof was committed after race start');
  must(prestart(snapshot),'cannot seal after race start');
  const data={...snapshot,stage:'formal_prestart',proof_commit:proof};
  const errors=validateV313(data);
  must(errors.length===0,'validator rejected formal v3.13: '+errors.join('; '));
  writeNew(output,data);
  console.log('SEALED_V313',data.race_id,data.final_bets.length,data.total_stake_yen,proof);
 }else{
  const file=argVal(args,'--input');
  must(file,'--input or --seal required');
  const input=JSON.parse(fs.readFileSync(file,'utf8'));
  must(Date.now()<Date.parse(input.race_context?.start_at),'cannot run after race start');
  const data=assembleV313(input,new Date().toISOString());
  writeNew(output,data);
  console.log('PENDING_V313',data.race_id,data.final_bets.length,data.total_stake_yen);
 }
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
 try{run()}catch(e){console.error('JRA V313 BLOCKER:',e.message);process.exitCode=1;}
}
