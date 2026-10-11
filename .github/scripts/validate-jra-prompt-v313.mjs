// Formal v3.13 prompt SHA/manifest gate: append-only versioned adoption of
// bounded winning-bet amount scaling, without modifying frozen old predictions.
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const old=json('e2e_validation/manifests/v3.12.json');
const now=json('e2e_validation/manifests/v3.13.json');
const latest=json('docs/data/latest_prompt.json');
const history=json('docs/data/prompt_history.json');
const allowed=json('docs/data/jra_v313_historical_adapter_v1.json');
const oldSup=json('docs/data/jra_ci_supersession_v312.json');
const oldWorkflowExemptions=new Map(oldSup.superseded_components.map(x=>[x.path,x]));
const hash=p=>execFileSync('git',['hash-object',p],{encoding:'utf8'}).trim();
assert.equal(now.prompt_version,'v3.13');
assert.deepEqual(now.components.slice(0,old.components.length),old.components,
 'old 83 historical SHA-pinned artifacts must remain exact in v3.13 manifest');
assert(now.components.length>=old.components.length+18,'v3.13 manifest missing new formal components');
const overrides=new Map(allowed.superseded_components.map(x=>[x.path,x]));
assert.deepEqual([...overrides.keys()].sort(),[
 '.github/scripts/validate-jra-archived-compact-v312.mjs',
 '.github/scripts/validate-jra-ci-forward-v312.mjs',
 '.github/scripts/validate-jra-prerace-v312.mjs',
 '.github/scripts/validate-jra-prompt-v312.mjs',
 'e2e_validation/validate_manifests.py'
 ]);
const seen=new Set();
for(const {path,git_blob_sha} of now.components){
 assert(!seen.has(path),'duplicate manifest path '+path);seen.add(path);
 assert(fs.existsSync(path),'required original or new v3.13 file absent '+path);
 const actual=hash(path);
 if(oldWorkflowExemptions.has(path)){
  const x=oldWorkflowExemptions.get(path);
  assert.equal(git_blob_sha,x.historical_blob_sha,'v3.11 workflow manifest SHA pin replaced '+path);
  assert.equal(actual,x.current_blob_sha,'not approved inherited v3.12 CI workflow '+path);
  const originalCommit=oldSup.historical_base_commit_sha;
  try{execFileSync('git',['cat-file','-e',originalCommit+':'+path],{stdio:'ignore'});}
  catch{execFileSync('git',['fetch','--no-tags','--depth=1','origin',originalCommit],{stdio:'ignore'});}
  assert.equal(execFileSync('git',['rev-parse',originalCommit+':'+path],{encoding:'utf8'}).trim(),
    git_blob_sha,'original v3.11 approved CI workflow missing');
 } else if(overrides.has(path)){
  const x=overrides.get(path);
  assert.equal(git_blob_sha,x.original_blob_sha,'historical legacy SHA was overwritten '+path);
  assert.equal(actual,x.current_blob_sha,'unauthorized historic validator change '+path);
  const anchor=allowed.historical_anchor_commit;
  try{execFileSync('git',['cat-file','-e',anchor+':'+path],{stdio:'ignore'});}
  catch{execFileSync('git',['fetch','--no-tags','--depth=1','origin',anchor],{stdio:'ignore'});}
  assert.equal(execFileSync('git',['rev-parse',anchor+':'+path],{encoding:'utf8'}).trim(),
   git_blob_sha,'original Git SHA not proven for old validator '+path);
 } else assert.equal(actual,git_blob_sha,'v3.13 manifest SHA mismatch '+path);
}
assert(history.entries.some(x=>x.version==='v3.13'&&x.previous_version==='v3.12'&&
 x.path==='競馬予想_完全版プロンプト_v3.13.txt'),'v3.13 append-only prompt history not present');
assert.equal(latest.version,'v3.13','v3.13 is not current canonical release');
assert.equal(latest.path,'競馬予想_完全版プロンプト_v3.13.txt');
assert.equal(latest.win_stake_formal_v313?.status,'formal_new_prestart_only');
for(const descriptor of [
 latest.win_stake_formal_v313.pipeline,
 latest.win_stake_formal_v313.validator,
 latest.win_stake_formal_v313.renderer,
 latest.win_stake_formal_v313.pdf_validator,
 latest.win_stake_formal_v313.prestart_workflow,
 latest.win_stake_formal_v313.prerace_workflow,
 latest.win_stake_formal_v313.stake_optimizer,
 latest.win_stake_formal_v313.historical_adapter,
 latest.odds_freshness_execution_overlay.policy,
 latest.odds_freshness_execution_overlay.collector,
 latest.odds_freshness_execution_overlay.freshness_gate,
 latest.odds_freshness_execution_overlay.new_race_workflow,
 latest.odds_freshness_execution_overlay.workflow]){
 assert(descriptor?.path && /^[a-f0-9]{40}$/.test(descriptor?.git_blob_sha||''),
  'missing strict v3.13 active SHA pin');
 assert.equal(hash(descriptor.path),descriptor.git_blob_sha,'latest formal SHA mismatch '+descriptor.path);
}
const prompt=fs.readFileSync(latest.path,'utf8');
for(const marker of ['[WIN-00]','[WIN-01]','[WIN-02]','[WIN-03]','[WIN-04]',
 '100円','1,200円','6,000円','STEP1','v3.12','非損失確率','発走前']){
 assert(prompt.includes(marker),'new formal release lacks required WIN stake policy '+marker);
}
const policy=json('docs/data/jra_fresh_odds_policy_v313_exec.json');
assert(policy.budget_yen===6000&&policy.refresh_all_expected_ticket_lines===true&&
 policy.reuse_previous_market_quotes===false&&policy.race_must_be_before_official_start===true);
console.log('PASS: historical 83 components sealed; v3.13 full deployment SHA pins, odds, history, WIN sizing active');
