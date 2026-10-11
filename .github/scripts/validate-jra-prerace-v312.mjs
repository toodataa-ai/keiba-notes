// v3.12 before-post safe revision contract: audit the ACTUAL workflow and publisher.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const read=p=>fs.readFileSync(p,'utf8');
const j=p=>JSON.parse(read(p));
const latest=j('docs/data/latest_prompt.json');
assert(['v3.12','v3.13'].includes(latest.version),'only historical/current v312-v313 are supported');
const refs=latest.prerace_overwrite_policy;
assert.equal(refs.version,'v312');
assert.equal(refs.read_each_new_jra_run,true);
for(const item of [refs.policy,refs.instructions,refs.publisher,refs.rerun_workflow]){
 assert(fs.existsSync(item.path),'missing prestart overwrite source '+item.path);
 assert.equal(execFileSync('git',['hash-object',item.path],{encoding:'utf8'}).trim(),
   item.git_blob_sha,'canonical rerun component unpinned '+item.path);
}
assert.equal(refs.rerun_workflow.path,'.github/workflows/jra-prerace-rerun-v312.yml');
assert.equal(refs.publisher.path,'.github/scripts/jra-promote-prerace-v312.py');
const w=read(refs.rerun_workflow.path),publisher=read(refs.publisher.path);
const markers=[
 'Validate unchanged formally pinned predictor and prereace-revision approval',
 'Validate newly added audited input, official post time and unique paths',
 'Recover and attest each missing actual priced ticket before STEP2',
 'Build complete v3.12 purchase set using unchanged prereace STEP1',
 'Generate every detailed page and reject blank pages before proof commit',
 'Strict start gate and immutable prereace Git snapshot',
 'Seal and validate formal report PDF, prepare revision manifest',
 'Commit only the latest canonical index plus new immutable artifacts and journal',
 'Verify newly published HTML PDF current registry and revised journal over public HTTP'
];
let last=-1;for(const m of markers){const i=w.indexOf(m);assert(i>last,'missing or reordered prereace publish gate '+m);last=i;}
for(const m of [
 'e2e_validation/inputs/revisions/v312/*.json',
 'jra-odds-recovery-v312.py',
 'jra-prestart-pipeline-v312.mjs',
 'jra-render-live-v312.py',
 'validate-jra-pdf-content-v312.py',
 'jra-promote-prerace-v312.py',
 'git add -- "$SNAPSHOT" "$RECOVERED_INPUT"',
 'git push origin HEAD:main',
 'cmp -s "$FILE"'
])assert(w.includes(m),'missing rerun proof/publication control '+m);
for(const m of [
 "pred['prompt_version']=='v3.12'",
 'coverage.get(\'status\')==\'complete\'',
 'check_proof(',
 'utc_now()<race_start',
 'older',  // overridden below to test actual old-record archival fields
]){if(m==='older')continue; assert(publisher.includes(m),'missing canonical publisher guard '+m);}
assert(publisher.includes("'old':copy.deepcopy(old)")&&
 publisher.includes("'immutable_prior_prediction'")&&
 publisher.includes("'immutable_prior_pdf'"),'historical original/journal retention absent');
assert(!w.includes('jra-promote-prerace-v311.py'),'current version may not downgrade publisher');
console.log('PASS v3.12 prereace rerun, quote proof, immutable snapshots, PDF, journal, and final HTTP verification');
