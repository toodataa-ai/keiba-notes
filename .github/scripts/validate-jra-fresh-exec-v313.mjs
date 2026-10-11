import assert from 'node:assert/strict';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const read=p=>fs.readFileSync(p,'utf8');
const json=p=>JSON.parse(read(p));
const p=json('docs/data/latest_prompt.json');
assert.equal(p.version,'v3.13');
assert.equal(p.path,'競馬予想_完全版プロンプト_v3.13.txt');
const addon=p.odds_freshness_execution_overlay;
assert.equal(addon.version,'v2_v313');
assert.equal(addon.prior_quote_reuse_prohibited,true);
assert.equal(addon.max_source_quote_age_at_seal_seconds,600);
assert.equal(addon.market_capture_window_max_seconds,180);
const policy=json(addon.policy.path);
assert.equal(policy.reuse_previous_market_quotes,false);
assert.equal(policy.refresh_all_expected_ticket_lines,true);
assert.equal(policy.require_all_line_source_evidence_sha256,true);
assert.equal(policy.max_quote_age_at_seal_seconds,600);
assert.equal(policy.max_capture_spread_seconds,180);
assert.equal(policy.optimizer_v311_decision_unchanged,true);
assert.equal(policy.new_race_requires_same_full_price_refresh,true);
assert.equal(addon.new_race_workflow.path,policy.new_race_execution_workflow);
for(const group of ['policy','collector','freshness_gate','workflow','new_race_workflow']){
 const {path,git_blob_sha}=addon[group];
 assert.equal(execFileSync('git',['hash-object',path],{encoding:'utf8'}).trim(),git_blob_sha,
   'source changed without synchronized versioned formal pointer: '+group);
}
assert.equal(addon.workflow.path,'.github/workflows/jra-prerace-rerun-fresh-v313.yml');
assert.equal(p.prerace_overwrite_policy.rerun_workflow.path,'.github/workflows/jra-prerace-rerun-v312.yml',
   'original SHA-pinned rerun remains historically intact');
const x=read(addon.workflow.path),source=read(addon.collector.path),checker=read(addon.freshness_gate.path);
const first=read(addon.new_race_workflow.path);
assert(x.includes('v313fresh/*.json'),'fresh input routing missing');
assert(first.includes('--refresh-all'),'first predictions would reuse morning odds');
assert((first.match(/jra-check-fresh-quotes-v313-exec\.py/g)||[]).length===3,'first prediction must be checked before proof+seal');
for(const marker of ['jra-prestart-pipeline-v313.mjs','validate-jra-pdf-content-v313.py',
 'jra-publish-live-v313.py','git push origin HEAD:main'])
 assert(first.includes(marker),'new-race first publication missing '+marker);
assert(x.includes('--refresh-all'),'fresh workflow still doing missing-only recovery');
assert(!x.includes('python3 .github/scripts/jra-odds-recovery-v313.py'),'legacy collector may not run');
assert((x.match(/jra-check-fresh-quotes-v313-exec\.py/g)||[]).length===3,
  'fresh check must run before evaluation, before snapshot Git proof and before sealing');
for(const marker of ['--input "$INPUT"','--output "$RECOVERED_INPUT"','jra-prestart-pipeline-v313.mjs',
  'validate-jra-pdf-content-v313.py','jra-promote-prerace-v313.py',
  'JRA_REVISED_PREREACE_REPORT_PUBLIC_VERIFIED'])
 assert(x.includes(marker),'prepost workflow missing '+marker);
assert(source.includes("present=set() if refresh_all"),'collector does not reject previous prices');
assert(source.includes("new['market_quotes']=[]"),'collector still carries old quote bytes');
assert(source.includes("len(new['market_quotes'])==len(expected)"),'not all expected source prices collected');
assert(checker.includes("max-spread-seconds")&&checker.includes("source_capture_sha256"),'fresh quote source SHA gate missing');
console.log('PASS: v3.13 verified fresh source odds, SHA pins, prestart proof, pre/post HTTP and historic v3.12 unchanged');
