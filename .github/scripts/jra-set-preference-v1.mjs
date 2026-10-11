// Purchase-set preference research: never edits STEP1, exact source quotes, formal v3.13,
// or any historical sealed forecast. Evaluate actual complete BOX/wheel/formation sets.
// This is a finite audited neighbourhood, NOT a proof of global portfolio optimality.
import {buildTicketUniverse} from './jra-portfolio-optimizer-v310.mjs';
import {expandStrategy,ticketKey,evaluateStrategy} from './jra-strategy-engine-v39.mjs';

const key=t=>ticketKey(t.type,t.selection);
const EPS=1e-7;
export const SET_PREFERENCE_POLICY=Object.freeze({
 max_budget_yen:6000,unit_yen:100,max_group_candidates:24,max_groups_per_portfolio:2,
 min_saved_purchase_commands:1,max_expected_profit_sacrifice_yen:100,
 max_expected_profit_sacrifice_ratio:0.02,max_union_hit_decrease:0.005,
 max_net_loss_increase:0.01,max_low_scenario_profit_sacrifice_yen:200
});
const must=(p,msg)=>{if(!p)throw Error('SET_PREFERENCE_BLOCKER: '+msg);};
const num=x=>typeof x==='number'&&Number.isFinite(x);
const profit=(stats,s)=>stats?.expected_payout_yen_scenarios?.[s]-stats.total_stake_yen;
const metric=(lines,args)=>{
 if(!lines.length)return {total_stake_yen:0,hit_probability_scenarios:null,loss_probability_scenarios:null,expected_payout_yen_scenarios:null};
 return evaluateStrategy(lines,args.outcome_distributions,args.frame_map,args.race_context);
};
const sortedKeys=lines=>lines.map(key).sort((a,b)=>a.localeCompare(b,'en'));
const display=t=>({type:t.type,selection:t.selection,stake_yen:t.stake_yen,market_odds:t.market_odds,
 source_url:t.source_url,observed_at:t.observed_at,market_selection_id:t.market_selection_id});
function toCandidateGroups(strategies,byKey,budget){
 const dedupe=new Map(),failures={unpriced:0,over_budget:0,incomplete:0,unsupported:0};
 for(const st of strategies){
  if(st.strategy_kind==='single'){continue;}
  let legal;
  try{legal=expandStrategy(st.type,st.strategy_kind,st.definition);}
  catch{failures.unsupported++;continue;}
  if(legal.length<2){continue;}
  const exact=new Map();
  for(const x of st.lines||[]){
   try{exact.set(key(x),x);}
   catch{failures.unsupported++;}
  }
  const expected=legal.map(key);
  if(exact.size!==expected.length||expected.some(k=>!exact.has(k))){
   failures.incomplete++;continue;
  }
  if(expected.length*100>budget){failures.over_budget++;continue;}
  if(expected.some(k=>!byKey.has(k))){
   failures.unpriced++;continue;
  }
  const lines=expected.map(k=>byKey.get(k));
  if(lines.some(x=>x.stake_yen!==100)){
   failures.unsupported++;continue;
  }
  const id=sortedKeys(lines).join('|'); // same exact purchased set may have multiple labels
  const group={strategy_id:st.strategy_id,type:st.type,kind:st.strategy_kind,
   definition:st.definition,tickets:expected.length,lines,keys:new Set(expected)};
  const old=dedupe.get(id);
  if(!old||String(group.kind).localeCompare(old.kind,'en')<0)dedupe.set(id,group);
 }
 return {groups:[...dedupe.values()],failures};
}
function packageExact(lines,groups){
 const selected=new Map(lines.map(t=>[key(t),t]));
 const used=new Set(),commands=[];
 const available=groups.filter(g=>g.lines.every(t=>selected.has(key(t))&&selected.get(key(t)).stake_yen===100))
 .sort((a,b)=>b.tickets-a.tickets||a.strategy_id.localeCompare(b.strategy_id,'en'));
 for(const g of available){
  if([...g.keys].some(k=>used.has(k)))continue;
  for(const k of g.keys)used.add(k);
  commands.push({method:g.kind,strategy_id:g.strategy_id,type:g.type,
   definition:g.definition,tickets:g.tickets,total_stake_yen:g.tickets*100,
   ticket_keys:[...g.keys].sort()});
 }
 for(const t of lines)if(!used.has(key(t))){
  const k=key(t);used.add(k);
  commands.push({method:'single',strategy_id:null,type:t.type,definition:{selection:t.selection},
   tickets:1,total_stake_yen:t.stake_yen,ticket_keys:[k]});
 }
 must(used.size===selected.size&&commands.reduce((a,x)=>a+x.total_stake_yen,0)===
  lines.reduce((a,x)=>a+x.stake_yen,0),'purchase commands incomplete');
 return commands;
}
function publishMetrics(lines,commands,args){
 const m=metric(lines,args);
 return {total_stake_yen:m.total_stake_yen,ticket_count:lines.length,command_count:commands.length,
  hit_probability:m.hit_probability_scenarios?.central??null,
  net_loss_probability:m.loss_probability_scenarios?.central??null,
  expected_net_profit_yen:lines.length?profit(m,'central'):0,
  expected_net_profit_low_yen:lines.length?profit(m,'low'):0};
}
export function compareSetPreferredPortfolio(args){
 const budget=args.budget_yen??6000;
 must(budget===6000,'formal JRA budget must remain exactly 6000 yen');
 must(Array.isArray(args.strategies)&&Array.isArray(args.baseline_selected_lines),'pre-price strategies and validated baseline required');
 const {all,audit}=buildTicketUniverse({...args,max_ticket_stake_yen:100});
 const byKey=new Map(all.map(x=>[key(x),x]));
 const baseline=args.baseline_selected_lines.map(x=>{
  const v=byKey.get(key(x));
  must(v!==undefined&&v.stake_yen===x.stake_yen&&
   JSON.stringify(v.market_odds)===JSON.stringify(x.market_odds)&&
   v.source_url===x.source_url&&v.observed_at===x.observed_at,
   'baseline selection differs from verified quotes '+key(x));
  return v;
 });
 must(new Set(baseline.map(key)).size===baseline.length,'baseline tickets duplicated');
 must(baseline.every(x=>x.stake_yen===100),'compare ticket selection BEFORE v3.13 WIN sizing');
 must(baseline.reduce((a,x)=>a+x.stake_yen,0)<=budget,'baseline exceeds budget');
 const {groups,failures}=toCandidateGroups(args.strategies,byKey,budget);
 const baselineCommands=packageExact(baseline,groups);
 const base=publishMetrics(baseline,baselineCommands,args);
 if(!baseline.length)return {
  algorithm:'set_preference_bounded_neighbourhood_v1',activated:false,status:'no_buy_baseline',
  baseline:base,proposed:base,commands:baselineCommands,proposed_lines:[],candidate_group_count:groups.length,
  considered:0,rejected:failures,why:'No positive-value baseline to rebalance'
 };
 const minProfit=base.expected_net_profit_yen-Math.min(
  SET_PREFERENCE_POLICY.max_expected_profit_sacrifice_yen,
  Math.max(0,base.expected_net_profit_yen)*SET_PREFERENCE_POLICY.max_expected_profit_sacrifice_ratio);
 const groupOrder=groups.map(g=>{
  const baselineKeys=new Set(baseline.map(key));
  const overlap=[...g.keys].filter(k=>baselineKeys.has(k)).length;
  return {...g,overlap};
 }).filter(g=>g.overlap>=2).sort((a,b)=>b.overlap-a.overlap||
   a.tickets-b.tickets||a.strategy_id.localeCompare(b.strategy_id,'en'))
 .slice(0,SET_PREFERENCE_POLICY.max_group_candidates);
 let choice={lines:baseline,commands:baselineCommands,summary:base,
  group_ids:[],changed_ticket_keys:[]};
 let considered=0,feasible=0;
 const tryGroups=chosen=>{
  const keys=new Set(),forced=[];
  for(const g of chosen)for(const x of g.lines){
   const k=key(x);
   if(keys.has(k))return;
   keys.add(k);forced.push(x);
  }
  if(forced.length*100>budget)return;
  const remainder=baseline.filter(x=>!keys.has(key(x)))
   .sort((a,b)=>b.expected_profit_yen-a.expected_profit_yen||
    key(a).localeCompare(key(b),'en'));
  const extra=remainder.slice(0,Math.floor((budget-forced.length*100)/100));
  const combined=[...forced,...extra].sort((a,b)=>key(a).localeCompare(key(b),'en'));
  considered++;
  const commands=packageExact(combined,groups),s=publishMetrics(combined,commands,args);
  if(s.command_count>=base.command_count||
     s.command_count>choice.summary.command_count||
     s.expected_net_profit_yen<=EPS||s.expected_net_profit_yen+EPS<minProfit||
     s.hit_probability+EPS<base.hit_probability-SET_PREFERENCE_POLICY.max_union_hit_decrease||
     s.net_loss_probability>base.net_loss_probability+SET_PREFERENCE_POLICY.max_net_loss_increase+EPS||
     s.expected_net_profit_low_yen+EPS<base.expected_net_profit_low_yen-
       SET_PREFERENCE_POLICY.max_low_scenario_profit_sacrifice_yen)return;
  feasible++;
  const better=s.command_count<choice.summary.command_count||
   (s.command_count===choice.summary.command_count&&
    (s.expected_net_profit_yen>choice.summary.expected_net_profit_yen+EPS||
     (Math.abs(s.expected_net_profit_yen-choice.summary.expected_net_profit_yen)<EPS&&
      s.hit_probability>choice.summary.hit_probability+EPS)));
  if(better)choice={lines:combined,commands,summary:s,group_ids:chosen.map(g=>g.strategy_id),
   changed_ticket_keys:sortedKeys(combined).filter(k=>!new Set(baseline.map(key)).has(k))};
 };
 for(let i=0;i<groupOrder.length;i++){
  tryGroups([groupOrder[i]]);
  for(let j=i+1;j<groupOrder.length;j++)tryGroups([groupOrder[i],groupOrder[j]]);
 }
 const changed=sortedKeys(choice.lines).join('|')!==sortedKeys(baseline).join('|');
 return {algorithm:'set_preference_bounded_neighbourhood_v1',
  activated:changed,status:changed?'eligible_shadow_candidate':'keep_formal_baseline',
  formal_prediction_unchanged:true,not_global_optimum:true,
  baseline:base,proposed:choice.summary,
  proposed_lines:choice.lines.map(display),commands:choice.commands,
  preferred_strategy_ids:choice.group_ids,
  considered,feasible,candidate_group_count:groups.length,
  source_quote_universe_count:audit.unique_tickets,rejected:failures,
  guardrails:{minimum_central_profit_yen:minProfit,policy:SET_PREFERENCE_POLICY},
  caveat:'Modeled win probabilities are uncalibrated; no actual-return guarantee. This sidecar never changes the official v3.13 final_bets.'};
}

if(process.argv[1]&&process.argv[1].endsWith('/jra-set-preference-v1.mjs')){
 try{
  const fs=await import('node:fs'),path=await import('node:path');
  const argv=process.argv.slice(2),get=k=>argv[argv.indexOf(k)+1];
  const input=get('--input'),output=get('--output');
  must(input&&output&&argv.includes('--input')&&argv.includes('--output'),'--input/--output required');
  must(!fs.existsSync(output),'immutable sidecar already exists: '+output);
  const source=JSON.parse(fs.readFileSync(input,'utf8'));
  must(source.prompt_version==='v3.13'&&source.stage==='formal_prestart'&&
   /^[a-f0-9]{40}$/.test(source.proof_commit||''),
   'only sealed v3.13 prestart originals are eligible for shadow research');
  must(new RegExp('^docs/data/jra-set-preference/[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+\\.json$').test(output)&&
   output==='docs/data/jra-set-preference/'+source.race_id+'.json',
   'sidecar path must be canonical and race-specific');
  const base=source.v312_balanced_baseline?.purchase_portfolio_selection?.selected_lines;
  must(Array.isArray(base),'immutable v3.12 baseline not available');
  const comparisons=compareSetPreferredPortfolio({
   budget_yen:6000,strategies:source.purchase_strategy_evaluations,
   baseline_selected_lines:base,outcome_distributions:source.outcome_distributions,
   frame_map:source.frame_map,race_context:source.race_context,freeze_at:source.final_bets_fixed_at
  });
  const sha=(await import('node:crypto')).createHash('sha256')
    .update(fs.readFileSync(input)).digest('hex');
  const payload={race_id:source.race_id,status:'shadow_comparison_only',
   formal_prompt_version:'v3.13',formal_purchase_decision_unchanged:true,
   formal_bets_selection_unchanged:true,formal_proof_commit:source.proof_commit,
   formal_prediction_file:input,formal_prediction_sha256:sha,
   models_compared:'v3.12 100-yen selected-line baseline vs grouped complete-strategy counterfactual; not v3.13 WIN-stake-sized final',
   comparison:comparisons};
  fs.mkdirSync(path.dirname(output),{recursive:true});
  fs.writeFileSync(output,JSON.stringify(payload,null,2)+'\\n');
  console.log('JRA_SET_PREFERENCE_SHADOW_CREATED',source.race_id,
   comparisons.status,comparisons.baseline.command_count,comparisons.proposed.command_count);
 }catch(e){console.error('JRA_SET_PREFERENCE_BLOCKER',e.message);process.exitCode=1;}
}
