// JRA v3.10 input-to-purchase pipeline. No network scraping, price invention, or STEP1 modification.
// Input is an audited, pre-price STEP1 and an independently observed exact market quote catalog.
// Generate all top-three outcomes; expand the pre-quote 8-type strategy plan; price each exact line;
// apply the already approved v3.10 optimiser. An unsealed snapshot is NEVER a formal prediction.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {TYPES,MODES,expandStrategy,ticketKey,oddsFloor,matches,evaluateStrategy} from './jra-strategy-engine-v39.mjs';
import {optimizePurchasePortfolio} from './jra-portfolio-optimizer-v310.mjs';
import {validateV310} from './validate-jra-portfolio-v310.mjs';

const scenes=['low','central','high'];
const isTime=s=>typeof s==='string'&&Number.isFinite(Date.parse(s));
const filled=s=>typeof s==='string'&&s.trim().length>0;
const must=(ok,message)=>{if(!ok)throw Error(message)};
const timestamp=s=>{must(isTime(s),'invalid timestamp '+s);return Date.parse(s)};
const cleanUrl=s=>typeof s==='string'&&/^https:\/\//.test(s);
const gradeOK=x=>['A+','A','B+','B','B-','C'].includes(x);
const near=(a,b)=>Math.abs(a-b)<=0.0000005;
const copy=x=>JSON.parse(JSON.stringify(x));
const idKey=s=>String(s);

export function fullFieldOutcomes(runners,scenarioFactors){
 must(runners.length>=4,'race must contain four or more runners');
 const ids=runners.map(r=>r.horse_number);
 const central=runners.map(r=>r.win_probability);
 const total=central.reduce((a,b)=>a+b,0);
 must(near(total,1),'STEP1 win probabilities must sum to 1; do not infer from market prices');
 const result={};
 for(const scenario of scenes){
  const factors=scenario==='central'?Object.fromEntries(ids.map(id=>[id,1])):scenarioFactors?.[scenario]?.by_horse;
  must(factors&&ids.every(id=>Number.isFinite(factors[id])&&factors[id]>0),'missing independent '+scenario+' scenario factors');
  const vals=central.map((p,i)=>p*factors[ids[i]]);
  const s=vals.reduce((a,b)=>a+b,0);
  const w=vals.map(n=>n/s);
  const outcomes=[];
  for(let i=0;i<ids.length;i++){
   for(let j=0;j<ids.length;j++){
    if(i===j)continue;
    for(let k=0;k<ids.length;k++){
     if(k===i||k===j)continue;
     // PL sequential without replacement. Central first-place marginals = STEP1 values.
     const p=w[i]*(w[j]/(1-w[i]))*(w[k]/(1-w[i]-w[j]));
     must(Number.isFinite(p)&&p>=0,'invalid conditional probability');
     outcomes.push({finish:[ids[i],ids[j],ids[k]],probability:p});
    }
   }
  }
  const mass=outcomes.reduce((a,x)=>a+x.probability,0);
  must(Math.abs(mass-1)<1e-7,'joint outcome mass error '+scenario);
  result[scenario]=outcomes;
 }
 return result;
}
function likelihood(line,dist,race,map){
 const p={};
 for(const sc of scenes){
  let n=0;
  for(const o of dist[sc])if(matches(line,o.finish,map,race))n+=o.probability;
  p[sc]=n;
 }
 return p;
}
function checkInput(input,freezeAt){
 must(input?.prompt_version==='v3.10','input version must be v3.10');
 must(/^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+$/.test(input.race_id),'safe dated race_id required');
 const race=input.race_context||{},fixed=input.step1||{},start=timestamp(race.start_at),freeze=timestamp(freezeAt);
 must(start>freeze,'BLOCKER: forecast and bet freeze must precede actual scheduled post');
 must(Date.parse(fixed.fixed_at)<=freeze&&isTime(fixed.fixed_at),'STEP1 fixed timestamp must precede freeze');
 must(fixed.no_odds_used_to_change_marks===true,'STEP1 independence from odds not attested');
 must(cleanUrl(race.official_source_url)&&cleanUrl(fixed.primary_source),'official race and STEP1 source URLs required');
 must(Number.isInteger(race.sale_field_size)&&race.sale_field_size>=9,'sale field must have >=9 runners (all 8 ticket types)');
 must(Array.isArray(race.offered_types)&&TYPES.every(t=>race.offered_types.includes(t))&&race.offered_types.length===8,
   'all 8 JRA ticket types must be officially confirmed (WIN5 excluded)');
 must(race.place_paid_positions===3,'incorrect place payment count');
 const runners=fixed.runners;
 must(Array.isArray(runners)&&runners.length===race.sale_field_size,'full-field STEP1 runners required');
 const seen=new Set();
 for(const h of runners){
  must(Number.isInteger(h.horse_number)&&h.horse_number>0&&!seen.has(h.horse_number),'duplicate/invalid STEP1 horse');
  seen.add(h.horse_number);
  must(Number.isFinite(h.win_probability)&&h.win_probability>0&&h.win_probability<1,'missing positive frozen win probability for '+h.horse_number);
  must(cleanUrl(h.source_url)&&filled(h.evidence),'missing per-runner non-market evidence '+h.horse_number);
  must(Array.isArray(h.factor_grades)&&h.factor_grades.length===9&&h.factor_grades.every(gradeOK),'missing all nine grades '+h.horse_number);
  must(filled(h.mark)&&filled(h.horse_name),'missing STEP1 mark/name');
 }
 must(near(runners.reduce((a,h)=>a+h.win_probability,0),1),'STEP1 probabilities unnormalized');
 must(runners.some(r=>r.mark==='◎')&&runners.some(r=>r.mark==='○')&&runners.some(r=>r.mark==='▲'),
   'final STEP1 ◎○▲ marks required');
 const frame=input.frame_map||{};
 for(const n of seen)must(Number.isInteger(frame[idKey(n)])&&frame[idKey(n)]>=1&&frame[idKey(n)]<=8,'missing official frame number for '+n);
 const factors=input.scenario_factors||{};
 for(const name of ['low','high']){
  must(filled(factors[name]?.assumption)&&Object.keys(factors[name]?.by_horse||{}).length===runners.length,
   'missing independently reasoned '+name+' sensitivity scenario');
 }
 must(Array.isArray(input.strategies)&&input.strategies.length>=8,'all eight type strategy planning required');
 const planIds=new Set(),mapped=new Set();
 for(const st of input.strategies){
  must(filled(st.strategy_id)&&!planIds.has(st.strategy_id),'strategy IDs must be unique');planIds.add(st.strategy_id);
  must(TYPES.includes(st.type)&&MODES[st.type].includes(st.strategy_kind),'invalid strategy mode');
  must(filled(st.ability_reason)&&filled(st.risk_reason)&&filled(st.decision_reason),'pre-price evidence and risk needed per strategy');
  must(isTime(input.strategy_plan_fixed_at)&&timestamp(input.strategy_plan_fixed_at)>=timestamp(fixed.fixed_at)&&timestamp(input.strategy_plan_fixed_at)<=freeze,
   'strategy plan must be frozen after STEP1 and before final freeze');
  mapped.add(st.type+':'+st.strategy_kind);
 }
 must(TYPES.every(type=>input.strategies.some(st=>st.type===type)),'must consider every ticket type before checking prices');
 const reviews=input.mode_exclusions||[];
 must(Array.isArray(reviews),'mode_exclusions must be array');
 const checked=new Set();
 for(const rev of reviews){
  must(TYPES.includes(rev.type)&&MODES[rev.type].includes(rev.mode),'unsupported exclusion mode');
  must(!mapped.has(rev.type+':'+rev.mode),'mode both planned and excluded');
  must(!checked.has(rev.type+':'+rev.mode),'duplicate mode exclusions');
  checked.add(rev.type+':'+rev.mode);
  must(filled(rev.reason)&&filled(rev.evidence),'mode exclusions require specific reason and pre-market evidence');
 }
 for(const type of TYPES)for(const mode of MODES[type])must(mapped.has(type+':'+mode)||checked.has(type+':'+mode),
   'missing mode audit '+type+'/'+mode);
 must(Array.isArray(input.market_quotes),'exact market quote catalog required');
 for(const q of input.market_quotes)must(timestamp(q.observed_at)>timestamp(input.strategy_plan_fixed_at),
  'BLOCKER: strategy selection plan must precede every market observation');
 return {race,runners,frame,freeze,start};
}
export function assemble(input,freezeAt,proofCommit=null){
 const {race,runners,frame,freeze}=checkInput(input,freezeAt);
 const dist=fullFieldOutcomes(runners,input.scenario_factors);
 const captured=new Map();
 const quoteIssues=[];
 for(const [i,q] of input.market_quotes.entries()){
  must(q.race_id===input.race_id,'wrong race odds at quote '+i);
  const key=ticketKey(q.type,q.selection),time=timestamp(q.observed_at);
  must(time<=freeze&&time<timestamp(race.start_at),'quote after freeze/post '+key);
  must(cleanUrl(q.source_url),'market URL missing '+key);
  must(q.market_selection_id===key,'market key does not match selection '+key);
  must(q.source_capture_sha256&&/^[a-f0-9]{64}$/i.test(q.source_capture_sha256),'quote capture content SHA256 required '+key);
  must(typeof q.source_capture_path==='string'&&q.source_capture_path.startsWith('e2e_validation/quote-evidence/')&&
   !q.source_capture_path.includes('..')&&fs.existsSync(q.source_capture_path),
   'tracked quote source capture missing '+key);
  const digest=createHash('sha256').update(fs.readFileSync(q.source_capture_path)).digest('hex');
  must(digest.toLowerCase()===q.source_capture_sha256.toLowerCase(),'actual quote capture SHA256 mismatch '+key);
  const snapshot=JSON.parse(fs.readFileSync(q.source_capture_path,'utf8'));
  must(snapshot.source_url===q.source_url&&snapshot.observed_at===q.observed_at,
   'capture URL/time disagrees with quote '+key);
  const observed=(snapshot.entries||[]).filter(t=>ticketKey(t.type,t.selection)===key);
  must(observed.length===1&&JSON.stringify(observed[0].market_odds)===JSON.stringify(q.market_odds),
   'capture lacks exact selection/price or has duplicate lines '+key);
  must(q.quote_verified===true&&oddsFloor(q.market_odds)!==null,'quote unverifiable '+key);
  if(captured.has(key)){
   const prior=captured.get(key);
   must(JSON.stringify(prior)===JSON.stringify(q),'conflicting price for same exact ticket '+key);
   continue;
  }
  captured.set(key,q);
 }
 const strategies=[],status=new Map(),comp=new Map();
 const quoteUsed=new Set();
 for(const st of input.strategies){
  const expanded=expandStrategy(st.type,st.strategy_kind,st.definition);
  const lines=expanded.map(t=>{
   const key=ticketKey(t.type,t.selection),q=captured.get(key);
   if(q)quoteUsed.add(key);
   return {...t,stake_yen:100,market_odds:q?.market_odds??null,source_url:q?.source_url??null,
    observed_at:q?.observed_at??null,market_selection_id:key,quote_verified:!!q};
  });
  const allPriced=lines.every(l=>l.quote_verified);
  const metrics=allPriced?evaluateStrategy(lines,dist,frame,race):
   {total_stake_yen:lines.length*100,hit_probability_scenarios:null,expected_payout_yen_scenarios:null,
    roi_scenarios:null,full_loss_probability_scenarios:null,loss_probability_scenarios:null};
  strategies.push({...copy(st),generated_ticket_count:lines.length,lines,
   eligibility:allPriced?'eligible':'unpriced',...metrics});
  status.set(st.type+':'+st.strategy_kind,allPriced?'evaluated':'unpriced');
  for(const line of lines){
   const k=ticketKey(line.type,line.selection);
   if(!comp.has(k))comp.set(k,{line,ability_reason:st.ability_reason,risk_reason:st.risk_reason});
  }
 }
 for(const k of captured.keys())if(!quoteUsed.has(k))quoteIssues.push('unused exact quote: '+k);
 const comparisons=[...comp.values()].map(({line,ability_reason,risk_reason})=>{
  const verified=line.quote_verified,p=likelihood(line,dist,race,frame),odds=oddsFloor(line.market_odds);
  return {type:line.type,selection:line.selection,market_odds:verified?line.market_odds:null,
   source_url:verified?line.source_url:null,observed_at:verified?line.observed_at:null,
   assessed_at:freezeAt,probability_method:'uncalibrated STEP1-anchored sequential Plackett-Luce',
   probability_scenarios:p,break_even_probability:verified?1/odds:null,
   ev_scenarios:verified?Object.fromEntries(scenes.map(s=>[s,p[s]*odds])):null,
   ability_reason,risk_reason,eligibility:verified?'eligible':'unpriced',
   decision_reason:verified?'Price captured, model sensitivity audited':'Exact price not verified; excluded'};
 }).sort((a,b)=>TYPES.indexOf(a.type)-TYPES.indexOf(b.type));
 const perType=TYPES.map(type=>comparisons.filter(c=>c.type===type));
 const typeRows=perType.map((xs,i)=>{
  const type=TYPES[i],priced=xs.filter(c=>c.eligibility==='eligible');
  const winner=priced.sort((a,b)=>b.ev_scenarios.central-a.ev_scenarios.central)[0];
  return winner?{type,status:'evaluated',candidate:{selection:winner.selection,kind:'horse_numbers',label:winner.selection.join('-')},
   market_odds:winner.market_odds,source_url:winner.source_url,observed_at:winner.observed_at,assessed_at:freezeAt,
   probability:winner.probability_scenarios.central,probability_method:winner.probability_method,
   ev_multiple:winner.ev_scenarios.central,decision:'pass',reason:'Portfolio selection follows exact cross-type optimiser'}
    :{type,status:'unpriced',candidate:null,market_odds:null,source_url:null,observed_at:null,assessed_at:freezeAt,
      probability:null,probability_method:null,ev_multiple:null,decision:'pass',reason:'No verified exact quote'};
 });
 const typeSearch=perType.map((xs,i)=>({type:TYPES[i],generated_count:xs.length,
  priced_count:xs.filter(x=>x.eligibility==='eligible').length,
  shortfall_reason:xs.length<(['三連複','三連単'].includes(TYPES[i])?3:2)?'Pre-price plan has fewer independent choices; inspect source plan':'',
  price_shortfall_reason:xs.filter(x=>x.eligibility==='eligible').length<(['三連複','三連単'].includes(TYPES[i])?3:2)?
   'Not enough independently verified exact-market selections':''}));
 const rowsCount=typeRows.filter(r=>r.status==='evaluated').length;
 const localCoverage=rowsCount===8?'complete':rowsCount>0?'partial':'none';
 const gate=typeRows.filter(r=>r.status==='evaluated').map(r=>{
  const compRow=comparisons.find(x=>x.type===r.type&&JSON.stringify(x.selection)===JSON.stringify(r.candidate.selection));
  return {type:r.type,selection:r.candidate.selection,quote_verified:true,source_url:r.source_url,observed_at:r.observed_at,
   probability_assessed:true,probability_method:r.probability_method,uncertainty_assessed:true,
   ability_reason:compRow.ability_reason,edge_reason:'Measured quote multiplied by independent STEP1 joint win probability',
   risk_reason:compRow.risk_reason,eligibility:'eligible',reason:'Quote and probability supported'};
 });
 const coverage=TYPES.map(type=>({type,modes:Object.fromEntries(MODES[type].map(mode=>{
  const k=type+':'+mode,s=status.get(k);
  if(s)return [mode,{status:s,reason:s==='unpriced'?'Some individual exact quotes missing':''}];
  const rev=(input.mode_exclusions||[]).find(x=>x.type===type&&x.mode===mode);
  return [mode,{status:'insufficient_evidence',reason:rev.reason+' / '+rev.evidence}];
 }))}));
 const audit={status:'complete',calibrated:input.step1.calibrated===true,
  model:'frozen STEP1 probabilities + sequential without-replacement Plackett-Luce',
  primary_source:input.step1.primary_source,source_observed_at:input.step1.fixed_at,
  runners:runners.map(({horse_number,win_probability,evidence,source_url})=>({horse_number,win_probability,evidence,source_url})),
  scenarios:scenes.map(s=>({name:s,assumption:s==='central'?'Frozen STEP1 central probabilities':
   input.scenario_factors[s].assumption,candidate_hit_probability:dist[s].filter(o=>o.finish[0]===runners[0].horse_number).reduce((p,o)=>p+o.probability,0)}))
 };
 // Do not classify a completely unobserved market as no-value; it is a blocker.
 must(rowsCount>0,'BLOCKER: no independently verified exact odds for any ticket type');
 const portfolio=optimizePurchasePortfolio({budget_yen:6000,strategies,
  outcome_distributions:dist,frame_map:frame,race_context:race,freeze_at:freezeAt});
 const pid='P-'+input.race_id+'-v310';
 const selected=portfolio.selected_lines.map((line,i)=>({...line,id:'B'+String(i+1).padStart(2,'0')}));
 const finalBets=selected.map(x=>({id:x.id,type:x.type,selection:x.selection,stake_yen:x.stake_yen,
  market_odds:x.market_odds,source_url:x.source_url,observed_at:x.observed_at,market_selection_id:x.market_selection_id}));
 const payload={
  schema_version:3,race_id:input.race_id,prompt_version:'v3.10',stage:proofCommit?'formal_prestart':'pending_git_proof',
  race_context:copy(race),frame_map:copy(frame),step1_fixed_at:input.step1.fixed_at,
  step1_ranking:copy(runners),no_odds_used_to_change_marks:true,
  model_assumptions:['no_dead_heat','uncalibrated_or_unverified_model_accuracy'],
  probability_model_audit:audit,outcome_distributions:dist,
  strategy_coverage_audit:coverage,purchase_strategy_evaluations:strategies,
  bet_type_evaluations:typeRows,market_coverage_status:rowsCount===8?'complete':'incomplete',
  market_coverage_snapshot_at:freezeAt,purchase_gate:{scope:'race_local_8types',local_coverage_status:localCoverage,candidates:gate},
  ticket_candidate_comparisons:comparisons,ticket_candidate_search_audit:typeSearch,
  purchase_budget_yen:6000,purchase_decision:portfolio.purchase_decision,
  purchase_reason_code:portfolio.purchase_reason_code,purchase_portfolio_selection:{...portfolio,portfolio_id:pid,
   expected_net_profit_yen_scenarios:portfolio.expected_payout_yen_scenarios?
    Object.fromEntries(scenes.map(s=>[s,portfolio.expected_payout_yen_scenarios[s]-portfolio.total_stake_yen])):null},
  final_bets:finalBets,total_stake_yen:portfolio.total_stake_yen,
  selected_strategy_id:finalBets.length?pid:null,best_strategy_id:finalBets.length?pid:null,
  best_bet_id:finalBets.length?'B01':null,final_bets_fixed_at:freezeAt,proof_commit:proofCommit,
  input_source:input.input_source,market_quote_audit:{submitted:input.market_quotes.length,verified:captured.size,
   unused:quoteIssues,missing_individual_lines:comparisons.filter(c=>c.eligibility==='unpriced').length},
  publication_status:'awaiting_independently_authored_full_html_and_validated_pdf',
  notes:['Probabilities are a sensitivity model, not historically calibrated win frequencies',
   'This calculation does not fetch market quotes or author the required full horse-by-horse PDF',
   'Final betting lines are predictions, not a record of real money placed']
 };
 if(proofCommit){
  must(/^[a-f0-9]{40}$/.test(proofCommit),'proof_commit must be real Git SHA');
  const errors=validateV310(payload);
  must(errors.length===0,'v3.10 official validator rejects prediction: '+errors.join('; '));
 }
 return payload;
}
function argValue(args,name){const i=args.indexOf(name);return i>=0?args[i+1]:null}
function main(){
 const args=process.argv.slice(2),output=argValue(args,'--output'),inputPath=argValue(args,'--input');
 const seal=argValue(args,'--seal'),proof=argValue(args,'--proof-commit');
 must(output,'--output path required');
 if(seal){
  must(proof&&/^[0-9a-f]{40}$/.test(proof),'--proof-commit Git SHA required');
  const proofObj=JSON.parse(execFileSync('git',['show',proof+':'+seal],{encoding:'utf8',maxBuffer:64*1024*1024}));
  must(proofObj.stage==='pending_git_proof'&&proofObj.proof_commit===null,'snapshot not pending or already sealed');
  const commitTime=execFileSync('git',['show','-s','--format=%cI',proof],{encoding:'utf8'}).trim();
  must(timestamp(commitTime)<timestamp(proofObj.race_context.start_at),'BLOCKER: proof commit after race post');
  must(Date.now()<timestamp(proofObj.race_context.start_at),'BLOCKER: cannot seal after race post');
  const result={...proofObj,stage:'formal_prestart',proof_commit:proof};
  const errors=validateV310(result);
  must(errors.length===0,'v3.10 validator rejects sealed prediction: '+errors.join('; '));
  must(!fs.existsSync(output),'immutable prediction path already exists');
  fs.mkdirSync((awaitImportPath(output)),{recursive:true});
  fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n');
  console.log('SEALED '+result.race_id+' lines='+result.final_bets.length+' yen='+result.total_stake_yen+' proof='+proof);
 }else{
  must(inputPath,'--input required');
  const src=JSON.parse(fs.readFileSync(inputPath,'utf8'));
  must(!fs.existsSync(output),'immutable snapshot already exists');
  const result=assemble(src,new Date().toISOString());
  fs.mkdirSync((awaitImportPath(output)),{recursive:true});
  fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n');
  console.log('PENDING PROOF '+result.race_id+' lines='+result.final_bets.length+' yen='+result.total_stake_yen);
 }
}
function awaitImportPath(file){return file.split('/').slice(0,-1).join('/')||'.'}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 try{main()}catch(e){console.error('PRESTART BLOCKER:',e.message);process.exitCode=1}
}
