// Independent usability shadow: at most three COMPLETE JRA purchase commands per race.
// This file never changes STEP1, final_bets, official predictions, or source odds.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {buildTicketUniverse} from './jra-portfolio-optimizer-v310.mjs';
import {expandStrategy,ticketKey,evaluateStrategy} from './jra-strategy-engine-v39.mjs';

export const THREE_COMMAND_POLICY=Object.freeze({
  budget_yen:6000,unit_yen:100,max_purchase_commands:3,
  max_group_candidates:48,max_single_candidates:12,max_exact_evaluations:90,
  formal_adoption:false,tradeoff_requires_explicit_review:true
});
const must=(p,msg)=>{if(!p)throw Error('THREE_COMMAND_BLOCKER: '+msg);};
const key=t=>ticketKey(t.type,t.selection);
const price=x=>x.expected_profit_yen;
const round=x=>Math.round(x*10000)/10000;
const sum=(xs,f)=>xs.reduce((a,x)=>a+f(x),0);
const stats=(lines,args)=>{
  if(!lines.length)return {stake_yen:0,expected_net_profit_yen:0,expected_net_profit_low_yen:0,
    hit_probability:0,net_loss_probability:0};
  const s=evaluateStrategy(lines,args.outcome_distributions,args.frame_map,args.race_context);
  must(Number.isFinite(s.hit_probability_scenarios?.central)&&
    Number.isFinite(s.loss_probability_scenarios?.central),'joint scenario outcomes required');
  return {stake_yen:s.total_stake_yen,
    expected_net_profit_yen:round(s.expected_payout_yen_scenarios.central-s.total_stake_yen),
    expected_net_profit_low_yen:round(s.expected_payout_yen_scenarios.low-s.total_stake_yen),
    hit_probability:round(s.hit_probability_scenarios.central),
    net_loss_probability:round(s.loss_probability_scenarios.central)};
};
const commandRank=(a,b)=>b.ev-a.ev||b.count-a.count||a.id.localeCompare(b.id,'en');
function candidates(strategies,all){
  const byKey=new Map(all.map(x=>[key(x),x])),groups=new Map();
  const rejected={partial:0,unpriced:0,over_budget:0,unsupported:0};
  const offer=(id,type,mode,definition,wanted)=>{
    const ks=wanted.map(key),unique=new Set(ks);
    if(unique.size!==ks.length){rejected.unsupported++;return;}
    if(ks.some(k=>!byKey.has(k))){rejected.unpriced++;return;}
    const lines=ks.map(k=>byKey.get(k));
    if(lines.length*100>THREE_COMMAND_POLICY.budget_yen){rejected.over_budget++;return;}
    const ev=sum(lines,price);
    if(ev<=1e-8)return;
    const signature=[...unique].sort().join('|');
    const candidate={id,type,method:mode,definition,count:lines.length,stake_yen:lines.length*100,
      ticket_keys:[...unique].sort(),lines,ev};
    const previous=groups.get(signature);
    const modePriority=m=>m==='box'?0:m==='key_wheel'?1:m==='two_key_wheel'?1:m==='formation'?2:3;
    if(!previous||modePriority(mode)<modePriority(previous.method))groups.set(signature,candidate);
  };
  for(const st of strategies){
    if(st.strategy_kind==='multiple_singles'||st.strategy_kind==='win_place_support')continue;
    let expanded;
    try{expanded=expandStrategy(st.type,st.strategy_kind,st.definition);}
    catch{rejected.unsupported++;continue;}
    const expected=expanded.map(key),actual=(st.lines||[]).map(key);
    if(expected.length!==actual.length||new Set(actual).size!==actual.length||
      expected.some(k=>!actual.includes(k))){rejected.partial++;continue;}
    offer(String(st.strategy_id),st.type,st.strategy_kind,st.definition,expanded);
  }
  // A single ticket is one complete JRA input, even when not explicitly predeclared.
  const singles=all.filter(x=>x.expected_profit_yen>0).sort((a,b)=>
    b.expected_profit_yen-a.expected_profit_yen||key(a).localeCompare(key(b),'en'))
    .slice(0,THREE_COMMAND_POLICY.max_single_candidates);
  for(const x of singles)offer('single:'+key(x),x.type,'single',{selection:x.selection},
    [{type:x.type,selection:x.selection}]);
  const allGroups=[...groups.values()].sort(commandRank);
  const multi=allGroups.filter(x=>x.count>1).slice(0,THREE_COMMAND_POLICY.max_group_candidates);
  return {groups:[...multi,...allGroups.filter(x=>x.count===1)],rejected,
    candidate_group_count:allGroups.length};
}
function mapToCommands(selected){
  return selected.map(x=>({type:x.type,method:x.method,definition:x.definition,
    points:x.count,unit_stake_yen:100,stake_yen:x.stake_yen,
    ticket_keys:x.ticket_keys,source_strategy_id:x.id}));
}
export function compareThreeCommandPortfolio(args){
  must(Array.isArray(args.strategies)&&args.strategies.length>0,'complete strategies required');
  must(Array.isArray(args.formal_final_bets),'formal final_bets required');
  must(args.freeze_at&&Date.parse(args.freeze_at)<Date.parse(args.race_context?.start_at),
    'must use sealed prestart data');
  const spendCeiling=args.max_spend_yen??THREE_COMMAND_POLICY.budget_yen;
  must(Number.isInteger(spendCeiling)&&spendCeiling>=100&&spendCeiling<=THREE_COMMAND_POLICY.budget_yen&&spendCeiling%100===0,
    'invalid max spend ceiling');
  const {all,audit}=buildTicketUniverse({...args,max_ticket_stake_yen:100});
  const priced=new Map(all.map(x=>[key(x),x]));
  const original=args.formal_final_bets.map(x=>{
    const p=priced.get(key(x));
    must(p&&JSON.stringify(p.market_odds)===JSON.stringify(x.market_odds)&&
      p.source_url===x.source_url&&p.observed_at===x.observed_at,
      'final_bets not fully matched to source-verified catalog: '+key(x));
    return {...p,stake_yen:x.stake_yen};
  });
  must(new Set(original.map(key)).size===original.length,'duplicate formal final tickets');
  must(sum(original,x=>x.stake_yen)<=THREE_COMMAND_POLICY.budget_yen,
    'official portfolio over budget');
  const baseline=stats(original,args);
  const {groups,rejected,candidate_group_count}=candidates(args.strategies,all);
  // Exact 0/1 search over complete, disjoint JRA actions. No synthetic "basket" rows.
  const seen=new Map(),top=[];
  let enumerated=0,feasible=0;
  const offer=selected=>{
    const spent=sum(selected,x=>x.stake_yen);
    if(spent>spendCeiling)return;
    const keys=selected.flatMap(x=>x.ticket_keys);
    if(new Set(keys).size!==keys.length)return;
    const ev=sum(selected,x=>x.ev);
    if(ev<=1e-8)return;
    enumerated++;
    const k=[...keys].sort().join('|');
    const old=seen.get(k);
    const next={selected,ev,spent,keys,command_count:selected.length,
      ticket_count:keys.length};
    if(!old||next.command_count<old.command_count)seen.set(k,next);
  };
  for(let i=0;i<groups.length;i++){
    offer([groups[i]]);
    for(let j=i+1;j<groups.length;j++){
      offer([groups[i],groups[j]]);
      for(let k=j+1;k<groups.length;k++)offer([groups[i],groups[j],groups[k]]);
    }
  }
  const pool=[...seen.values()];
  const byProfit=[...pool].sort((a,b)=>b.ev-a.ev||a.command_count-b.command_count);
  const byEfficiency=[...pool].sort((a,b)=>
    (b.ev/b.command_count)-(a.ev/a.command_count)||b.ev-a.ev);
  const bySpread=[...pool].sort((a,b)=>
    b.ticket_count-a.ticket_count||b.ev-a.ev);
  const finalists=new Map();
  for(const source of [byProfit,byEfficiency,bySpread]){
    for(const p of source.slice(0,THREE_COMMAND_POLICY.max_exact_evaluations/3)){
      finalists.set(p.keys.join('|'),p);
    }
  }
  let best=null;
  for(const p of finalists.values()){
    const lines=p.selected.flatMap(x=>x.lines);
    const s=stats(lines,args);
    if(s.expected_net_profit_yen<=0)continue;
    feasible++;
    // Maximise modeled central EV; then union hit; then fewer purchase commands.
    // Low-scenario and net-loss are audited and shown, NEVER hidden or inferred.
    if(!best||s.expected_net_profit_yen>best.metrics.expected_net_profit_yen+1e-6||
      (Math.abs(s.expected_net_profit_yen-best.metrics.expected_net_profit_yen)<=1e-6&&
        (s.hit_probability>best.metrics.hit_probability+1e-6||
         (s.hit_probability===best.metrics.hit_probability&&p.command_count<best.commands.length)))){
      best={commands:mapToCommands(p.selected),metrics:s,
        lines:lines.map(x=>({type:x.type,selection:x.selection,stake_yen:x.stake_yen,
          market_odds:x.market_odds,source_url:x.source_url,observed_at:x.observed_at}))};
    }
  }
  if(best){
    must(best.commands.length<=THREE_COMMAND_POLICY.max_purchase_commands,
      'more than three actions');
    const keys=best.lines.map(key);
    must(new Set(keys).size===keys.length,'candidate duplicates ticket');
    const commands=best.commands.flatMap(x=>x.ticket_keys);
    must(commands.length===keys.length&&commands.every(x=>keys.includes(x)),
      'purchase instructions do not expand to exactly all candidate lines');
    must(sum(best.commands,x=>x.stake_yen)===best.metrics.stake_yen,
      'purchase command amounts differ from portfolio');
  }
  return {status:best?'three_command_shadow_candidate':'no_qualifying_three_command_set',
    formal_prediction_unchanged:true,formal_bets_unchanged:true,
    formal_adoption_authorized:false,not_global_optimum:true,
    algorithm:'three_command_bounded_joint_outcome_shadow_v1', max_spend_yen:spendCeiling,
    baseline,proposed:best?.metrics??null,
    commands:best?.commands??[],proposed_lines:best?.lines??[],
    comparison:best?{expected_profit_delta_yen:round(best.metrics.expected_net_profit_yen-baseline.expected_net_profit_yen),
      hit_probability_delta_pp:round(100*(best.metrics.hit_probability-baseline.hit_probability)),
      net_loss_probability_delta_pp:round(100*(best.metrics.net_loss_probability-baseline.net_loss_probability))}:null,
    audit:{verified_source_ticket_count:audit.unique_tickets,candidate_group_count,
      combinations_enumerated:enumerated,exact_evaluations:finalists.size,
      positive_profit_evaluations:feasible,rejected},
    caution:'This is a separately priced counterfactual, not the formal final_bets. Never publish as the official purchase instruction; model probabilities are uncalibrated.'};
}
if(process.argv[1]?.endsWith('/jra-three-command-shadow-v1.mjs')){
  try{
    const argv=process.argv.slice(2),arg=n=>argv[argv.indexOf(n)+1];
    must(argv.includes('--input')&&argv.includes('--output'),'--input and --output required');
    const input=arg('--input'),output=arg('--output');
    const original=fs.readFileSync(input);
    const r=JSON.parse(original);
    must(r.prompt_version==='v3.13'&&r.stage==='formal_prestart'&&
      /^[0-9a-f]{40}$/.test(r.proof_commit||''),'sealed prestart v3.13 source required');
    must(output==='docs/data/jra-three-command-shadow/'+r.race_id+'.json'&&
      !fs.existsSync(output),'must create a new immutable race-specific shadow');
    const result=compareThreeCommandPortfolio({
      budget_yen:6000,strategies:r.purchase_strategy_evaluations,
      formal_final_bets:r.final_bets,outcome_distributions:r.outcome_distributions,
      frame_map:r.frame_map,race_context:r.race_context,freeze_at:r.final_bets_fixed_at});
    fs.mkdirSync(path.dirname(output),{recursive:true});
    fs.writeFileSync(output,JSON.stringify({
      race_id:r.race_id,source_prediction_sha256:createHash('sha256').update(original).digest('hex'),
      proof_commit:r.proof_commit,model_version:'v3.13',status:'shadow_only',
      ...result},null,2)+'\n');
    console.log('JRA_THREE_COMMAND_SHADOW',r.race_id,result.status,
      'commands',result.commands.length,'baseline_profit',result.baseline.expected_net_profit_yen,
      'proposed_profit',result.proposed?.expected_net_profit_yen??null);
  }catch(e){console.error(e.message);process.exitCode=1;}
}
