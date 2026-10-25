// Explicit 2026-10-25 JRA three-main-race prestart reprice of the
// ALREADY PUBLISHED v3.15 ticket selections. No new bets and no STEP1 changes.
// Full 8-type catalog prices are recaptured by original audited v3.13 reader.
import fs from 'node:fs';
import crypto from 'node:crypto';
import {ticketKey,expandStrategy,evaluateStrategy} from './jra-strategy-engine-v39.mjs';
import {compareV316Shadow} from './jra-stake-optimizer-v316-shadow.mjs';
const need=(p,msg)=>{if(!p)throw Error('V316_TODAY_FRESH_BLOCKER: '+msg);};
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const t=x=>Date.parse(x);
const key=x=>ticketKey(x.type,x.selection);
const round=x=>Math.round(x*10000)/10000;
const equal=(x,y)=>JSON.stringify(x)===JSON.stringify(y);
const ALLOWED=new Set([
 '2026-10-25-lumiere-autumn-dash','2026-10-25-kikka-sho','2026-10-25-kannazuki-stakes'
]);
export function buildTodayFreshV316({source,sourceBytes,prior,priorBytes,originalInput,
 freshInput,freshBytes,originalInputBytes,now_iso=new Date().toISOString()}){
 const now=t(now_iso),post=t(source?.race_context?.start_at);
 need(ALLOWED.has(source?.race_id),'restricted to 2026-10-25 JRA three main races');
 need(Number.isFinite(now)&&Number.isFinite(post)&&now<post,'race already started');
 need(source.stage==='formal_prestart'&&source.prompt_version==='v3.13'&&
  /^[a-f0-9]{40}$/.test(source.proof_commit),'original prestart source or proof absent');
 need(prior.purchase_strategy_version==='v3.15'&&prior.status==='formal_prestart'&&
  prior.source_race_id===source.race_id&&prior.purchase_decision==='buy','official v3.15 predecessor needed');
 need(prior.source_prediction_sha256===sha(sourceBytes)&&
  prior.source_prediction_proof===source.proof_commit&&
  /^[a-f0-9]{40}$/.test(prior.proof_commit),'original source SHA and proof mismatch');
 need(t(prior.final_bets_fixed_at)<now&&t(source.final_bets_fixed_at)<t(prior.final_bets_fixed_at),
  'official v3.15 not previously frozen before this new recommendation');
 need(originalInput.race_id===source.race_id&&freshInput.race_id===source.race_id&&
  originalInput.prompt_version==='v3.13'&&freshInput.prompt_version==='v3.13'&&
  equal(originalInput.step1,freshInput.step1)&&
  equal(originalInput.strategies,freshInput.strategies)&&
  equal(originalInput.frame_map,freshInput.frame_map)&&
  equal(originalInput.race_context,freshInput.race_context)&&
  equal(originalInput.scenario_factors,freshInput.scenario_factors),
  'a forecast input or STEP1 has changed instead of only its prices');
 need(equal(source.race_context,prior.race_context)&&equal(source.race_context,freshInput.race_context),
  'wrong race context');
 const q=freshInput.market_quotes;
 need(Array.isArray(q)&&q.length>0,'no refreshed market odds');
 const quotes=new Map();
 for(const v of q){
  const k=key(v);
  need(v.quote_verified===true&&v.market_selection_id===k&&
   typeof v.source_url==='string'&&v.source_url.startsWith('https://sports.yahoo.co.jp/keiba/race/odds/')&&
   typeof v.source_capture_path==='string'&&
   v.source_capture_path.startsWith('e2e_validation/quote-evidence/')&&
   /^[a-f0-9]{64}$/.test(v.source_capture_sha256||'')&&
   Number.isFinite(t(v.observed_at))&&t(v.observed_at)<=now,
   'refreshed quote lacks complete original provider provenance '+k);
  need(!quotes.has(k),'duplicate fresh quote '+k);
  quotes.set(k,v);
 }
 // Require ALL canonical candidates from the original eight-type strategy
 // catalog, not merely a repricing of the officially selected tickets.
 const expected=new Set(originalInput.strategies.flatMap(s=>
  expandStrategy(s.type,s.strategy_kind,s.definition).map(key)));
 need(expected.size===quotes.size&&[...expected].every(k=>quotes.has(k)),
  'full catalog quotes are incomplete');
 const ages=q.map(v=>t(v.observed_at));
 const oldest=Math.min(...ages),latest=Math.max(...ages);
 need(now-oldest<=600000&&latest-oldest<=180000&&latest<post,
  'fresh quotes violate 600-second age, 180-second span, or start gate');
 const pricedSource=structuredClone(source);
 let repricedSourceLines=0;
 for(const strategy of pricedSource.purchase_strategy_evaluations||[]){
  for(const line of strategy.lines||[]){
   if(line.quote_verified!==true)continue;
   const u=quotes.get(key(line));
   need(u,'an originally verified model strategy quote absent from full-refresh '+key(line));
   Object.assign(line,{
    market_odds:u.market_odds,source_url:u.source_url,observed_at:u.observed_at,
    quote_verified:true,market_selection_id:key(line)
   });
   repricedSourceLines++;
  }
 }
 need(repricedSourceLines>0,'no source strategy quotes repriced');
 const p=structuredClone(prior);
 const originalKeys=prior.formal_bets.map(key);
 need(new Set(originalKeys).size===originalKeys.length,'old formal ticket duplication');
 p.formal_bets=prior.formal_bets.map(v=>{
  const quote=quotes.get(key(v));
  need(quote,'previously purchased ticket cannot be re-quoted '+key(v));
  return {...v,market_odds:quote.market_odds,source_url:quote.source_url,
   observed_at:quote.observed_at,quote_verified:true,market_selection_id:key(v)};
 });
 const sim=structuredClone(p);
 sim.final_bets_fixed_at=now_iso;
 const metrics=evaluateStrategy(sim.formal_bets,
  pricedSource.outcome_distributions,pricedSource.frame_map,pricedSource.race_context);
 sim.purchase_metrics={
  ...p.purchase_metrics,stake_yen:metrics.total_stake_yen,
  modeled_expected_net_profit_yen:round(metrics.expected_payout_yen_scenarios.central-metrics.total_stake_yen),
  modeled_low_expected_net_profit_yen:round(metrics.expected_payout_yen_scenarios.low-metrics.total_stake_yen),
  modeled_union_hit_probability:round(metrics.hit_probability_scenarios.central),
  modeled_net_loss_probability:round(metrics.loss_probability_scenarios.central)
 };
 const pricedBytes=JSON.stringify(pricedSource)+'\n';
 sim.source_prediction_sha256=sha(pricedBytes);
 const comparison=compareV316Shadow({source:pricedSource,sourceBytes:pricedBytes,formal:sim});
 const improved=comparison.shadow_proposal_available;
 const moneyByTicket=new Map(comparison.proposed_lines.map(x=>[key(x),x.stake_yen]));
 need(moneyByTicket.size===originalKeys.length,'stake allocator changed ticket set');
 p.formal_bets=p.formal_bets.map(v=>({...v,stake_yen:moneyByTicket.get(key(v))}));
 const groups=comparison.commands;
 let cursor=0;
 function promote(c){
  if(c.method==='pass')return c;
  const g=groups[cursor++];
  need(g&&g.category===c.category&&g.type===c.type&&g.method===c.method&&
   g.jra_input===c.jra_input&&equal(g.ticket_keys,c.ticket_keys),
   'JRA purchase-command definitions changed');
  return {...c,unit_stake_yen:g.unit_stake_yen,stake_yen:g.stake_yen};
 }
 p.regular_commands=prior.regular_commands.map(promote);
 p.medium_command=promote(prior.medium_command);
 p.large_command=promote(prior.large_command);
 need(cursor===groups.length,'new group comparison count mismatch');
 p.total_stake_yen=comparison.candidate.stake_yen;
 p.purchase_metrics={
  ...prior.purchase_metrics,stake_yen:p.total_stake_yen,ticket_count:p.formal_bets.length,
  modeled_expected_net_profit_yen:comparison.candidate.scenarios.central.expected_net_profit_yen,
  modeled_low_expected_net_profit_yen:comparison.candidate.scenarios.low.expected_net_profit_yen,
  modeled_union_hit_probability:comparison.candidate.scenarios.central.union_hit_probability,
  modeled_net_loss_probability:comparison.candidate.scenarios.central.loss_probability,
  modeled_low_net_loss_probability:comparison.candidate.scenarios.low.loss_probability
 };
 need(p.total_stake_yen<=6000&&p.total_stake_yen>=prior.total_stake_yen&&
  p.total_stake_yen-prior.total_stake_yen<=600&&
  p.total_stake_yen<=prior.total_stake_yen*1.5,
  'over budget or outside marginal exposure policy');
 need(p.formal_bets.every((x,i)=>key(x)===originalKeys[i]),'selection modified');
 p.purchase_strategy_version='v3.16';
 p.source_purchase_version='v3.15';
 p.source_purchase_proof=prior.proof_commit;
 p.source_purchase_sha256=sha(priorBytes);
 p.source_purchase_path=null;
 p.source_prediction_sha256=sha(sourceBytes);
 p.status='pending_git_proof';p.proof_commit=null;p.final_bets_fixed_at=now_iso;
 p.quote_age_max_seconds=(now-oldest)/1000;
 p.quote_capture_span_seconds=(latest-oldest)/1000;
 p.stake_optimization_audit=comparison;
 p.stake_optimization_audit.original_v315_stake_yen=prior.total_stake_yen;
 p.stake_optimization_audit.actual_fresh_price_baseline=true;
 p.stake_optimization_audit.temporary_quotation_replay_sha256=sha(pricedBytes);
 p.full_refresh_odds={
  input_source_sha256:sha(originalInputBytes),
  fresh_input_sha256:sha(freshBytes),fresh_input_path:null,
  checked_candidate_keys:expected.size,quote_count:q.length,
  repriced_source_lines:repricedSourceLines,refreshed_after_v315:true,
  original_v315_source_sha256:sha(sourceBytes),
  earliest_quote_at:new Date(oldest).toISOString(),
  latest_quote_at:new Date(latest).toISOString(),
  reference_frozen_v315_at:prior.final_bets_fixed_at,
  all_eight_type_prices_refetched:true,
  never_inherited_old_formal_price:true
 };
 p.selection_method='v3.16 original selections preserved; all eight-type source prices independently refetched and audited; bounded purchase-command capital allocation';
 p.risk_disclosure='Expected profits derive from an uncalibrated prereace outcome model and observed odds, not guaranteed real payouts. The original v3.15 stake and odds records remain immutable.';
 return {plan:p,comparison,improved,summary:{
  race_id:source.race_id,original_spend_yen:prior.total_stake_yen,
  fresh_100_yen_baseline_profit:comparison.baseline.scenarios.central.expected_net_profit_yen,
  new_spend_yen:p.total_stake_yen,new_expected_profit:comparison.candidate.scenarios.central.expected_net_profit_yen,
  fresh_quote_count:q.length,earliest_quote_at:new Date(oldest).toISOString(),
  upgraded:improved,changes:groups.filter(c=>c.unit_stake_yen>100).map(c=>({input:c.jra_input,stake:c.unit_stake_yen}))
 }};
}
if(process.argv[1]?.endsWith('/jra-build-today-fresh-v316.mjs')){
 try{
  const a=process.argv.slice(2),arg=n=>a[a.indexOf(n)+1];
  const sourcePath=arg('--source'),priorPath=arg('--prior'),
   inputPath=arg('--original-input'),freshPath=arg('--fresh'),output=arg('--output');
  need(sourcePath?.startsWith('e2e_validation/predictions/')&&
   priorPath?.startsWith('e2e_validation/predictions/')&&
   inputPath?.startsWith('e2e_validation/inputs/v313/')&&
   freshPath?.startsWith('e2e_validation/inputs/v316-fresh/')&&
   output?.startsWith('e2e_validation/snapshots/')&&!output.includes('..'),
   'unsafe file paths');
  need(!fs.existsSync(output),'immutable snapshot already exists');
  const sourceBytes=fs.readFileSync(sourcePath),priorBytes=fs.readFileSync(priorPath),
   originalInputBytes=fs.readFileSync(inputPath),freshBytes=fs.readFileSync(freshPath);
  const result=buildTodayFreshV316({
   source:JSON.parse(sourceBytes),sourceBytes,prior:JSON.parse(priorBytes),priorBytes,
   originalInput:JSON.parse(originalInputBytes),originalInputBytes,
   freshInput:JSON.parse(freshBytes),freshBytes
  });
  result.plan.source_purchase_path=priorPath;
  result.plan.full_refresh_odds.fresh_input_path=freshPath;
  fs.mkdirSync(output.slice(0,output.lastIndexOf('/')),{recursive:true});
  fs.writeFileSync(output,JSON.stringify(result.plan,null,2)+'\n');
  console.log('PASS_V316_TODAY_FULL_EIGHT_TYPE_FRESH_REPRICE',JSON.stringify(result.summary));
 }catch(e){console.error(e.stack||String(e));process.exitCode=1;}
}
