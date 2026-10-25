// JRA v3.16 CANDIDATE: stake-sizing-only research. Never publish or mutate official bets.
// Replays the existing v3.15 purchase operations against the immutable v3.13
// joint prestart outcome model. Exhaustive over bounded 100-yen command increments.
import fs from 'node:fs';
import crypto from 'node:crypto';
import {ticketKey,oddsFloor,matches} from './jra-strategy-engine-v39.mjs';

export const V316_SHADOW_POLICY=Object.freeze({
 version:'v3.16-shadow-v1',
 budget_yen:6000,unit_step_yen:100,
 maximum_regular_unit_stake_yen:300,
 maximum_added_exposure_yen:600,
 maximum_total_stake_multiplier:1.5,
 maximum_central_loss_probability_increase:0,
 maximum_low_loss_probability_increase:0.005,
 minimum_expected_profit_gain_yen:10,
 minimum_low_scenario_expected_profit_gain_yen:0,
 allow_speculative_stake_increase:false,
 release_to_formal:false
});
const must=(condition,reason)=>{if(!condition)throw Error('V316_SHADOW_BLOCKER: '+reason);};
const money=x=>Math.round(x*10000)/10000;
const sha256=x=>crypto.createHash('sha256').update(x).digest('hex');
const goodSha=x=>typeof x==='string'&&/^[0-9a-f]{40}$/.test(x);
const finite=x=>Number.isFinite(x);
const key=x=>ticketKey(x.type,x.selection);
const lossMargin=1e-8;
const SCENARIOS=['low','central','high'];
const unique=x=>new Set(x).size===x.length;
const sum=(xs,f)=>xs.reduce((s,x,i)=>s+f(x,i),0);

function validateAndGroup(source,sourceBytes,formal,policy){
 must(source?.prompt_version==='v3.13'&&source?.stage==='formal_prestart',
  'immutable v3.13 formal prestart source required');
 must(formal?.purchase_strategy_version==='v3.15'&&formal?.source_race_id===source.race_id,
  'sealed v3.15 purchase for the same race required');
 must(goodSha(source.proof_commit)&&goodSha(formal.proof_commit)&&
   source.proof_commit===formal.source_prediction_proof,'original proof chain missing');
 must(sha256(sourceBytes)===formal.source_prediction_sha256,'original prediction SHA256 mismatch');
 const freeze=Date.parse(formal.final_bets_fixed_at);
 must(finite(freeze)&&freeze>Date.parse(source.final_bets_fixed_at)&&
   freeze<Date.parse(source.race_context?.start_at),
  'original formal purchase not frozen before the start');
 must(Number.isInteger(policy.budget_yen)&&policy.budget_yen>0&&
   policy.budget_yen<=6000,'budget cap invalid');
 must(Array.isArray(formal.formal_bets)&&Array.isArray(formal.regular_commands)&&
   formal.regular_commands.length<=3,'v3.15 purchase command structure missing');
 const lines=formal.formal_bets;
 const lineKeys=lines.map(key);
 must(unique(lineKeys),'repeated bet in frozen formal purchase');
 const quoted=new Map();
 for(const s of source.purchase_strategy_evaluations||[])for(const l of s.lines||[]){
  if(l.quote_verified!==true)continue;
  const k=key(l),prev=quoted.get(k);
  if(prev){
   must(prev.source_url===l.source_url&&prev.observed_at===l.observed_at&&
    JSON.stringify(prev.market_odds)===JSON.stringify(l.market_odds),
    'contradictory original quotes');
  }else quoted.set(k,l);
 }
 for(const l of lines){
  must(l.quote_verified===true&&l.market_selection_id===key(l)&&
    oddsFloor(l.market_odds)!==null&&l.stake_yen===100,
    'frozen verified 100-yen priced ticket required');
  const q=quoted.get(key(l));
  must(q&&q.market_selection_id===key(l)&&q.source_url===l.source_url&&
    q.observed_at===l.observed_at&&
    JSON.stringify(q.market_odds)===JSON.stringify(l.market_odds),
    'priced ticket must be traced exactly to the frozen v3.13 quote');
  must(Date.parse(l.observed_at)<=freeze,'quote timestamp after purchase freeze');
 }
 const commandRows=[...formal.regular_commands,
   formal.medium_command,formal.large_command].filter(Boolean);
 const consumed=new Set();
 const groups=[];
 for(const c of commandRows){
  if(c.method==='pass'){must(!c.points&&!c.stake_yen,'pass command has stake');continue;}
  must(Array.isArray(c.ticket_keys)&&unique(c.ticket_keys)&&c.ticket_keys.length===c.points&&
   c.stake_yen===100*c.points&&c.unit_stake_yen===100,'invalid original purchase command expansion');
  for(const k of c.ticket_keys){
   must(lineKeys.includes(k)&&!consumed.has(k),'command overlap or unknown frozen ticket');
   consumed.add(k);
  }
  const isRegular=c.category==='通常';
  groups.push({category:c.category,type:c.type,method:c.method,
   jra_input:c.jra_input,point_count:c.points,ticket_keys:[...c.ticket_keys],
   lines:c.ticket_keys.map(k=>lines[lineKeys.indexOf(k)]),
   max_unit_yen:isRegular?policy.maximum_regular_unit_stake_yen:100});
 }
 must(consumed.size===lines.length,'frozen purchase tickets not fully covered by command operations');
 must(formal.total_stake_yen===lines.length*100&&
   formal.total_stake_yen<=policy.budget_yen,'baseline purchase total not conserved');
 return groups;
}

function buildOutcomeCache(source,groups){
 const results={};
 for(const sc of SCENARIOS){
  const outcomes=source.outcome_distributions?.[sc];
  must(Array.isArray(outcomes)&&outcomes.length,'missing prestart joint outcomes '+sc);
  const entries=[];let mass=0;
  const finishes=new Set();
  for(const o of outcomes){
   must(Array.isArray(o.finish)&&o.finish.length===3&&unique(o.finish)&&
     finite(o.probability)&&o.probability>=0,'bad joint outcome '+sc);
   const f=JSON.stringify(o.finish);
   must(!finishes.has(f),'repeated outcome '+sc);finishes.add(f);
   mass+=o.probability;
   const payoutAt100=groups.map(c=>sum(c.lines,l=>
     matches(l,o.finish,source.frame_map,source.race_context)?
       100*oddsFloor(l.market_odds):0));
   entries.push({probability:o.probability,payoutAt100});
  }
  must(Math.abs(mass-1)<=1e-5,'joint outcome probability not normalized '+sc);
  results[sc]=entries;
 }
 return results;
}

function measure(units,groups,cache){
 const stake=sum(groups,(g,i)=>g.point_count*units[i]);
 const scenarios={};
 for(const sc of SCENARIOS){
  let expectation=0,win=0,loss=0,full=0;
  for(const o of cache[sc]){
   let payout=0;
   for(let i=0;i<units.length;i++)payout+=o.payoutAt100[i]*(units[i]/100);
   expectation+=o.probability*payout;
   if(payout>0)win+=o.probability;else full+=o.probability;
   if(payout+lossMargin<stake)loss+=o.probability;
  }
  scenarios[sc]={
   expected_net_profit_yen:money(expectation-stake),
   loss_probability:money(loss),
   union_hit_probability:money(win),
   full_loss_probability:money(full)
  };
 }
 return {stake_yen:stake,scenarios};
}

function isBetter(x,best){
 if(!best)return true;
 const a=x.metrics.scenarios.central,b=best.metrics.scenarios.central;
 if(a.expected_net_profit_yen>b.expected_net_profit_yen+lossMargin)return true;
 if(a.expected_net_profit_yen+lossMargin<b.expected_net_profit_yen)return false;
 if(a.loss_probability+lossMargin<b.loss_probability)return true;
 if(a.loss_probability>b.loss_probability+lossMargin)return false;
 if(x.metrics.stake_yen<best.metrics.stake_yen)return true;
 if(x.metrics.stake_yen>best.metrics.stake_yen)return false;
 return x.units.join(',')<best.units.join(',');
}

export function compareV316Shadow({source,sourceBytes,formal,policy=V316_SHADOW_POLICY}){
 must(typeof sourceBytes==='string'||Buffer.isBuffer(sourceBytes),'source bytes required for integrity check');
 const groups=validateAndGroup(source,sourceBytes,formal,policy);
 const baseUnits=groups.map(()=>100);
 if(!groups.length)return {
  version:'v3.16-shadow-v1',race_id:source.race_id,activated:false,reason:'formal_pass_no_bets',
  baseline:null,candidate:null,command_count:0,source_prediction_sha256:sha256(sourceBytes),
  source_proof_commit:source.proof_commit,formal_proof_commit:formal.proof_commit,
  formal_unchanged:true,publication_allowed:false
 };
 const cache=buildOutcomeCache(source,groups);
 const baseline=measure(baseUnits,groups,cache);
 must(baseline.stake_yen===formal.total_stake_yen,'baseline stake differs from the sealed purchase');
 // Guard against an accidental change to the replay evaluator or source distributions.
 const fm=formal.purchase_metrics;
 must(finite(fm?.modeled_expected_net_profit_yen)&&
  Math.abs(fm.modeled_expected_net_profit_yen-baseline.scenarios.central.expected_net_profit_yen)<0.1&&
  Math.abs(fm.modeled_low_expected_net_profit_yen-baseline.scenarios.low.expected_net_profit_yen)<0.1&&
  Math.abs(fm.modeled_net_loss_probability-baseline.scenarios.central.loss_probability)<0.0001,
  'recalculated baseline differs from published v3.15 metrics');
 const exposureCap=Math.min(policy.budget_yen,
  baseline.stake_yen+policy.maximum_added_exposure_yen,
  Math.floor(baseline.stake_yen*policy.maximum_total_stake_multiplier/100)*100);
 let considered=0,passed=0,best=null;
 const units=baseUnits.slice();
 function enumerate(index){
  if(index===groups.length){
   const total=sum(groups,(g,i)=>g.point_count*units[i]);
   if(total>exposureCap)return;
   considered++;
   const current=measure(units,groups,cache);
   const low=current.scenarios.low,central=current.scenarios.central;
   if(low.expected_net_profit_yen+lossMargin<
    baseline.scenarios.low.expected_net_profit_yen+policy.minimum_low_scenario_expected_profit_gain_yen)return;
   if(central.loss_probability>
    baseline.scenarios.central.loss_probability+policy.maximum_central_loss_probability_increase+lossMargin)return;
   if(low.loss_probability>
    baseline.scenarios.low.loss_probability+policy.maximum_low_loss_probability_increase+lossMargin)return;
   if(central.expected_net_profit_yen<
    baseline.scenarios.central.expected_net_profit_yen+policy.minimum_expected_profit_gain_yen-lossMargin)return;
   passed++;
   const candidate={units:[...units],metrics:current};
   if(isBetter(candidate,best))best=candidate;
   return;
  }
  for(let unit=100;unit<=groups[index].max_unit_yen;unit+=100){
   units[index]=unit;
   if(sum(groups.slice(0,index+1),(g,j)=>g.point_count*units[j])+
    sum(groups.slice(index+1),g=>g.point_count*100)>exposureCap)continue;
   enumerate(index+1);
  }
  units[index]=100;
 }
 enumerate(0);
 const chosen=best?.metrics??baseline;
 const finalUnits=best?.units??baseUnits;
 const commands=groups.map((g,i)=>({
  category:g.category,type:g.type,method:g.method,jra_input:g.jra_input,
  points:g.point_count,unit_stake_yen:finalUnits[i],
  stake_yen:g.point_count*finalUnits[i],ticket_keys:g.ticket_keys,
  original_unit_stake_yen:100,original_stake_yen:g.point_count*100
 }));
 const ticketKeys=groups.flatMap(g=>g.ticket_keys);
 const proposedLines=groups.flatMap((g,i)=>g.lines.map(l=>({
   ...l,stake_yen:finalUnits[i]
 })));
 must(unique(ticketKeys)&&proposedLines.length===formal.formal_bets.length&&
  sum(proposedLines,x=>x.stake_yen)===chosen.stake_yen&&
  chosen.stake_yen<=policy.budget_yen,'shadow amount conservation failed');
 must(proposedLines.every(l=>key(l)===l.market_selection_id),'ticket identity changed');
 return {
  version:'v3.16-shadow-v1',race_id:source.race_id,
  activated:false,shadow_proposal_available:!!best,
  reason:best?'bounded_risk_eligible_stake_reallocation':'no_qualifying_improvement',
  baseline,candidate:chosen,delta:{
   investment_yen:chosen.stake_yen-baseline.stake_yen,
   central_expected_profit_yen:money(chosen.scenarios.central.expected_net_profit_yen-
     baseline.scenarios.central.expected_net_profit_yen),
   low_expected_profit_yen:money(chosen.scenarios.low.expected_net_profit_yen-
     baseline.scenarios.low.expected_net_profit_yen),
   central_loss_probability_pp:money(100*(chosen.scenarios.central.loss_probability-
     baseline.scenarios.central.loss_probability))
  },commands,proposed_lines:proposedLines,
  audit:{combinations_considered:considered,qualified_combinations:passed,
   unchanged_ticket_set:true,unchanged_purchase_command_count:true,
   unchanged_hit_probability:Math.abs(baseline.scenarios.central.union_hit_probability-
    chosen.scenarios.central.union_hit_probability)<1e-8,
   speculation_stays_at_100_yen:commands.filter(x=>x.category!=='通常')
     .every(x=>x.unit_stake_yen===100),
   modeled_probabilities_not_calibrated:true,
   formal_purchase_and_published_reports_not_modified:true,
   exhaustive_only_within_frozen_selection_and_bounded_stake_grid:true},
  source_prediction_sha256:sha256(sourceBytes),
  source_proof_commit:source.proof_commit,formal_proof_commit:formal.proof_commit,
  formal_unchanged:true,publication_allowed:false
 };
}

export function replayV316Files(sourcePath,formalPath,outputPath=null){
 const sourceBytes=fs.readFileSync(sourcePath);
 const source=JSON.parse(sourceBytes);
 const formal=JSON.parse(fs.readFileSync(formalPath));
 const candidate=compareV316Shadow({source,sourceBytes,formal});
 if(outputPath){
  must(outputPath.startsWith('/tmp/')||outputPath.startsWith('docs/staging/data/v316-shadow/'),
   'research-only output path required');
  must(!fs.existsSync(outputPath),'shadow replay must not overwrite a previous result');
  fs.mkdirSync((awaitImportPathDirname)(outputPath),{recursive:true});
  fs.writeFileSync(outputPath,JSON.stringify(candidate,null,2)+'\n');
 }
 return candidate;
}
const awaitImportPathDirname=x=>x.slice(0,x.lastIndexOf('/'))||'.';
