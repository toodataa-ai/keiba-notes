import fs from 'node:fs';
import path from 'node:path';
import {validateV34} from './validate-purchase-gate-v34.mjs';

const TYPES=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'];
const key=(type,selection)=>type+':'+JSON.stringify(selection);
const isV35=v=>{const m=/^v(\d+)\.(\d+)$/.exec(String(v||''));return !!m&&(Number(m[1])>3||Number(m[1])===3&&Number(m[2])>=5)};
const priced=odds=>typeof odds==='number'&&Number.isFinite(odds)&&odds>1 ||
  Array.isArray(odds)&&odds.length===2&&odds.every(n=>typeof n==='number'&&Number.isFinite(n)&&n>1);
const nonempty=x=>typeof x==='string'&&x.trim().length>0;
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const tstamp=s=>nonempty(s)&&Number.isFinite(Date.parse(s));
const depth={単勝:2,複勝:2,枠連:2,馬連:2,馬単:2,ワイド:2,三連複:3,三連単:3};

export function validateMultiCandidate35(data){
  const errors=[];
  const err=t=>errors.push(t);
  if(!isV35(data.prompt_version))return errors;
  errors.push(...validateV34(data));
  const comparisons=data.ticket_candidate_comparisons;
  const audit=data.ticket_candidate_search_audit;
  if(!Array.isArray(comparisons)){err('ticket_candidate_comparisons required');return errors;}
  if(!Array.isArray(audit)||audit.length!==8){err('ticket_candidate_search_audit must describe eight ticket types');return errors;}
  if(TYPES.some((t,i)=>audit[i]?.type!==t))err('ticket search audit types missing/out of order');
  const seen=new Set(), bytype=new Map(TYPES.map(t=>[t,[]]));
  for(const [i,c] of comparisons.entries()){
    const loc='comparison['+i+']';
    if(!TYPES.includes(c.type)){err(loc+' invalid type or WIN5');continue;}
    if(!Array.isArray(c.selection)||!c.selection.length||c.selection.some(n=>!Number.isInteger(n)||n<1)||(c.type!=='枠連'&&new Set(c.selection).size!==c.selection.length))err(loc+' invalid selection');
    if(['三連複','三連単'].includes(c.type)&&c.selection.length!==3)err(loc+' must have 3 selections');
    if(['馬単','馬連','枠連','ワイド'].includes(c.type)&&c.selection.length!==2)err(loc+' must have 2 selections');
    if(['単勝','複勝'].includes(c.type)&&c.selection.length!==1)err(loc+' must have 1 selection');
    const k=key(c.type,c.selection);
    if(seen.has(k))err(loc+' duplicate candidate selection');seen.add(k);
    bytype.get(c.type).push(c);
    if(!['eligible','ineligible','unpriced','probability_unavailable'].includes(c.eligibility))err(loc+' missing eligibility status');
    if(!nonempty(c.ability_reason)||!nonempty(c.risk_reason)||!nonempty(c.decision_reason))err(loc+' missing ability/risk/decision reasons');
    if(c.eligibility==='unpriced'||c.eligibility==='probability_unavailable'){
      if(c.eligibility==='unpriced'&&(c.market_odds!==null||c.ev_scenarios!==null))err(loc+' unpriced cannot have invented odds/EV');
      continue;
    }
    if(!priced(c.market_odds)||!nonempty(c.source_url)||!tstamp(c.observed_at)||!tstamp(c.assessed_at))err(loc+' missing exact quoted market evidence');
    if(!nonempty(c.probability_method)||!c.probability_scenarios||!c.ev_scenarios)err(loc+' missing probability model or scenarios');
    else {
      const ps=Object.values(c.probability_scenarios),ev=Object.values(c.ev_scenarios);
      if(ps.length<3||ps.some(n=>typeof n!=='number'||n<0||n>1)||ev.length<3||ev.some(n=>typeof n!=='number'||n<0))err(loc+' needs >=3 valid probability and EV scenarios');
      const o=Array.isArray(c.market_odds)?c.market_odds[0]:c.market_odds;
      if(priced(c.market_odds)&&Number.isFinite(c.break_even_probability)&&Math.abs(1/o-c.break_even_probability)>0.0002)err(loc+' invalid break-even probability');
    }
    if(!Number.isFinite(c.break_even_probability))err(loc+' missing break-even probability');
  }
  for(const [i,type] of TYPES.entries()){
    const a=audit[i],arr=bytype.get(type),row=data.bet_type_evaluations?.[i];
    if(!a||!row)continue;
    if(!Number.isInteger(a.generated_count)||a.generated_count<arr.length||!Number.isInteger(a.priced_count)||a.priced_count>arr.length)err('audit invalid counts '+type);
    if(a.priced_count!==arr.filter(c=>priced(c.market_odds)).length)err('audit priced_count mismatch '+type);
    if(arr.length===0&&row.status!=='not_offered'&&row.status!=='unpriced')err('missing candidate '+type);
    if(a.generated_count<depth[type]&&!nonempty(a.shortfall_reason))err('missing documented reason for low candidate generation '+type);
    if(a.priced_count<depth[type]&&!nonempty(a.price_shortfall_reason))err('missing explanation for insufficient real-odds alternatives '+type);
    if(row.status==='evaluated'){
      const matched=arr.find(c=>same(c.selection,row.candidate?.selection));
      if(!matched)err('summary type selection missing from candidate comparison '+type);
      else {
        if(!same(matched.market_odds,row.market_odds)||matched.observed_at!==row.observed_at||matched.source_url!==row.source_url)
          err('representative source/price mismatch for '+type);
      }
    }
  }
  const bets=Array.isArray(data.final_bets)?data.final_bets:[];
  for(const bet of bets){
    const c=comparisons.find(x=>key(x.type,x.selection)===key(bet.type,bet.selection));
    if(!c||c.eligibility!=='eligible'||!priced(c.market_odds))err('final_bet must match verified eligible comparison including trifecta');
    if(bet.type==='三連単'&&bet.selection.length!==3)err('ordered trifecta selection required');
  }
  if(data.purchase_decision==='buy'&&!bets.length)err('buy must specify final bets');
  if(data.purchase_decision==='pass'&&bets.length)err('pass must not contain final bets');
  return errors;
}

if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(new URL(import.meta.url).pathname)){
  let checked=0;const errors=[];
  const root='e2e_validation/predictions';
  if(fs.existsSync(root)){
    for(const ent of fs.readdirSync(root,{withFileTypes:true})){
      if(!ent.isDirectory())continue;
      for(const file of fs.readdirSync(path.join(root,ent.name)).filter(f=>f.endsWith('.json'))){
        const path0=path.join(root,ent.name,file);
        const data=JSON.parse(fs.readFileSync(path0,'utf8'));
        if(!isV35(data.prompt_version))continue;
        checked++;
        for(const e of validateMultiCandidate35(data))errors.push(path0+': '+e);
      }
    }
  }
  if(errors.length){console.error(errors.join('\n'));process.exit(1);}
  console.log('v3.5 multi-combination audit OK: '+checked+' new formal predictions; all 8 types eligible for best ticket');
}
