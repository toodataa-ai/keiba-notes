// Stage-only evidence-backed comparison of an exacta 2nd-fixed wheel to
// 1st-fixed and one-axis MULTI. No STEP1, official odds or final_bets edits.
import {expandStrategy,ticketKey,evaluateStrategy} from './jra-strategy-engine-v39.mjs';

const key=x=>ticketKey(x.type,x.selection);
const sum=(xs,f)=>xs.reduce((a,x)=>a+f(x),0);
const fix=x=>Math.round(x*10000)/10000;
const typeRank=Object.fromEntries(['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'].map((x,i)=>[x,i]));
export function sortRegularPurchaseCommands(commands){
 return commands.map((c,i)=>({...c,_original_index:i}))
  .sort((a,b)=>(typeRank[a.type]??99)-(typeRank[b.type]??99)||a._original_index-b._original_index)
  .map(({_original_index,...x},i)=>({...x,row:i+1}));
}
const stats=(lines,args)=>{
 if(!lines.length)return {stake_yen:0,expected_net_profit_yen:0,hit_probability:0,net_loss_probability:0};
 const t=evaluateStrategy(lines,args.outcome_distributions,args.frame_map,args.race_context);
 const vals=[t.expected_payout_yen_scenarios?.central,t.hit_probability_scenarios?.central,t.loss_probability_scenarios?.central];
 if(vals.some(x=>!Number.isFinite(x)))throw Error('EXACTA_COMPARISON_BLOCKER: missing joint probabilities');
 return {stake_yen:t.total_stake_yen,expected_net_profit_yen:fix(vals[0]-t.total_stake_yen),
  hit_probability:fix(vals[1]),net_loss_probability:fix(vals[2])};
};
/** Always compare 2nd-fixed, 1st-fixed and multi on the same frozen odds.
 * Promote only a Pareto-safe option with NO loss of expected EV / joint hit /
 * net-loss safety and no increase beyond 6000 yen. Otherwise retain fixed.
 */
export function assessExactaMultiCoverage({regular_commands,regular_lines,side_lines,all,args,budget_yen=6000}){
 let commands=regular_commands.map(c=>({...c}));
 let lines=regular_lines.map(c=>({...c}));
 const others=side_lines.map(x=>({...x}));
 const catalog=new Map(all.map(x=>[key(x),x]));
 const comparison=[];
 for(let i=0;i<commands.length;i++){
  const command=commands[i];
  if(command.type!=='馬単'||!['key_wheel_second','key_wheel_first'].includes(command.method))continue;
  const existingKeys=new Set(command.ticket_keys);
  const unmodified=lines.filter(x=>!existingKeys.has(key(x)));
  if(unmodified.length!==lines.length-command.points)throw Error('EXACTA_COMPARISON_BLOCKER: source group expanded incorrectly');
  const occupied=new Set([...unmodified,...others].map(key));
  const input={key:command.definition.key,partners:[...command.definition.partners]};
  const baseline=stats([...unmodified,...lines.filter(x=>existingKeys.has(key(x))),...others],args);
  const variants={};
  for(const [mode,label] of [
   ['key_wheel_first','1着固定'],['key_wheel_second','2着固定'],['key_wheel_multi','1頭軸マルチ']
  ]){
   let expanded;
   try{expanded=expandStrategy('馬単',mode,input);}
   catch(e){variants[mode]={status:'unsupported',reason:String(e)};continue;}
   const wanted=expanded.map(key);
   if(wanted.some(k=>!catalog.has(k))){variants[mode]={status:'unpriced',points:wanted.length,reason:'verified market price missing; no imputation'};continue;}
   if(wanted.some(k=>occupied.has(k))){variants[mode]={status:'overlap',points:wanted.length,reason:'would duplicate regular or speculative tickets'};continue;}
   const proposed=[...unmodified,...wanted.map(k=>catalog.get(k)),...others];
   if(sum(proposed,x=>x.stake_yen)>budget_yen){
    variants[mode]={status:'over_budget',points:wanted.length,stake_yen:sum(proposed,x=>x.stake_yen)};
    continue;
   }
   variants[mode]={status:'eligible',points:wanted.length,stake_yen:wanted.length*100,
    metrics:stats(proposed,args)};
  }
  // Choose the Pareto-best among fully priced/covered alternatives and
  // current selected mode. Never claim multi is ALWAYS better: extra tickets cost money.
  const safe=[command.method,'key_wheel_multi','key_wheel_first','key_wheel_second'].filter((m,i,a)=>a.indexOf(m)===i)
   .filter(m=>variants[m]?.status==='eligible'&&
    variants[m].metrics.expected_net_profit_yen>=baseline.expected_net_profit_yen-0.000001&&
    variants[m].metrics.hit_probability>=baseline.hit_probability-0.000001&&
    variants[m].metrics.net_loss_probability<=baseline.net_loss_probability+0.000001);
  safe.sort((a,b)=>
   variants[b].metrics.expected_net_profit_yen-variants[a].metrics.expected_net_profit_yen||
   variants[b].metrics.hit_probability-variants[a].metrics.hit_probability||
   (a===command.method?-1:0)-(b===command.method?-1:0));
  const choice=safe[0]??command.method;
  const next=variants[choice];
  if(choice!==command.method&&next?.status==='eligible'){
    const selectedKeys=expandStrategy('馬単',choice,input).map(key);
    commands[i]={...command,method:choice,definition:input,
       points:selectedKeys.length,stake_yen:selectedKeys.length*100,
       ticket_keys:[...selectedKeys].sort(),source_strategy_id:'audited_'+choice+'_from_'+command.source_strategy_id};
    lines=[...unmodified,...selectedKeys.map(k=>catalog.get(k))];
  }
  comparison.push({type:'馬単',axis:command.definition.key,partners:[...input.partners].sort((a,b)=>a-b),
    original_method:command.method,selected_method:choice,
    initial_portfolio:baseline,variants,
    decision:choice!==command.method?'Pareto-safer candidate selected':
      variants.key_wheel_multi?.status!=='eligible'?
       'Multi rejected: '+(variants.key_wheel_multi?.status||'not examined'):
       'Multi did not Pareto-improve the full priced portfolio'});
 }
 const finalKeys=lines.map(key);
 if(new Set([...finalKeys,...others.map(key)]).size!==finalKeys.length+others.length)
  throw Error('EXACTA_COMPARISON_BLOCKER: duplicate after review');
 if(sum([...lines,...others],x=>x.stake_yen)>budget_yen)
  throw Error('EXACTA_COMPARISON_BLOCKER: budget exceeded after review');
 return {regular_commands:sortRegularPurchaseCommands(commands),regular_lines:lines,
  audit:comparison,final_portfolio_metrics:stats([...lines,...others],args)};
}

