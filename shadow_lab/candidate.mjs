// Independent Shadow adapter. Existing formal modules are imported read-only.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {assembleV313} from '../.github/scripts/jra-prestart-pipeline-v313.mjs';
import {buildFormalThreeCommandPlan} from '../.github/scripts/jra-build-formal-3action-v315.mjs';
import {buildV316FormalPlan} from '../.github/scripts/jra-build-formal-stake-v316.mjs';
import {fullFieldOutcomes} from '../.github/scripts/jra-prestart-pipeline-v312.mjs';
import {evaluateStrategy} from '../.github/scripts/jra-strategy-engine-v39.mjs';
const p=JSON.parse(fs.readFileSync(process.argv[2]||0,'utf8'));
const copy=x=>JSON.parse(JSON.stringify(x));
const must=(v,m)=>{if(!v)throw Error(m);};
const input=copy(p.input), baseline=copy(p.baseline), kind=p.theme;
must(input.race_id===baseline.race_id,'race mismatch');
must(Date.now()<Date.parse(input.race_context.start_at),'start passed');
must(baseline.prompt_version==='v3.13','unsupported formal version');
const reproduced=assembleV313(copy(input),baseline.final_bets_fixed_at);
for(const key of ['step1_ranking','outcome_distributions','final_bets','total_stake_yen'])
 must(JSON.stringify(reproduced[key])===JSON.stringify(baseline[key]),'formal/input reproduction mismatch: '+key);
const sourceBaseline=copy(baseline);
if(p.purchase){
 must(['v3.15','v3.16'].includes(p.purchase.purchase_strategy_version),'unsupported current purchase policy');
 must(p.purchase.source_prediction_sha256===createHash('sha256').update(p.baseline_bytes).digest('hex'),'current purchase source hash mismatch');
 must(p.purchase.source_race_id===baseline.race_id,'current purchase race mismatch');
 baseline.final_bets=copy(p.purchase.formal_bets);baseline.total_stake_yen=p.purchase.total_stake_yen;
 baseline.purchase_strategy_version=p.purchase.purchase_strategy_version;
 baseline.current_purchase_original=p.purchase;
}
let candidate;
if(kind==='ticket_portfolio'){
 // Fixed v1 hypothesis: remove lines with nonpositive low-scenario EV;
 // size the remaining original lines at 100 yen. Eight-type evaluations stay.
 candidate=copy(baseline);
 const selected=baseline.final_bets.filter(l=>{
   const s=evaluateStrategy([{...l,stake_yen:100}],baseline.outcome_distributions,baseline.frame_map,baseline.race_context);
   return s.expected_payout_yen_scenarios.low>100;
 }).map(l=>({...l,stake_yen:100}));
 candidate.final_bets=selected.map((l,i)=>({...l,id:'S'+i}));
 candidate.total_stake_yen=selected.length*100;
 must(candidate.total_stake_yen<=6000,'budget exceeded');
 candidate.purchase_portfolio_selection={...baseline.purchase_portfolio_selection,selected_lines:selected,
   total_stake_yen:candidate.total_stake_yen,shadow_rule:'positive_low_EV_equal_100_v1'};
 candidate.shadow_rejections=baseline.final_bets.filter(l=>!selected.some(s=>s.type===l.type&&JSON.stringify(s.selection)===JSON.stringify(l.selection)));
}else{
 const rows=input.step1.runners;
 const values=rows.map(r=>r.win_probability*p.multipliers[String(r.horse_number)]);
 const total=values.reduce((a,b)=>a+b,0);
 rows.forEach((r,i)=>{r.win_probability=values[i]/total;});
 const rank=[...rows].sort((a,b)=>b.win_probability-a.win_probability||a.horse_number-b.horse_number);
 if(!kind.startsWith('E')){
   rank.forEach((r,i)=>{r.mark=['◎','○','▲','△'][Math.min(i,3)];});
   if(p.factor_index!==null)rows.forEach(r=>{r.factor_grades[p.factor_index]=p.grades[String(r.horse_number)];});
   // The approved STEP2 algorithm and exact quote catalog are reused unchanged.
   candidate=assembleV313(input,p.cutoff);
   if(p.purchase&&candidate.final_bets.length){
     // Reuse the current purchase rules in memory; this is never a formal seal.
     candidate.stage='formal_prestart';candidate.proof_commit=sourceBaseline.proof_commit;
     candidate.final_bets_fixed_at=sourceBaseline.final_bets_fixed_at;
     const bytes=JSON.stringify(candidate);
     let purchase=buildFormalThreeCommandPlan(candidate,bytes,{now_iso:p.purchase.final_bets_fixed_at});
     if(p.purchase.purchase_strategy_version==='v3.16'&&purchase.purchase_decision==='buy'){
       purchase.status='formal_prestart';purchase.proof_commit=sourceBaseline.proof_commit;
       purchase.final_bets_fixed_at=new Date(Date.parse(p.purchase.final_bets_fixed_at)-1).toISOString();
       const upgraded=buildV316FormalPlan({source:candidate,sourceBytes:bytes,prior:purchase,priorBytes:JSON.stringify(purchase),now_iso:p.purchase.final_bets_fixed_at});
       if(upgraded.status!=='no_change')purchase=upgraded.plan;
     }
     candidate.final_bets=purchase.formal_bets;candidate.total_stake_yen=purchase.total_stake_yen;
     candidate.shadow_purchase= purchase;
   }else if(p.purchase){
     candidate.shadow_purchase={status:'pass',reason:'upstream_model_has_no_qualifying_purchase; overlay_not_applicable'};
   }
 }else{
   candidate=copy(baseline);
   candidate.step1_ranking=rows;
   candidate.outcome_distributions=fullFieldOutcomes(rows,input.scenario_factors);
 }
}
const probabilities=s=>{
 const top3=Object.fromEntries(s.step1_ranking.map(r=>[r.horse_number,0]));
 for(const o of s.outcome_distributions.central)for(const n of o.finish)top3[n]+=o.probability;
 return {win:Object.fromEntries(s.step1_ranking.map(r=>[r.horse_number,r.win_probability])),top3};
};
candidate.stage='shadow_only';candidate.proof_commit=null;
candidate.prompt_version=p.candidate_version;
candidate.shadow_metrics=candidate.final_bets.length?evaluateStrategy(candidate.final_bets,candidate.outcome_distributions,candidate.frame_map,candidate.race_context):null;
console.log(JSON.stringify({baseline,candidate,probabilities:{baseline:probabilities(baseline),candidate:probabilities(candidate)}}));
