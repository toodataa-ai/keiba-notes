// v3.10 only: preserve v3.9 ability/market validation, replace single-strategy purchase gate.
import fs from 'node:fs';
import path from 'node:path';
import {validateV39} from './validate-jra-strategy-v39.mjs';
import {optimizePurchasePortfolio} from './jra-portfolio-optimizer-v310.mjs';
import {ticketKey} from './jra-strategy-engine-v39.mjs';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const near=(a,b)=>finite(a)&&Math.abs(a-b)<=Math.max(1e-6,Math.abs(b)*1e-6);
const time=x=>typeof x==='string'&&Number.isFinite(Date.parse(x));
const text=x=>typeof x==='string'&&x.trim().length>0;
const SC=['low','central','high'];
const metrics=['expected_payout_yen_scenarios','roi_scenarios','hit_probability_scenarios','full_loss_probability_scenarios','loss_probability_scenarios'];
export function validateV310(data){
 const errors=[],err=s=>errors.push(s);
 if(data.prompt_version!=='v3.10')return errors;
 const gate=data.purchase_gate?.candidates||[];
 const projected={...data,prompt_version:'v3.9',selected_strategy_id:null,best_strategy_id:null,
  best_bet_id:null,purchase_decision:'pass',
  purchase_reason_code:gate.some(x=>x.eligibility==='eligible')?'risk_high':'insufficient_local_information',
  final_bets:[],total_stake_yen:0};
 errors.push(...validateV39(projected).map(x=>'legacy STEP1/STEP2 input: '+x));
 if(data.purchase_budget_yen!==6000)err('formal v3.10 budget must be 6000 yen');
 const portfolio=data.purchase_portfolio_selection;
 if(!portfolio||typeof portfolio!=='object'){err('purchase_portfolio_selection required');return errors;}
 if(portfolio.algorithm!=='exact_zero_one_knapsack_v1'||portfolio.objective!=='maximize_central_expected_net_profit_yen')
  err('unknown purchase optimizer or objective');
 if(portfolio.budget_yen!==6000)err('portfolio cap not 6000');
 if(!text(portfolio.portfolio_id))err('portfolio id missing');
 if(!time(data.final_bets_fixed_at)||!time(data.race_context?.start_at)||Date.parse(data.final_bets_fixed_at)>=Date.parse(data.race_context.start_at))
  err('final bets must be frozen pre-start');
 if(!text(data.proof_commit))err('pre-race proof_commit required');
 let optimum;
 try{
   optimum=optimizePurchasePortfolio({
     budget_yen:6000,strategies:data.purchase_strategy_evaluations,
     outcome_distributions:data.outcome_distributions,frame_map:data.frame_map,race_context:data.race_context,
     freeze_at:data.final_bets_fixed_at,max_ticket_stake_yen:100
   });
 }catch(e){err('portfolio inputs / optimizer: '+e.message);return errors;}
 if(data.purchase_decision!==optimum.purchase_decision)err('purchase_decision disagrees with exact optimizer');
 if(data.purchase_reason_code!==optimum.purchase_reason_code)err('purchase reason disagrees with exact optimizer');
 if(portfolio.optimizer_audit?.eligible_count!==optimum.optimizer_audit.eligible_count||
   portfolio.optimizer_audit?.selected_count!==optimum.optimizer_audit.selected_count||
   portfolio.optimizer_audit?.budget_unused_yen!==optimum.optimizer_audit.budget_unused_yen||
   !near(portfolio.optimizer_audit?.expected_net_profit_yen,optimum.optimizer_audit.expected_net_profit_yen))
   err('portfolio optimizer objective/count/audit differs from optimum');
 const selected=Array.isArray(portfolio.selected_lines)?portfolio.selected_lines:[];
 const target=optimum.selected_lines;
 if(selected.length!==target.length)err('portfolio selected line count differs from exact optimum');
 const byKey=new Map(target.map(t=>[t.key,t])),seen=new Set();
 for(const line of selected){
   let k;try{k=ticketKey(line.type,line.selection)}catch(e){err('invalid portfolio ticket '+e.message);continue;}
   if(seen.has(k))err('portfolio duplicates same exact ticket');seen.add(k);
   const t=byKey.get(k);
   if(!t||JSON.stringify(t.market_odds)!==JSON.stringify(line.market_odds)||
     t.source_url!==line.source_url||t.observed_at!==line.observed_at||
     t.stake_yen!==line.stake_yen||line.market_selection_id!==k||
     JSON.stringify(t.origin_strategy_ids)!==JSON.stringify(line.origin_strategy_ids))
     err('portfolio line differs from verified optimum exact ticket');
 }
 if([...byKey.keys()].some(k=>!seen.has(k)))err('portfolio missing optimizer-selected ticket');
 for(const field of metrics){
   if(optimum.selected_lines.length===0){
     if(portfolio[field]!==null)err('pass metrics should be null '+field);
   }else for(const sc of SC)if(!near(portfolio[field]?.[sc],optimum[field]?.[sc]))err('portfolio correlated metric mismatch '+field+' '+sc);
 }
 if(portfolio.total_stake_yen!==optimum.total_stake_yen||
  data.total_stake_yen!==optimum.total_stake_yen||
  data.total_stake_yen>6000)err('final portfolio stake inconsistent with 6000-yen cap');
 if(data.purchase_decision==='pass'){
   if(data.selected_strategy_id!==null||data.best_strategy_id!==null||
     data.best_bet_id!==null||data.total_stake_yen!==0||
     !Array.isArray(data.final_bets)||data.final_bets.length!==0)err('pass must have no purchase');
 }else if(data.purchase_decision==='buy'){
   if(data.selected_strategy_id!==portfolio.portfolio_id||data.best_strategy_id!==portfolio.portfolio_id)
     err('legacy selected strategy must point to full combined portfolio');
   if(!Array.isArray(data.final_bets)||data.final_bets.length!==target.length)
     err('final_bets must exactly reflect all selected portfolio lines');
   const finalKeys=new Set(),ids=new Set();
   for(const bet of data.final_bets||[]){
     let k;try{k=ticketKey(bet.type,bet.selection)}catch(e){err('invalid final_bets ticket');continue;}
     if(finalKeys.has(k)||ids.has(bet.id))err('duplicate purchased line/id');
     finalKeys.add(k);ids.add(bet.id);
     const t=byKey.get(k);
     if(!t||bet.stake_yen!==t.stake_yen||JSON.stringify(bet.market_odds)!==JSON.stringify(t.market_odds)||
       bet.source_url!==t.source_url||bet.observed_at!==t.observed_at||
       bet.market_selection_id!==k)err('purchased ticket differs from portfolio candidate quote');
   }
   if([...byKey.keys()].some(k=>!finalKeys.has(k)))err('purchased lines omit chosen portfolio ticket');
   if(!text(data.best_bet_id)||!(data.final_bets||[]).some(b=>b.id===data.best_bet_id))
     err('best_bet_id must refer to purchased line');
   if((data.final_bets||[]).some(b=>Date.parse(b.observed_at)>Date.parse(data.final_bets_fixed_at)))
     err('a purchased quote was observed after freeze');
 }
 return errors;
}
if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(new URL(import.meta.url).pathname)){
 let checked=0,errors=[];const root='e2e_validation/predictions';
 if(fs.existsSync(root))for(const folder of fs.readdirSync(root,{withFileTypes:true})){
   if(!folder.isDirectory())continue;
   for(const file of fs.readdirSync(path.join(root,folder.name)).filter(n=>n.endsWith('.json'))){
     const p=path.join(root,folder.name,file),data=JSON.parse(fs.readFileSync(p,'utf8'));
     if(data.prompt_version!=='v3.10')continue;checked++;
     for(const e of validateV310(data))errors.push(p+': '+e);
   }
 }
 if(errors.length){console.error(errors.join('\n'));process.exit(1);}
 console.log('v3.10 portfolio contract: '+checked+' new formal predictions verified; all legacy versions untouched');
}
