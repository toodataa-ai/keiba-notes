import fs from 'node:fs';
import path from 'node:path';

const TYPES=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'];
const ALL=TYPES;
const REASONS=['bought','no_value','risk_high','insufficient_local_information'];
const PASS_REASONS=['no_value','risk_high','insufficient_local_information'];

export function isV34OrLater(v) {
  const match=/^v(\d+)\.(\d+)$/.exec(String(v||''));
  return !!match && (Number(match[1])>3 || (Number(match[1])===3 && Number(match[2])>=4));
}
const positiveOdds = x => (typeof x==='number' && Number.isFinite(x) && x>1) ||
  (Array.isArray(x) && x.length===2 && x.every(v=>typeof v==='number' && Number.isFinite(v) && v>1));
const sameSelection=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const nonempty=x=>typeof x==='string' && x.trim().length>0;
const dateValid=x=>nonempty(x)&&Number.isFinite(Date.parse(x));

export function validateV34(data) {
  const errors=[];
  const add=message=>errors.push(message);
  if(!isV34OrLater(data.prompt_version)) return errors;
  const rows=data.bet_type_evaluations;
  if(!Array.isArray(rows)||rows.length!==8) { add('exactly eight bet_type_evaluations required; WIN5 excluded'); return errors; }
  if(ALL.some((type,i)=>rows[i]?.type!==type)) add('eight local ticket types missing/out of policy order');
  const map=new Map(rows.map(r=>[r.type,r]));
  if(!['complete','incomplete'].includes(data.market_coverage_status)) add('invalid market_coverage_status');
  if(!dateValid(data.market_coverage_snapshot_at)) add('market_coverage_snapshot_at required');
  const gate=data.purchase_gate;
  if(!gate||gate.scope!=='race_local_8types') {add('purchase_gate.scope must be race_local_8types');return errors;}
  if(!['complete','partial','none'].includes(gate.local_coverage_status)) add('invalid local_coverage_status');
  if('win5_status' in gate || 'WIN5' in map) add('WIN5 is out of scope for v3.4');
  if(!Array.isArray(gate.candidates)) {add('purchase_gate.candidates array required');return errors;}
  const localEvaluated=TYPES.filter(t=>map.get(t)?.status==='evaluated');
  const complete=localEvaluated.length===8;
  if(data.market_coverage_status==='complete' && !complete) add('market marked complete without 8 priced/assessed local types');
  if(gate.local_coverage_status==='complete' && !complete) add('local coverage marked complete without eight evaluated rows');
  if(gate.local_coverage_status==='none' && localEvaluated.length) add('local coverage none despite evaluated type');
  if(gate.local_coverage_status==='partial' && (complete||localEvaluated.length===0)) add('local coverage partial inconsistent with priced types');
  const audit=data.probability_model_audit;
  if(!audit||typeof audit!=='object') add('probability_model_audit required');
  else if(audit.status==='complete'){
    if(!nonempty(audit.model)||!nonempty(audit.primary_source)||!dateValid(audit.source_observed_at)) add('probability model lacks source/method/timestamp');
    if(!Array.isArray(audit.runners)||audit.runners.length<3) add('full-field probability runners missing');
    else{
      if(data.runners&&audit.runners.length!==data.runners.length) add('probability field size does not equal runner count');
      const ids=new Set(audit.runners.map(r=>r.horse_number));
      const probSum=audit.runners.reduce((a,r)=>a+(Number.isFinite(r.win_probability)?r.win_probability:0),0);
      if(ids.size!==audit.runners.length||Math.abs(probSum-1)>1e-5) add('full-field probabilities not normalized or duplicate horses');
      for(const r of audit.runners){
        if(!(Number.isInteger(r.horse_number)&&r.horse_number>0&&Number.isFinite(r.win_probability)&&r.win_probability>0&&r.win_probability<1))
          add('invalid per-runner probability');
        if(!nonempty(r.evidence)||!nonempty(r.source_url)) add('per-runner evidence/source required');
      }
    }
    if(!Array.isArray(audit.scenarios)||audit.scenarios.length<3) add('at least three sensitivity scenarios needed');
    else for(const z of audit.scenarios) {
      if(!nonempty(z.name)||!nonempty(z.assumption)||!Number.isFinite(z.candidate_hit_probability)||z.candidate_hit_probability<0||z.candidate_hit_probability>1) add('scenario missing assumption/probability');
    }
    if(audit.calibrated!==false&&audit.calibrated!==true) add('calibrated flag must be explicit');
  } else if(audit?.status!=='incomplete') add('probability_model_audit.status must be complete/incomplete');
  const eligible=[];
  for(const [i,c] of gate.candidates.entries()){
    const loc='candidate['+i+']';
    if(!TYPES.includes(c.type)) {add(loc+' cannot be WIN5 or unknown type');continue;}
    const row=map.get(c.type);
    if(!row || row.status!=='evaluated') {add(loc+' lacks evaluated market row');continue;}
    if(!sameSelection(c.selection,row.candidate?.selection)) add(loc+' selection mismatch with priced market row');
    if(!dateValid(c.observed_at)||!nonempty(c.source_url)||!nonempty(c.ability_reason)||!nonempty(c.risk_reason)||!nonempty(c.edge_reason)) add(loc+' lacks source/time/ability/risk/edge evidence');
    if(!['eligible','ineligible'].includes(c.eligibility)||!nonempty(c.reason)) add(loc+' missing eligibility/reason');
    if(c.eligibility==='eligible'){
      if(c.quote_verified!==true||c.probability_assessed!==true||c.uncertainty_assessed!==true) add(loc+' eligible without independently checked quote, probability and uncertainty');
      if(!positiveOdds(row.market_odds)||!dateValid(row.observed_at)||!nonempty(row.source_url)||!nonempty(row.probability_method)||
        typeof row.probability!=='number'||row.probability<0||row.probability>1) add(loc+' eligible without actual market/probability evidence');
      if(c.source_url!==row.source_url || c.observed_at!==row.observed_at) add(loc+' market source/timestamp differ from evaluated row');
      eligible.push(c);
    }
  }
  if(!REASONS.includes(data.purchase_reason_code)) add('invalid purchase_reason_code');
  if(!['buy','pass'].includes(data.purchase_decision)) add('invalid purchase_decision');
  const bets=Array.isArray(data.final_bets)?data.final_bets:[];
  if(!Array.isArray(data.final_bets)) add('final_bets must be array');
  const total=bets.reduce((n,b)=>n+(Number.isFinite(b.stake_yen)?b.stake_yen:0),0);
  if(data.total_stake_yen!==total) add('total stake mismatch');
  if(data.purchase_decision==='buy'){
    if(data.purchase_reason_code!=='bought') add('buy requires bought reason');
    if(eligible.length===0) add('buy has no eligible local candidates');
    if(audit?.status!=='complete') add('buy requires full-field audited probability model, not point estimate alone');
    if(!bets.length) add('buy requires frozen final_bets');
    if(!nonempty(data.best_bet_id)||!bets.some(b=>b.id===data.best_bet_id)) add('buy must have one best bet id in final_bets');
    if(!dateValid(data.final_bets_fixed_at)) add('buy requires prereace fixed time');
    const seen=new Set();
    for(const bet of bets) {
      if(seen.has(bet.id)) add('duplicate final_bet id');seen.add(bet.id);
      if(!Number.isInteger(bet.stake_yen)||bet.stake_yen<100||bet.stake_yen%100!==0) add('invalid final_bet stake');
      if(!eligible.some(c=>c.type===bet.type&&sameSelection(c.selection,bet.selection))) add('final_bet not in eligible verified candidates');
    }
    const start=data.race_context?.start_at;
    if(start&&dateValid(start)&&new Date(data.final_bets_fixed_at)>=new Date(start)) add('final_bets fixed at or after post');
    if(dateValid(data.final_bets_fixed_at)){
      for(const c of eligible) if(dateValid(c.observed_at)&&new Date(c.observed_at)>new Date(data.final_bets_fixed_at)) add('market quote observed after final_bets fixed');
    }
  } else if(data.purchase_decision==='pass'){
    if(!PASS_REASONS.includes(data.purchase_reason_code)) add('pass must have explicit reason code');
    if(data.best_bet_id!==null||bets.length||data.total_stake_yen!==0) add('pass must have zero stake, empty bets, null best_bet_id');
    if(data.purchase_reason_code==='insufficient_local_information' && eligible.length>0) add('insufficient_local_information invalid when any local candidate is eligible (WIN5/coverage may be incomplete)');
    if(['no_value','risk_high'].includes(data.purchase_reason_code) && eligible.length===0) add('no_value/risk_high requires at least one eligible local candidate');
    if(['no_value','risk_high'].includes(data.purchase_reason_code) && audit?.status!=='complete') add('value/risk judgement requires audited probability scenarios');
  }
  // User excludes WIN5. A local bet is evaluated without any unrelated cross-race gate.
  return errors;
}

if(process.argv[1] && path.resolve(process.argv[1])===path.resolve(new URL(import.meta.url).pathname)){
  const root=process.cwd();
  const base=path.join(root,'e2e_validation','predictions');
  const errors=[];
  let count=0;
  if(fs.existsSync(base)){
    for(const ent of fs.readdirSync(base,{withFileTypes:true})){
      if(!ent.isDirectory())continue;
      for(const f of fs.readdirSync(path.join(base,ent.name)).filter(n=>n.endsWith('.json'))){
        const filepath=path.join(base,ent.name,f);
        const obj=JSON.parse(fs.readFileSync(filepath,'utf8'));
        if(!isV34OrLater(obj.prompt_version))continue;
        count++;
        for(const e of validateV34(obj))errors.push(path.relative(root,filepath)+': '+e);
      }
    }
  }
  if(errors.length){console.error('v3.4 purchase-gate validation FAILED\n'+errors.join('\n'));process.exit(1);}
  console.log('v3.4 purchase-gate validation OK; '+count+' v3.4+ predictions, eight local types only, WIN5 omitted');
}
