// Prototype only: three JRA betting-screen operations plus ONE separately audited
// speculative/longshot line. Never overwrite formal v3.13 predictions or final_bets.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {compareThreeCommandPortfolio} from './jra-three-command-shadow-v1.mjs';
import {buildTicketUniverse} from './jra-portfolio-optimizer-v310.mjs';
import {evaluateStrategy,oddsFloor,ticketKey,expandStrategy} from './jra-strategy-engine-v39.mjs';
import {formatPurchaseCommand} from './jra-ticket-notation-v1.mjs';
import {assessExactaMultiCoverage} from './jra-exacta-wheel-comparison-v1.mjs';
const must=(v,msg)=>{if(!v)throw Error('THREE_PLUS_ANA_BLOCKER: '+msg);};
const sum=(xs,f)=>xs.reduce((a,x)=>a+f(x),0);
const key=x=>ticketKey(x.type,x.selection);
const round=x=>Math.round(x*10000)/10000;
export const PURCHASE_ACTION_POLICY=Object.freeze({
 version:'v3.15-candidate-shadow',max_regular_commands:3,max_medium_rows:1,max_large_rows:1,
 budget_total_yen:6000,minimum_unit_yen:100,
 medium_min_odds:20,large_min_odds:100,
 medium_max_odds_exclusive:100,max_rare_event_probability:0.10,
 require_positive_edge:true,formal_release:false
});
export const instructions=formatPurchaseCommand;
const pctSafe=x=>Number.isFinite(x)?x:0;
const amount=x=>x.stake_yen??100;
function identifyHoles(args,all){
 const quotes=new Map(all.map(x=>[key(x),x]));
 const h=[];
 const tryCandidate=(type,method,definition,wanted,source)=>{
   if(!Array.isArray(wanted)||!wanted.length)return;
   const ks=wanted.map(key),uniq=new Set(ks);
   if(uniq.size!==ks.length||ks.some(x=>!quotes.has(x)))return;
   const lines=ks.map(x=>quotes.get(x));
   const odds=lines.map(x=>oddsFloor(x.market_odds));
   const ev=sum(lines,x=>x.expected_profit_yen);
   const stake=lines.length*100;
   if(odds.some(x=>!Number.isFinite(x))||ev<=0||stake>=6000)return;
   const centralProb=Math.max(...lines.map(x=>pctSafe(x.probabilities?.central)));
   const minimum=Math.min(...odds);
   // The whole command is eligible for a labelled class, not merely one
   // extraordinary-priced ticket hidden among ordinary-priced lines.
   const tier=minimum>=100?'大穴':minimum>=20&&Math.max(...odds)<100?'中穴':null;
   if(!tier||centralProb>PURCHASE_ACTION_POLICY.max_rare_event_probability)return;
   h.push({tier,type,method,definition,ticket_keys:[...uniq],lines,
     points:lines.length,stake_yen:stake,expected_profit_yen:ev,
     minimum_odds:minimum,maximum_odds:Math.max(...odds),source});
 };
 for(const x of all){
   if(['三連複','三連単'].includes(x.type))continue; // no 1-point triple bet
   tryCandidate(x.type,'single',{selection:x.selection},
      [{type:x.type,selection:x.selection}],'verified-single');
 }
 for(const st of args.strategies){
   if(!['三連複','三連単'].includes(st.type)||st.strategy_kind==='single')continue;
   let expanded;
   try{expanded=expandStrategy(st.type,st.strategy_kind,st.definition);}
   catch{continue;}
   const actual=(st.lines||[]).map(key),expected=expanded.map(key);
   if(expected.length!==actual.length||new Set(actual).size!==actual.length||
     expected.some(k=>!actual.includes(k)))continue;
   if(expanded.length<(st.type==='三連単'?6:3))continue;
   tryCandidate(st.type,st.strategy_kind,st.definition,expanded,'verified-complete-group');
 }
 const unique=new Map();
 for(const x of h){
   const signature=x.tier+':'+[...x.ticket_keys].sort().join('|');
   const prev=unique.get(signature);
   if(!prev||x.method==='box'&&prev.method!=='box')unique.set(signature,x);
 }
 return [...unique.values()].sort((a,b)=>
   b.expected_profit_yen/b.stake_yen-a.expected_profit_yen/a.stake_yen||
   b.expected_profit_yen-a.expected_profit_yen||a.points-b.points);
}
function allocateHoles(pool){
 const med=pool.filter(x=>x.tier==='中穴').slice(0,60);
 const large=pool.filter(x=>x.tier==='大穴').slice(0,60);
 // Jointly choose the medium and high-return rows. Never choose a duplicate
 // selection, a negative-edge command or more than 5,900 yen of side bets.
 const options=(xs)=>[null,...xs];
 let best={medium:null,large:null,ev:0,spend:0};
 for(const m of options(med))for(const l of options(large)){
   const spend=amount(m||{stake_yen:0})+amount(l||{stake_yen:0});
   if(spend>5900)continue;
   if(m&&l&&m.ticket_keys.some(k=>l.ticket_keys.includes(k)))continue;
   const ev=(m?.expected_profit_yen??0)+(l?.expected_profit_yen??0);
   if(ev>best.ev+1e-9||Math.abs(ev-best.ev)<1e-9&&spend<best.spend)
     best={medium:m,large:l,ev,spend};
 }
 return best;
}
const holeRow=(candidate,tier,row)=>candidate?{
 row,category:tier,type:candidate.type,method:candidate.method,
 definition:candidate.definition,jra_input:instructions(candidate),
 points:candidate.points,unit_stake_yen:100,stake_yen:candidate.stake_yen,
 ticket_keys:candidate.ticket_keys,
 minimum_verified_odds:round(candidate.minimum_odds),
 maximum_verified_odds:round(candidate.maximum_odds),
 indicative_minimum_payout_yen:Math.floor(candidate.minimum_odds*100),
 model_expected_profit_yen:round(candidate.expected_profit_yen),
 pricing_source:candidate.source,
 reason:tier==='大穴'?'100円あたり1万円以上の的中払戻となる組番だけを選定。モデル期待利益がプラス。':'実測20倍以上・100倍未満の組番だけを選定。モデル期待利益がプラス。'
}:{
 row,category:tier,method:'pass',type:'見送り',jra_input:
 tier==='大穴'?'100倍以上で期待値がプラスの購入セットなし':'20倍以上100倍未満で期待値がプラスの購入セットなし',
 points:0,unit_stake_yen:0,stake_yen:0,ticket_keys:[],
 reason:'条件に合わないため購入を強制しない。'
};
export function compareThreePlusAna(args){
 const {all}=buildTicketUniverse({...args,max_ticket_stake_yen:100});
 const eligibleHoles=identifyHoles(args,all);
 const allocation=allocateHoles(eligibleHoles);
 const medium=holeRow(allocation.medium,'中穴',4);
 const large=holeRow(allocation.large,'大穴',5);
 const excluded=[...medium.ticket_keys,...large.ticket_keys];
 const regular=compareThreeCommandPortfolio({...args,formal_final_bets:args.formal_final_bets,
   max_spend_yen:6000-allocation.spend,exclude_ticket_keys:excluded});
 const quoteLookup=new Map(all.map(x=>[key(x),x]));
 const selectedHole=[...excluded].map(k=>{
   const x=quoteLookup.get(k);must(x,'special selection quote disappeared');
   return {type:x.type,selection:x.selection,stake_yen:100,market_odds:x.market_odds,
     source_url:x.source_url,observed_at:x.observed_at,market_selection_id:x.market_selection_id};
 });
 // Independently check both key directions and the complete 1-axis MULTI,
 // with actual quoted odds and the budget INCLUDING medium/large class rows.
 const exacta=assessExactaMultiCoverage({
   regular_commands:regular.commands,regular_lines:regular.proposed_lines,
   side_lines:selectedHole,all,args,budget_yen:6000
 });
 const commands=exacta.regular_commands.map(c=>({...c,
   category:'通常',jra_input:instructions(c)}));
 const selectedRegular=exacta.regular_lines;
 const lines=[...selectedRegular,...selectedHole];
 must(commands.length<=3,'too many regular commands');
 must(new Set(lines.map(key)).size===lines.length,'overlapping candidate tickets');
 const total=sum(lines,x=>x.stake_yen);
 must(total<=6000,'budget exceeded');
 const commandKeys=[...commands,medium,large].flatMap(c=>c.ticket_keys);
 must(commandKeys.length===lines.length&&new Set(commandKeys).size===lines.length&&
    commandKeys.every(k=>lines.some(x=>key(x)===k)),'screen commands differ from priced actual lines');
 const s=lines.length?evaluateStrategy(lines,args.outcome_distributions,args.frame_map,args.race_context):null;
 const stat=s?{
   stake_yen:total,ticket_count:lines.length,
   command_count:commands.length+(medium.points?1:0)+(large.points?1:0),
   modeled_expected_net_profit_yen:round(s.expected_payout_yen_scenarios.central-total),
   modeled_low_expected_net_profit_yen:round(s.expected_payout_yen_scenarios.low-total),
   modeled_union_hit_probability:round(s.hit_probability_scenarios.central),
   modeled_net_loss_probability:round(s.loss_probability_scenarios.central)
 }:null;
 const formal=regular.baseline;
 return {algorithm:'three_regular_plus_optional_medium_and_100x_large_shadow_v3_exacta_audit',
   status:regular.proposed?'three_plus_two_holes_shadow_candidate':'no_qualifying_regular_command',
   formal_version_unchanged:true,formal_final_bets_unchanged:true,
   candidate_medium_count:eligibleHoles.filter(x=>x.tier==='中穴').length,
   candidate_large_count:eligibleHoles.filter(x=>x.tier==='大穴').length,
   max_regular_commands:3,max_medium_rows:1,max_large_rows:1,
   max_total_budget_yen:6000,formal_baseline:formal,regular_research:regular,
   summary:stat,regular_commands:commands,exacta_coverage_audit:exacta.audit,
   medium_command:medium,large_command:large,proposed_lines:lines,
   change_vs_formal:stat?{
     expected_profit_yen:round(stat.modeled_expected_net_profit_yen-formal.expected_net_profit_yen),
     union_hit_pp:round(100*(stat.modeled_union_hit_probability-formal.hit_probability)),
     net_loss_pp:round(100*(stat.modeled_net_loss_probability-formal.net_loss_probability))
   }:null,
   warning:'STAGING SHADOW ONLY. 100x is a conditional estimated payout on a winning 100-yen ticket, not a guarantee. Model probabilities are uncalibrated. Formal source is immutable.'};
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
   'medium',v.medium_command.method,'large',v.large_command.method,'budget',v.summary?.stake_yen,'delta_ev',v.change_vs_formal?.expected_profit_yen);
 }catch(e){console.error(e.stack??String(e));process.exitCode=1;}
}
