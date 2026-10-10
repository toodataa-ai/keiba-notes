import fs from 'node:fs';
import path from 'node:path';
import {validateMultiCandidate35} from './validate-multi-candidate-v35.mjs';

const TYPES=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'];
const KINDS=['single','trifecta_formation','trifecta_two_key_multi','trifecta_box'];
const requiredScenarios=['low','central','high'];
const key=(type,sel)=>type+':'+JSON.stringify(sel);
const nonempty=x=>typeof x==='string'&&x.trim().length>0;
const dateOk=x=>nonempty(x)&&Number.isFinite(Date.parse(x));
const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const n=x=>typeof x==='number'&&Number.isFinite(x);
const near=(a,b)=>n(a)&&Math.abs(a-b)<=Math.max(0.000001,Math.abs(b)*0.000001);
export const isV38=v=>{const m=/^v(\\d+)\\.(\\d+)$/.exec(String(v||''));return !!m&&(Number(m[1])>3||Number(m[1])===3&&Number(m[2])>=8);};

function orderedTriples(def,kind){
 const out=[],add=a=>{if(a.length===3&&a.every(x=>Number.isInteger(x)&&x>0)&&new Set(a).size===3)out.push(a);};
 if(kind==='trifecta_formation') for(const a of def.first||[])for(const b of def.second||[])for(const c of def.third||[])add([a,b,c]);
 if(kind==='trifecta_two_key_multi'){
   const axis=def.axis||[];
   if(axis.length!==2||axis[0]===axis[1])return null;
   for(const c of def.partners||[]){
     const [a,b]=axis;
     for(const t of [[a,b,c],[a,c,b],[b,a,c],[b,c,a],[c,a,b],[c,b,a]])add(t);
   }
 }
 if(kind==='trifecta_box'){
   const horses=def.horses||[];
   for(const a of horses)for(const b of horses)for(const c of horses)add([a,b,c]);
 }
 const seen=new Set(),uniq=[];
 for(const t of out){const k=JSON.stringify(t);if(!seen.has(k)){seen.add(k);uniq.push(t);}}
 return uniq;
}

export function validateV38(data){
 const errors=[],err=s=>errors.push(s);
 if(!isV38(data.prompt_version))return errors;
 // Reuse all pre-v3.8 probability/8-type/market checks without changing their old contracts.
 // Project ONLY the legacy one-point purchase segment into a neutral pass; v3.8 audits real purchases below.
 const projected={...data,prompt_version:'v3.7',purchase_decision:'pass',best_bet_id:null,
   purchase_reason_code:(data.purchase_gate?.candidates||[]).some(x=>x.eligibility==='eligible')?'risk_high':'insufficient_local_information',
   final_bets:[],total_stake_yen:0};
 errors.push(...validateMultiCandidate35(projected).map(x=>'legacy invariant: '+x));
 if(!Array.isArray(data.purchase_strategy_evaluations)||!data.purchase_strategy_evaluations.length) {
   err('purchase_strategy_evaluations required');return errors;
 }
 if(!['buy','pass'].includes(data.purchase_decision))err('purchase_decision must be buy/pass');
 if(!['bought','no_value','risk_high','insufficient_local_information'].includes(data.purchase_reason_code))err('invalid purchase_reason_code');
 const strategies=data.purchase_strategy_evaluations;
 const strategyIds=new Set();
 const searchMap=new Map((data.ticket_candidate_comparisons||[]).map(x=>[key(x.type,x.selection),x]));
 const valued=new Map();
 for(const [i,st] of strategies.entries()){
   const loc='strategy['+i+']';
   if(!nonempty(st.strategy_id)||strategyIds.has(st.strategy_id))err(loc+' duplicate/missing strategy_id');
   strategyIds.add(st.strategy_id);
   if(!KINDS.includes(st.strategy_kind)||!TYPES.includes(st.type))err(loc+' invalid strategy kind/type');
   if(st.strategy_kind!=='single'&&st.type!=='三連単')err(loc+' expanded strategy must be trifecta');
   if(!st.definition||typeof st.definition!=='object')err(loc+' missing definition');
   if(!Array.isArray(st.lines)||!st.lines.length){err(loc+' lines missing');continue;}
   let expected;
   if(st.strategy_kind==='single')expected=[st.definition?.selection];
   else expected=orderedTriples(st.definition||{},st.strategy_kind);
   if(!expected||expected.some(x=>!Array.isArray(x)||x.some(y=>!Number.isInteger(y)||y<1)))err(loc+' malformed definition');
   else {
     const a=new Set(expected.map(x=>key(st.type,x))),b=new Set(st.lines.map(x=>key(x.type,x.selection)));
     if(st.generated_ticket_count!==a.size||a.size!==st.lines.length||a.size!==b.size||[...a].some(x=>!b.has(x)))err(loc+' expanded combinations/count mismatch or duplicates');
   }
   const amount=st.lines.reduce((x,l)=>x+(n(l.stake_yen)?l.stake_yen:0),0);
   if(st.total_stake_yen!==amount)err(loc+' strategy total stake mismatch');
   let priceAll=true;
   for(const [j,l] of st.lines.entries()){
     const lLoc=loc+'.line['+j+']';
     if(l.type!==st.type)err(lLoc+' type mismatches strategy');
     if(!Number.isInteger(l.stake_yen)||l.stake_yen<100||l.stake_yen%100!==0)err(lLoc+' stake must be 100-yen unit');
     if(!Array.isArray(l.selection)||l.selection.length!==(st.type==='三連単'?3:(['単勝','複勝'].includes(st.type)?1:2)))err(lLoc+' selection arity mismatch');
     const c=searchMap.get(key(l.type,l.selection));
     if(!c)err(lLoc+' missing detailed individual candidate');
     if(!n(l.market_odds)||l.market_odds<=1||!nonempty(l.source_url)||!dateOk(l.observed_at)){priceAll=false;continue;}
     if(!c||c.eligibility!=='eligible'||!eq(c.market_odds,l.market_odds)||c.source_url!==l.source_url||c.observed_at!==l.observed_at)err(lLoc+' priced line not exact verified candidate');
     if(dateOk(data.race_context?.start_at)&&new Date(l.observed_at)>=new Date(data.race_context.start_at))err(lLoc+' market quote after post');
     if(!l.probability_scenarios||requiredScenarios.some(sc=>!n(l.probability_scenarios[sc])||l.probability_scenarios[sc]<0||l.probability_scenarios[sc]>1))err(lLoc+' missing 3 coherent probability scenarios');
   }
   if(!['eligible','ineligible','unpriced','probability_unavailable'].includes(st.eligibility))err(loc+' invalid eligibility');
   if(!nonempty(st.decision_reason))err(loc+' missing selection/rejection reason');
   if(!priceAll){
     if(st.eligibility==='eligible')err(loc+' unpriced lines cannot form eligible strategy');
     if(st.roi_scenarios!==null||st.expected_payout_yen_scenarios!==null)err(loc+' unpriced strategy must have null ROI/payout');
     continue;
   }
   const priceInBounds=n(st.total_stake_yen)&&st.total_stake_yen>0;
   if(!priceInBounds){err(loc+' zero/invalid strategy stake');continue;}
   if(st.eligibility==='unpriced')err(loc+' priced strategy mislabeled unpriced');
   for(const sc of requiredScenarios){
     let p=0,payout=0;
     for(const l of st.lines){
       if(!l.probability_scenarios||!n(l.probability_scenarios[sc]))continue;
       p+=l.probability_scenarios[sc];payout+=l.probability_scenarios[sc]*l.stake_yen*l.market_odds;
     }
     if(p>1.0000001)err(loc+' sum of disjoint trifecta probabilities exceeds 1 ('+sc+')');
     if(!near(st.hit_probability_scenarios?.[sc],p))err(loc+' hit probability sum incorrect ('+sc+')');
     if(!near(st.expected_payout_yen_scenarios?.[sc],payout))err(loc+' expected payout not sum of priced tickets ('+sc+')');
     if(!near(st.roi_scenarios?.[sc],payout/amount))err(loc+' ROI is not payout / whole strategy stake ('+sc+')');
     if(!near(st.full_loss_probability_scenarios?.[sc],1-p))err(loc+' full loss probability incorrect ('+sc+')');
   }
   valued.set(st.strategy_id,st);
 }
 const bets=Array.isArray(data.final_bets)?data.final_bets:[];
 if(!Array.isArray(data.final_bets))err('final_bets must be an array');
 if(data.total_stake_yen!==bets.reduce((s,x)=>s+(n(x.stake_yen)?x.stake_yen:0),0))err('final_bets total stake mismatch');
 if(data.purchase_decision==='pass'){
   if(!['no_value','risk_high','insufficient_local_information'].includes(data.purchase_reason_code))err('pass needs explicit reason');
   if(data.selected_strategy_id!==null||data.best_strategy_id!==null||data.best_bet_id!==null||bets.length||data.total_stake_yen!==0)err('pass must select no strategy, no bets and zero stake');
 }else if(data.purchase_decision==='buy'){
   if(data.purchase_reason_code!=='bought')err('buy requires bought reason');
   if(!nonempty(data.selected_strategy_id)||data.selected_strategy_id!==data.best_strategy_id)err('buy requires exactly one selected/best strategy');
   const st=valued.get(data.selected_strategy_id);
   if(!st||st.eligibility!=='eligible')err('selected strategy is not fully priced and eligible');
   if(!data.probability_model_audit||data.probability_model_audit.status!=='complete')err('buy requires full field audited probability model');
   if(!dateOk(data.final_bets_fixed_at)||dateOk(data.race_context?.start_at)&&new Date(data.final_bets_fixed_at)>=new Date(data.race_context.start_at))err('final bets must be frozen before post');
   if(!nonempty(data.best_bet_id)||!bets.some(b=>b.id===data.best_bet_id))err('best_bet_id must reference one purchased line for legacy compatibility');
   const budget=data.purchase_budget_yen===undefined?3000:data.purchase_budget_yen;
   if(!Number.isInteger(budget)||budget<100||budget%100!==0||budget>3000&&data.budget_source!=='user')err('budget must be sensible; >3000 requires user budget_source');
   if(data.total_stake_yen>budget)err('strategy purchase exceeds budget cap');
   if(st){
     if(st.lines.length!==bets.length)err('all selected strategy lines must appear in final_bets');
     const lines=new Map(st.lines.map(x=>[key(x.type,x.selection),x])),seen=new Set(),ids=new Set();
     for(const b of bets){
       const k=key(b.type,b.selection),l=lines.get(k);
       if(seen.has(k)||ids.has(b.id))err('duplicate final_bet line/id');seen.add(k);ids.add(b.id);
       if(!nonempty(b.id)||!l||l.stake_yen!==b.stake_yen||!eq(l.market_odds,b.market_odds)||l.source_url!==b.source_url||l.observed_at!==b.observed_at)err('final_bet does not exactly match selected strategy priced line');
     }
     if(dateOk(data.final_bets_fixed_at))for(const l of st.lines)if(dateOk(l.observed_at)&&new Date(l.observed_at)>new Date(data.final_bets_fixed_at))err('strategy quote observed after final_bets freeze');
     if(st.total_stake_yen!==data.total_stake_yen)err('selected strategy and final bets stake disagree');
   }
 }
 return errors;
}

if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(new URL(import.meta.url).pathname)){
 const base='e2e_validation/predictions',errors=[];let count=0;
 if(fs.existsSync(base))for(const dir of fs.readdirSync(base,{withFileTypes:true})){
   if(!dir.isDirectory())continue;
   for(const file of fs.readdirSync(path.join(base,dir.name)).filter(x=>x.endsWith('.json'))){
     const filePath=path.join(base,dir.name,file),data=JSON.parse(fs.readFileSync(filePath,'utf8'));
     if(!isV38(data.prompt_version))continue;count++;
     for(const error of validateV38(data))errors.push(filePath+': '+error);
   }
 }
 if(errors.length){console.error('v3.8 strategy verification failed:\\n'+errors.join('\\n'));process.exit(1);}
 console.log('v3.8 strategy validation OK; '+count+' versioned predictions audited');
}
