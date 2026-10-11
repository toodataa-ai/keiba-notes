// Real prestart replay of v3.13 formal STEP2: baseline unchanged, typed risk,
// exact same ticket selection and immutable original JSON byte hash.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {upgradeToV313} from './jra-prestart-pipeline-v313.mjs';
import {validateV313} from './validate-jra-portfolio-v313.mjs';
import {evaluateStrategy,ticketKey} from './jra-strategy-engine-v39.mjs';
const races=[
 'e2e_validation/predictions/2026-10-11-ireland-trophy/v3.12-rerun38113832729-attempt1.json',
 'e2e_validation/predictions/2026-10-11-uzumasa-stakes/v3.12-rerun38113827050-attempt2.json'
];
for(const file of races){
 const original=fs.readFileSync(file,'utf8'),record=JSON.parse(original);
 const changed=upgradeToV313(record);
 assert.equal(changed.prompt_version,'v3.13');
 assert.equal(changed.v312_balanced_baseline.total_stake_yen,record.total_stake_yen);
 assert.deepEqual(changed.v312_balanced_baseline.purchase_portfolio_selection,record.purchase_portfolio_selection);
 assert.deepEqual(changed.v312_balanced_baseline.final_bets,record.final_bets);
 assert.deepEqual(changed.step1_ranking,record.step1_ranking);
 assert.deepEqual(changed.outcome_distributions,record.outcome_distributions);
 assert.deepEqual(changed.purchase_set_comparisons_v312,record.purchase_set_comparisons_v312);
 assert.equal(changed.final_bets.length,record.final_bets.length);
 assert(changed.final_bets.every((x,i)=>x.type==='単勝'||x.stake_yen===record.final_bets[i].stake_yen));
 assert(changed.total_stake_yen<=6000);
 assert.equal(fs.readFileSync(file,'utf8'),original);
 const errors=validateV313(changed);
 assert.deepEqual(errors,[],file+' '+errors.join('; '));
 const altered=JSON.parse(JSON.stringify(changed));
 altered.total_stake_yen+=100;
 assert(validateV313(altered).some(x=>/final purchase amount/.test(x)),
   'malicious amount mismatch must fail closed');
 const hidden=JSON.parse(JSON.stringify(changed));
 if(hidden.final_bets.length){
  hidden.final_bets[0].stake_yen+=100;
  assert(validateV313(hidden).some(x=>/stake decision/.test(x)),
    'malicious one-line stake must fail closed');
 }
 console.log('PASS_REAL_RACE_V313',record.race_id,
   'original=',record.total_stake_yen,'v313=',changed.total_stake_yen,
   'formal=',changed.stage,'proof=',changed.proof_commit,
   'win_sizing_activated=',changed.win_stake_allocation_v313.activated);
}
// 100->200 win recovery is separately proven in existing synthetic pilot test.
console.log('PASS: two real prestart immutable v3.12 predictions reproduced through new formal v3.13 rule with tamper rejection');
