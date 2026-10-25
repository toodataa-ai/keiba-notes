// JRA v3.16 forward-only purchase amount overlay, using an immutable prior v3.15
// public purchase and SHA-verified source v3.13 prerace distribution.
// Will not change selected tickets or investment when risk gates do not pass.
import fs from 'node:fs';
import crypto from 'node:crypto';
import {compareV316Shadow} from './jra-stake-optimizer-v316-shadow.mjs';
import {ticketKey} from './jra-strategy-engine-v39.mjs';
const must=(ok,m)=>{if(!ok)throw Error('V316_FORMAL_BLOCKER: '+m);};
const sha256=b=>crypto.createHash('sha256').update(b).digest('hex');
const key=x=>ticketKey(x.type,x.selection);
const millis=x=>Date.parse(x);
const sum=(xs,fn)=>xs.reduce((s,x)=>s+fn(x),0);
const round=x=>Math.round(x*10000)/10000;
export function buildV316FormalPlan({source,sourceBytes,prior,priorBytes,now_iso=new Date().toISOString()}){
 const now=millis(now_iso),start=millis(source?.race_context?.start_at);
 must(Number.isFinite(now)&&Number.isFinite(start)&&now<start,'only before actual race start');
 must(sourceBytes&&priorBytes&&prior?.status==='formal_prestart','original immutable prestart files required');
 must(prior.purchase_decision==='buy'&&prior.formal_bets?.length>0,
   'prior formal PASS needs no reallocation');
 must(millis(prior.final_bets_fixed_at)<now,'formal v3.15 has not been frozen yet');
 must(prior.quote_age_max_seconds<=600&&prior.quote_capture_span_seconds<=180,
   'prior official odds were not fresh');
 // A fresh new v3.16 seal cannot reuse evidence whose oldest quotation is >600s old.
 must((now-millis(prior.final_bets_fixed_at))/1000+prior.quote_age_max_seconds<=600,
   'odds are stale at new v3.16 purchase freeze: recapture source quotes');
 must(prior.source_prediction_sha256===sha256(sourceBytes),'v3.13 source SHA mismatch');
 const comparison=compareV316Shadow({source,sourceBytes,formal:prior});
 if(!comparison.shadow_proposal_available)return {status:'no_change',reason:comparison.reason,comparison};
 const modified=structuredClone(prior);
 const adjustedByKey=new Map(comparison.proposed_lines.map(x=>[key(x),x]));
 must(adjustedByKey.size===prior.formal_bets.length,'v3.16 ticket identity mismatch');
 modified.formal_bets=prior.formal_bets.map(x=>{
  const expected=adjustedByKey.get(key(x));
  must(expected&&expected.stake_yen>=x.stake_yen&&expected.stake_yen%100===0,
    'unexpected ticket substitution or stake decrease');
  return {...x,stake_yen:expected.stake_yen};
 });
 const commands=comparison.commands;
 let offset=0;
 const convert=c=>{
  if(!c||c.method==='pass')return c;
  const shadow=commands[offset++];
  must(shadow.category===c.category&&shadow.type===c.type&&shadow.method===c.method&&
   shadow.jra_input===c.jra_input&&shadow.points===c.points&&
   JSON.stringify(shadow.ticket_keys)===JSON.stringify(c.ticket_keys),
   'existing JRA input and command expansion changed');
  return {...c,unit_stake_yen:shadow.unit_stake_yen,stake_yen:shadow.stake_yen};
 };
 modified.regular_commands=prior.regular_commands.map(convert);
 modified.medium_command=convert(prior.medium_command);
 modified.large_command=convert(prior.large_command);
 must(offset===commands.length,'shadow purchase command count differs');
 const total=sum(modified.formal_bets,x=>x.stake_yen);
 must(total===comparison.candidate.stake_yen&&total<=6000&&
  total>prior.total_stake_yen,'no provable bounded beneficial stake increase');
 must(sum([...modified.regular_commands,modified.medium_command,modified.large_command]
  .filter(c=>c.method!=='pass'),x=>x.stake_yen)===total,
  'purchase operation price not consistent with formal ticket totals');
 const central=comparison.candidate.scenarios.central;
 const low=comparison.candidate.scenarios.low;
 const base=prior.purchase_metrics;
 modified.purchase_strategy_version='v3.16';
 modified.source_purchase_version='v3.15';
 modified.source_purchase_proof=prior.proof_commit;
 modified.source_purchase_sha256=sha256(priorBytes);
 modified.source_purchase_path=null; // CLI sets canonical original pathname
 modified.status='pending_git_proof';modified.proof_commit=null;
 modified.final_bets_fixed_at=now_iso;
 modified.total_stake_yen=total;
 modified.purchase_metrics={
  ...base,stake_yen:total,ticket_count:modified.formal_bets.length,
  modeled_expected_net_profit_yen:central.expected_net_profit_yen,
  modeled_low_expected_net_profit_yen:low.expected_net_profit_yen,
  modeled_union_hit_probability:central.union_hit_probability,
  modeled_net_loss_probability:central.loss_probability,
  modeled_low_net_loss_probability:low.loss_probability
 };
 modified.comparison_to_v313={
  ...prior.comparison_to_v313,
  expected_profit_yen:round((prior.comparison_to_v313?.expected_profit_yen??0)+
   comparison.delta.central_expected_profit_yen)
 };
 modified.stake_optimization_audit={
  ...comparison,
  // The shadow recommendation itself is NOT active; this version undergoes
  // an independent formal prestart Git proof before publication.
  authorization:'user-approved-v3.16-forward-only-variable-stake',
  prior_formal_fixed_at:prior.final_bets_fixed_at,
  formal_pending_fixed_at:now_iso
 };
 modified.selection_method='v3.16 bounded command-uniform 100-yen stake reallocation with unchanged tickets; independent SHA and Git proof; central EV/low-scenario/net-loss guard';
 modified.risk_disclosure='Model probabilities not calibrated; 100-yen fixed source preserved; purchased amounts are only a model-based recommendation, not guaranteed results.';
 return {status:'candidate',plan:modified,comparison};
}
if(process.argv[1]?.endsWith('/jra-build-formal-stake-v316.mjs')){
 try{
  const a=process.argv.slice(2),arg=x=>a[a.indexOf(x)+1];
  const src=arg('--source'),base=arg('--prior'),out=arg('--output');
  must(src?.startsWith('e2e_validation/predictions/')&&base?.startsWith('e2e_validation/predictions/')&&
   out?.startsWith('e2e_validation/snapshots/')&&!out.includes('..'),'strict paths required');
  must(!fs.existsSync(out),'immutable output already exists');
  const sourceBytes=fs.readFileSync(src),priorBytes=fs.readFileSync(base);
  const result=buildV316FormalPlan({
   source:JSON.parse(sourceBytes),sourceBytes,prior:JSON.parse(priorBytes),priorBytes
  });
  if(result.status==='no_change'){
   console.log('PASS_V316_NO_BET_CHANGE',JSON.stringify({source:src,prior:base,reason:result.reason}));
   process.exit(20); // workflow interprets this as a NO-CHANGE success, not as published.
  }
  const plan=result.plan;plan.source_purchase_path=base;
  fs.mkdirSync(out.slice(0,out.lastIndexOf('/')),{recursive:true});
  fs.writeFileSync(out,JSON.stringify(plan,null,2)+'\n');
  console.log('V316_FRESH_PREREACE_SHADOW_ADOPTED',
   JSON.stringify({race:plan.source_race_id,source_purchase_proof:plan.source_purchase_proof,
    original_yen:result.comparison.baseline.stake_yen,
    new_yen:plan.total_stake_yen,ev_delta:result.comparison.delta.central_expected_profit_yen,
    changed_commands:result.comparison.commands.filter(x=>x.unit_stake_yen>100)}));
 }catch(e){console.error(e.stack||String(e));process.exitCode=1}
}
