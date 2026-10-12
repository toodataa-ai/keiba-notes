import fs from 'node:fs';
import assert from 'node:assert/strict';
import {buildFormalThreeCommandPlan} from './jra-build-formal-3action-v315.mjs';
const sourcePaths=[
  'e2e_validation/predictions/2026-10-12-october-stakes/v3.13-rerun38185599767-attempt2.json',
  'e2e_validation/predictions/2026-10-12-swan-stakes/v3.13-rerun38185612987-attempt1.json'
];
for(const p of sourcePaths){
 const raw=fs.readFileSync(p),o=JSON.parse(raw);o.__source_path=p;
 const sealTime=new Date(Date.parse(o.final_bets_fixed_at)+1000).toISOString();
 const plan=buildFormalThreeCommandPlan(o,raw,{now_iso:sealTime});
 assert.equal(plan.status,'pending_git_proof');
 assert.equal(plan.total_stake_yen,plan.formal_bets.reduce((n,x)=>n+x.stake_yen,0));
 assert.equal(plan.regular_commands.length<=3,true);
 assert.equal(plan.medium_command.row,4);
 assert.equal(plan.large_command.row,5);
 assert.ok(plan.quote_age_max_seconds<=600);
 assert.ok(plan.source_prediction_sha256);
 const id=o.race_id;
 const output='/tmp/jra-v315-preview-'+id+'.json';
 plan.status='formal_prestart';plan.proof_commit='a'.repeat(40);
 fs.writeFileSync(output,JSON.stringify(plan,null,2));
 console.log('PASS_V315_REAL_NEWEST_FORMAL_SOURCE',id,'regular',plan.regular_commands.length,
   'extra',plan.medium_command.method,plan.large_command.method,
   'tickets',plan.formal_bets.length,'stake',plan.total_stake_yen,
   'ev',plan.purchase_metrics.modeled_expected_net_profit_yen,
   'quote_age',plan.quote_age_max_seconds,
   'source_path',p);
 // Source is immutable; this is a test-only synthetic seal that cannot be published.
 assert.equal(raw.compare(fs.readFileSync(p)),0);
}
console.log('PASS_V315_FULL_SOURCE_REPLAY');

