// Forward-compatible execution for SHA-frozen historical CI validators.
// A legacy validator is executed without alteration when its historical version
// is current. When v3.12 is current, the v3.12 SHA/history compatibility contract
// supersedes ONLY the old validators' hard-coded latest-version condition.
// Their underlying fixed scripts, source blobs, prediction/STEP1 data remain intact.
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
const scripts=process.argv.slice(2);
assert(scripts.length>0,'explicit historical CI validators required');
const current=JSON.parse(fs.readFileSync('docs/data/latest_prompt.json','utf8'));
assert(['v3.11','v3.12'].includes(current.version),'unsupported canonical JRA release version');
const allowed=/^\.github\/scripts\/(?:validate-jra-(?:balanced-prompt-v311|portfolio-prompt-v31[01]|strategy-prompt-v3[89]|reader-v37|one-shot-v36|completion-addendum-v1)\.mjs)$/;
for(const script of scripts){
 assert(allowed.test(script),'unexpected historical script '+script);
 assert(fs.existsSync(script),'missing historical executable '+script);
}
const executions=current.version==='v3.12'?['.github/scripts/validate-jra-prompt-v312.mjs']:scripts;
for(const script of executions){
 const p=spawnSync(process.execPath,[script],{stdio:'inherit'});
 if(p.error)throw p.error;
 assert.equal(p.status,0,'validator failed: '+script);
}
console.log('PASS JRA forward-compatible historical CI scope, current='+current.version+
  ', protected historical checks='+scripts.join(','));
