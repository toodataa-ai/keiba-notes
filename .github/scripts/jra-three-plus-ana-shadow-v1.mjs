// Prototype only: three JRA betting-screen operations plus ONE separately audited
// speculative/longshot line. Never overwrite formal v3.13 predictions or final_bets.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {compareThreeCommandPortfolio} from './jra-three-command-shadow-v1.mjs';
import {buildTicketUniverse} from './jra-portfolio-optimizer-v310.mjs';
import {evaluateStrategy,oddsFloor,ticketKey} from './jra-strategy-engine-v39.mjs';
import {formatPurchaseCommand} from './jra-ticket-notation-v1.mjs';
const must=(v,msg)=>{if(!v)throw Error('THREE_PLUS_ANA_BLOCKER: '+msg);};
const sum=(xs,f)=>xs.reduce((a,x)=>a+f(x),0);
const key=x=>ticketKey(x.type,x.selection);
const round=x=>Math.round(x*10000)/10000;
export const PURCHASE_ACTION_POLICY=Object.freeze({
 version:'v3.15-candidate-shadow',max_regular_commands:3,max_ana_lines:1,
 budget_total_yen:6000,ana_line_stake_yen:100,
 min_longshot_market_odds:20,max_longshot_central_event_probability:0.10,
 require_positive_edge:true,formal_release:false
});
export const instructions=formatPurchaseCommand;
export function compareThreePlusAna(args){
 const {all}=buildTicketUniverse({...args,max_ticket_stake_yen:100});
 // Longshot defined as a rare winning event at observed >=20x, not as
 // a result-based guess or an obligation to spend the full budget.
 // A speculative single is allowed only for ticket types where a one-point
 // selection is a normal, meaningful standalone wager. Triples are reserved
 // for fully priced grouped strategies in the 3-command regular comparison.
 const anaCandidates=all.filter(x=>!['三連単','三連複'].includes(x.type)&&x.stake_yen===100&&
   oddsFloor(x.market_odds)>=PURCHASE_ACTION_POLICY.min_longshot_market_odds&&
   x.probabilities.central<=PURCHASE_ACTION_POLICY.max_longshot_central_event_probability&&
   x.expected_profit_yen>0)
   .sort((a,b)=>b.expected_profit_yen-a.expected_profit_yen||
      b.market_odds-a.market_odds||key(a).localeCompare(key(b),'en'));
 const coreArgs={...args,formal_final_bets:args.formal_final_bets};
 // Release of 100 yen is allowed only if a legitimately priced longshot exists.
 const core=compareThreeCommandPortfolio({...coreArgs,
   max_spend_yen:anaCandidates.length?5900:6000});
 let selectedAna=null;
 if(core.proposed){
   const purchased=new Set(core.proposed_lines.map(key));
   selectedAna=anaCandidates.find(x=>!purchased.has(key(x)))??null;
 }
 // If there is no distinct longshot after core search, release the reservation
 // and restore the best unrestricted 3-command reference before presenting it.
 const regular=selectedAna?core:
   anaCandidates.length?compareThreeCommandPortfolio({...coreArgs,max_spend_yen:6000}):core;
 const commands=regular.commands.map((c,i)=>({...c,
   row:i+1,category:'通常',jra_input:instructions(c)}));
 const ana=selectedAna?{
    row:4,category:'穴狙い',type:selectedAna.type,method:'single',
    definition:{selection:selectedAna.selection},jra_input:instructions({type:selectedAna.type,method:'single',definition:{selection:selectedAna.selection}}),
    points:1,unit_stake_yen:100,stake_yen:100,ticket_keys:[key(selectedAna)],
    observed_odds_floor:oddsFloor(selectedAna.market_odds),
    modeled_central_event_probability:round(selectedAna.probabilities.central),
    modeled_profit_yen:round(selectedAna.expected_profit_yen),
    reason:'実測オッズ20倍以上・推定事象確率10%以下・モデル上の期待純利益プラス。高配当狙いの別枠で的中保証なし。'
  }:{
    row:4,category:'穴狙い',method:'pass',type:'見送り',jra_input:'実オッズと期待値の採用条件を満たす別枠なし',
    points:0,unit_stake_yen:0,stake_yen:0,ticket_keys:[],
    reason:'条件不足で穴馬券を無理に追加しない。'
  };
 const selectedRegular=regular.proposed_lines;
 const selectedAnaLine=selectedAna?{type:selectedAna.type,selection:selectedAna.selection,
   stake_yen:100,market_odds:selectedAna.market_odds,observed_at:selectedAna.observed_at,
   source_url:selectedAna.source_url,market_selection_id:selectedAna.market_selection_id}:null;
 const lines=[...selectedRegular,...(selectedAnaLine?[selectedAnaLine]:[])];
 must(commands.length<=3,'more than three main purchase operations');
 must(new Set(lines.map(key)).size===lines.length,'overlapping main and longshot tickets');
 const total=sum(lines,x=>x.stake_yen);
 must(total<=6000,'max budget exceeded');
 const commandKeys=[...commands,ana].flatMap(c=>c.ticket_keys);
 must(commandKeys.length===lines.length&&new Set(commandKeys).size===lines.length&&
   commandKeys.every(k=>lines.some(x=>key(x)===k)),
   'shown commands do not reproduce purchased counterfactual lines exactly');
 let stat=null;
 if(lines.length){
   const x=evaluateStrategy(lines,args.outcome_distributions,args.frame_map,args.race_context);
   stat={stake_yen:total,ticket_count:lines.length,command_count:commands.length+(selectedAna?1:0),
     modeled_expected_net_profit_yen:round(x.expected_payout_yen_scenarios.central-total),
     modeled_low_expected_net_profit_yen:round(x.expected_payout_yen_scenarios.low-total),
     modeled_union_hit_probability:round(x.hit_probability_scenarios.central),
     modeled_net_loss_probability:round(x.loss_probability_scenarios.central)};
 }
 const formal=regular.baseline;
 return {algorithm:'three_regular_plus_optional_longshot_shadow_v1',
   status:regular.proposed?'three_plus_ana_shadow_candidate':'no_profitable_regular_command',
   formal_version_unchanged:true,formal_final_bets_unchanged:true,
   eligible_longshot_count:anaCandidates.length,
   max_regular_commands:3,max_ana_rows:1,max_total_budget_yen:6000,
   formal_baseline:formal,regular_research:regular,
   summary:stat,regular_commands:commands,ana_command:ana,
   proposed_lines:lines,
   change_vs_formal:stat?{
     expected_profit_yen:round(stat.modeled_expected_net_profit_yen-formal.expected_net_profit_yen),
     union_hit_pp:round(100*(stat.modeled_union_hit_probability-formal.hit_probability)),
     net_loss_pp:round(100*(stat.modeled_net_loss_probability-formal.net_loss_probability))
   }:null,
   warning:'STAGING RESEARCH ONLY. Never use as actual official purchase instruction before new formal model/CI/live E2E approval. Probability model not calibrated.'};
}
if(process.argv[1]?.endsWith('/jra-three-plus-ana-shadow-v1.mjs')){
 try{
 const argv=process.argv.slice(2),arg=x=>argv[argv.indexOf(x)+1];
 must(argv.includes('--input')&&argv.includes('--output'),'--input and --output required');
 const input=arg('--input'),out=arg('--output');
 const bytes=fs.readFileSync(input),o=JSON.parse(bytes);
 must(o.prompt_version==='v3.13'&&o.stage==='formal_prestart'&&/^[0-9a-f]{40}$/.test(o.proof_commit||''),
   'sealed original required');
 must(out==='docs/staging/data/three-plus-ana/'+o.race_id+'.json','staging-only output');
 must(!fs.existsSync(out),'cannot overwrite even staged immutable research');
 const v=compareThreePlusAna({budget_yen:6000,strategies:o.purchase_strategy_evaluations,
   formal_final_bets:o.final_bets,frame_map:o.frame_map,
   outcome_distributions:o.outcome_distributions,race_context:o.race_context,
   freeze_at:o.final_bets_fixed_at});
 fs.mkdirSync(path.dirname(out),{recursive:true});
 fs.writeFileSync(out,JSON.stringify({race_id:o.race_id,formal_prediction_sha256:createHash('sha256').update(bytes).digest('hex'),
   formal_proof_commit:o.proof_commit,created_from_frozen_source_only:true,...v},null,2)+'\n');
 console.log('THREE_PLUS_ANA_STAGED',o.race_id,'regular',v.regular_commands.length,
   'ana',v.ana_command.method,'budget',v.summary?.stake_yen,'delta_ev',v.change_vs_formal?.expected_profit_yen);
 }catch(e){console.error(e.stack??String(e));process.exitCode=1;}
}
