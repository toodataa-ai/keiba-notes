import fs from 'node:fs';
import {validateV34} from './validate-purchase-gate-v34.mjs';
const slugs=['2026-10-10-saudi-arabia-royal-cup','2026-10-10-mimuro-stakes'];
const problems=[];
for(const slug of slugs){
  const base='docs/data/v3.4-research/';
  const p=JSON.parse(fs.readFileSync(base+'prediction-'+slug+'.json','utf8'));
  const s=JSON.parse(fs.readFileSync(base+'step1-'+slug+'.json','utf8'));
  const proof=JSON.parse(fs.readFileSync(base+'proof-'+slug+'.json','utf8'));
  problems.push(...validateV34(p).map(e=>slug+': '+e));
  if(p.prompt_version!=='v3.4'||p.bet_type_evaluations.length!==8)problems.push(slug+': not eight v3.4 bet types');
  if(p.step1_blob_sha!==undefined && !p.step1_blob_sha)problems.push(slug+': missing step1 SHA');
  if(p.step1_fixed_at!==s.generated_at)problems.push(slug+': different fixed STEP1 time');
  if(!proof.passed||proof.race_id!==slug||proof.snapshot_path!==base+'prediction-'+slug+'.json')problems.push(slug+': prereace proof mismatch');
  if(!p.official_registry_excluded||p.total_stake_yen!==100||!p.previous_records_not_modified)problems.push(slug+': protection or stake invariant');
  if('WIN5' in p.purchase_gate||p.bet_type_evaluations.some(r=>r.type==='WIN5'))problems.push(slug+': WIN5 must be excluded');
  for(const r of p.bet_type_evaluations){
    if(!r.probability_scenarios||!r.ev_scenarios||!r.market_odds||!r.source_url)problems.push(slug+': ungrounded odds or probability '+r.type);
  }
  console.log(slug+': 8 local bet types, full-field probabilities, proof '+proof.proof_commit+', research stake '+p.total_stake_yen);
}
if(problems.length){console.error('v3.4 research snapshot checks failed\n'+problems.join('\n'));process.exit(1);}
console.log('v3.4 research snapshots verified (not auto-promoted to official races.json)');
