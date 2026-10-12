// JRA purchase-only v3.15 formal proposal from one immutably sealed v3.13 prestart
// prediction. The source is preserved; only a new plan and new current pointer are created.
import fs from 'node:fs';
import crypto from 'node:crypto';
import {compareThreePlusAna} from './jra-three-plus-ana-shadow-v1.mjs';
import {expandStrategy,ticketKey} from './jra-strategy-engine-v39.mjs';
const fail=m=>{throw Error('JRA_V315_BLOCKER: '+m)};
const need=(x,m)=>{if(!x)fail(m)};
const key=x=>ticketKey(x.type,x.selection);
const money=xs=>xs.reduce((a,x)=>a+x.stake_yen,0);
const timestamp=x=>Date.parse(x);
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
export function buildFormalThreeCommandPlan(source,srcBytes,{now_iso=new Date().toISOString(),max_quote_age_ms=600000}={}){
 need(source.prompt_version==='v3.13'&&source.stage==='formal_prestart','sealed v3.13 prediction required');
 need(/^[0-9a-f]{40}$/.test(source.proof_commit||''),'valid historical proof SHA required');
 need(source.race_context?.start_at,'missing scheduled race time');
 const now=timestamp(now_iso),start=timestamp(source.race_context.start_at);
 need(Number.isFinite(now)&&now<start,'race already started');
 need(Array.isArray(source.purchase_strategy_evaluations)&&source.purchase_strategy_evaluations.length,'priced strategy catalog absent');
 need(Array.isArray(source.final_bets)&&source.final_bets.length>0,'prior official final_bets unavailable');
 need(now>timestamp(source.final_bets_fixed_at),'source must be sealed before new purchase decision');
 // v3.13 market freshness <=10m is mandatory for formal action: no 08:50
 // odds can quietly become a new official selection many minutes later.
 const observed=source.purchase_strategy_evaluations.flatMap(s=>s.lines||[]).map(x=>timestamp(x.observed_at));
 need(observed.length>0&&observed.every(x=>Number.isFinite(x)&&x<=now),'complete quote time evidence required');
 const oldest=Math.min(...observed),newest=Math.max(...observed);
 need(now-oldest<=max_quote_age_ms,'market quotes older than 10min; MUST re-fetch ALL verified odds first');
 need(newest-oldest<=180000,'market capture span >180 seconds');
 need(source.market_quote_audit?.verified>0,'source verified quote audit missing');
 const args={budget_yen:6000,strategies:source.purchase_strategy_evaluations,
  formal_final_bets:source.final_bets,frame_map:source.frame_map,
  outcome_distributions:source.outcome_distributions,race_context:source.race_context,
  freeze_at:source.final_bets_fixed_at};
 const result=compareThreePlusAna(args);
 need(result.status==='three_plus_two_holes_shadow_candidate'&&result.regular_commands.length>0,
    'no valid positive-EV 3-action purchase set; publish a documented PASS rather than fabricate ticket');
 const regular=result.regular_commands,side=[result.medium_command,result.large_command];
 need(regular.length<=3&&side.length===2,'more than 3+2 commands');
 need(side[0].category==='中穴'&&side[1].category==='大穴','incorrect speculative tiers');
 const tickets=result.proposed_lines.map(x=>({...x,quote_verified:true,
    market_selection_id:key(x)}));
 need(new Set(tickets.map(key)).size===tickets.length,'duplicate tickets');
 need(tickets.length===regular.reduce((n,x)=>n+x.points,0)+side.reduce((n,x)=>n+x.points,0),
    'command expansion differs from final ticket count');
 need(money(tickets)<=6000,'overbudget');
 for(const c of [...regular,...side]){
  if(c.method==='pass')continue;
  const expanded=expandStrategy(c.type,c.method,c.definition).map(key).sort();
  need(expanded.length===c.points&&c.stake_yen===c.points*100,'cost mismatch');
  need(JSON.stringify(expanded)===JSON.stringify([...c.ticket_keys].sort()),'inaccurate JRA purchase instructions');
 }
 const sourceQuoted=new Map(source.purchase_strategy_evaluations.flatMap(s=>s.lines||[]).map(x=>[key(x),x]));
 for(const t of tickets){
  const quote=sourceQuoted.get(key(t));
  need(quote?.quote_verified===true&&quote.market_selection_id===key(t)&&
    JSON.stringify(quote.market_odds)===JSON.stringify(t.market_odds)&&
    quote.source_url===t.source_url&&quote.observed_at===t.observed_at,'quote provenance mismatch');
 }
 // The original model including all runner STEP1 items is referenced by SHA; never re-score.
 return {
  schema_version:1,purchase_strategy_version:'v3.15',model_version:'v3.13',
  status:'pending_git_proof',source_race_id:source.race_id,
  source_prediction_sha256:hash(srcBytes),source_prediction_proof:source.proof_commit,
  source_prediction_path:source.__source_path || null,
  race_context:source.race_context,
  step1_fixed_at:source.step1_fixed_at,
  source_final_bets_fixed_at:source.final_bets_fixed_at,
  final_bets_fixed_at:now_iso,proof_commit:null,
  quote_age_max_seconds:(now-oldest)/1000,quote_capture_span_seconds:(newest-oldest)/1000,
  formal_bets:tickets,regular_commands:regular,medium_command:side[0],large_command:side[1],
  total_stake_yen:money(tickets),purchase_decision:tickets.length?'buy':'pass',
  command_count:regular.length+side.filter(c=>c.method!=='pass').length,
  ticket_count:tickets.length,
  purchase_metrics:result.summary,exacta_coverage_audit:result.exacta_coverage_audit,
  comparison_to_v313:result.change_vs_formal,
  risk_disclosure:'3+2 actions may significantly lower union hit probability compared with original 60-ticket source. No guaranteed profit. Original odds and v3.13 score are unchanged.',
  selection_method:'bounded priced complete command sets, exact tuple expansion, 0 duplicated tickets, max 6000 yen. Not a proof of global optimum.',
  old_original_immutable:true
 };
}
if(process.argv[1]?.endsWith('/jra-build-formal-3action-v315.mjs')){
 try{
  const args=process.argv.slice(2),src=args[args.indexOf('--source')+1],out=args[args.indexOf('--output')+1];
  need(src&&out&&src.startsWith('e2e_validation/predictions/')&&
       out.startsWith('e2e_validation/snapshots/')&&!out.includes('..'),'safe CLI paths required');
  need(!fs.existsSync(out),'refusing historical snapshot overwrite');
  const b=fs.readFileSync(src),o=JSON.parse(b);o.__source_path=src;
  const plan=buildFormalThreeCommandPlan(o,b);
  fs.mkdirSync(out.split('/').slice(0,-1).join('/'),{recursive:true});
  fs.writeFileSync(out,JSON.stringify(plan,null,2)+'\n');
  console.log('FORMAL_V315_RESEARCH_SNAPSHOT',o.race_id,plan.regular_commands.length,
    plan.medium_command.method,plan.large_command.method,
    plan.ticket_count,plan.total_stake_yen,
    'max_quote_age_seconds',plan.quote_age_max_seconds);
 }catch(e){console.error(e.stack??e);process.exitCode=1;}
}

