// Forward-only active execution compatibility gate. Does not mutate or weaken
// any v3.13 source manifest, prediction, approved reader-v1 CSS or historic SHA.
// The immutable 2026 v3.13 validator predates the separately approved current E2E
// supersession for three CI files. This gate delegates the complete original
// manifest and anchored-historical checks to the active Python auditor.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const gitSha=p=>execFileSync('git',['hash-object',p],{encoding:'utf8'}).trim();
const latest=read('docs/data/latest_prompt.json');
const manifest=read('e2e_validation/manifests/v3.13.json');
const ci=read('docs/data/jra_current_e2e_ci_supersession_v1.json');
assert.equal(latest.version,'v3.13');
assert.equal(latest.path,'競馬予想_完全版プロンプト_v3.13.txt');
assert.equal(manifest.prompt_version,'v3.13');
assert.equal(manifest.components.length,104);
assert.equal(ci.scope,'current_e2e_orchestration_supersession_only');
assert.deepEqual(ci.superseded_components.map(x=>x.path).sort(),[
 '.github/workflows/e2e-validation.yml',
 'e2e_validation/validate_experience_history_v312.py',
 'e2e_validation/validate_manifests.py']);
for (const item of ci.superseded_components)
 assert.equal(gitSha(item.path),item.current_blob_sha,'unaudited active E2E file '+item.path);
const v313=latest.win_stake_formal_v313;
const descriptors=[
 v313.pipeline,v313.validator,v313.renderer,v313.pdf_validator,
 v313.prestart_workflow,v313.prerace_workflow,v313.stake_optimizer,
 v313.historical_adapter,
 latest.odds_freshness_execution_overlay.policy,
 latest.odds_freshness_execution_overlay.collector,
 latest.odds_freshness_execution_overlay.freshness_gate,
 latest.odds_freshness_execution_overlay.new_race_workflow,
 latest.odds_freshness_execution_overlay.workflow
];
for (const d of descriptors){
 assert(d?.path && /^[a-f0-9]{40}$/.test(d?.git_blob_sha??''),
   'missing pinned immutable v3.13 descriptor');
 assert.equal(gitSha(d.path),d.git_blob_sha,'immutable current v3.13 model component changed '+d.path);
}
assert.equal(latest.generic_one_shot_execution_v314.formal_prediction_version,'v3.13');
assert.equal(latest.purchase_command_formal_v315.version,'v3.15');
execFileSync('python3',['e2e_validation/validate_manifests.py'],{stdio:'inherit'});
console.log('PASS_JRA_V313_ACTIVE_104_SHA_AND_HISTORICAL_BRIDGES: no changes to immutable models or history');
