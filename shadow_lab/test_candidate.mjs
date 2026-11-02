// Real engine E2E with explicitly synthetic FUTURE timing. Never write evidence.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {assembleV313} from '../.github/scripts/jra-prestart-pipeline-v313.mjs';
const input=JSON.parse(fs.readFileSync('e2e_validation/inputs/v313-recovered/2026-10-31-fantasy-stakes-run41143212430.json'));
input.race_context.start_at='2099-01-01T15:00:00+09:00';
// Bound the synthetic strategy universe to one exact line per ticket type.
// All other modes remain explicitly excluded before pricing.
import {TYPES,MODES} from '../.github/scripts/jra-strategy-engine-v39.mjs';
input.strategies=TYPES.map((t,i)=>{
 const st=JSON.parse(JSON.stringify(input.strategies.find(s=>s.type===t)));
 const quote=input.market_quotes.find(q=>q.type===t);
 st.strategy_kind='single';st.definition={selection:quote.selection};return st;
});
input.mode_exclusions=TYPES.flatMap(type=>MODES[type].filter(m=>m!=='single').map(mode=>({type,mode,reason:'Synthetic bounded test',evidence:'Test-only predetermined single line'})));
// A low-price synthetic market avoids expensive portfolio search in unit E2E.
// This file is new, test-only, and removed on process exit.
const capture='e2e_validation/quote-evidence/shadow-test-'+process.pid+'.json';
process.on('exit',()=>{if(fs.existsSync(capture))fs.unlinkSync(capture);});
for(const q of input.market_quotes){q.market_odds=1.01;q.source_url='https://example.org/shadow-synthetic-only';}
const observed=input.market_quotes[0].observed_at;
for(const q of input.market_quotes)q.observed_at=observed;
const bytes=JSON.stringify({source_url:input.market_quotes[0].source_url,observed_at:observed,entries:input.market_quotes.map(q=>({type:q.type,selection:q.selection,market_odds:q.market_odds}))});
fs.writeFileSync(capture,bytes,{flag:'wx'});
import {createHash} from 'node:crypto';
for(const q of input.market_quotes){q.source_capture_path=capture;q.source_capture_sha256=createHash('sha256').update(bytes).digest('hex');}
const cutoff='2026-10-31T08:16:00+09:00';
const baseline=assembleV313(input,cutoff);
const original=JSON.stringify(input);
for(const theme of ['pace_positioning','track_condition','ticket_portfolio','field_experience','E0','E1','E2']){
 const factor=theme==='pace_positioning'?1:theme==='track_condition'?2:null;
 const request={theme,input,baseline,candidate_version:'test-only',cutoff,
  factor_index:factor,grades:Object.fromEntries(input.step1.runners.map(r=>[r.horse_number,'B+'])),
  multipliers:Object.fromEntries(input.step1.runners.map((r,i)=>[r.horse_number,i===0?1.1:1]))};
 const requestPath=path.join(os.tmpdir(),'shadow-request-'+process.pid+'.json');
 fs.writeFileSync(requestPath,JSON.stringify(request));
 let out;
 try{out=JSON.parse(execFileSync('node',['shadow_lab/candidate.mjs',requestPath],{maxBuffer:20e6,timeout:20000}));}
 finally{fs.unlinkSync(requestPath);}
 assert.equal(JSON.stringify(input),original);
 assert.equal(out.candidate.stage,'shadow_only');
 assert.equal(out.candidate.proof_commit,null);
 assert.ok(Math.abs(Object.values(out.probabilities.candidate.win).reduce((a,b)=>a+b)-1)<1e-6);
 assert.ok(Math.abs(Object.values(out.probabilities.candidate.top3).reduce((a,b)=>a+b)-3)<1e-6);
 assert.ok(out.candidate.total_stake_yen<=6000);
 if(theme==='ticket_portfolio')assert.deepEqual(out.candidate.step1_ranking,baseline.step1_ranking);
 else for(const r of out.candidate.step1_ranking){
  const before=baseline.step1_ranking.find(x=>x.horse_number===r.horse_number);
  for(let j=0;j<9;j++)if(j!==factor)assert.equal(r.factor_grades[j],before.factor_grades[j]);
 }
 console.log('PASS_SYNTHETIC_ONLY_FULL_ENGINE',theme);
}
