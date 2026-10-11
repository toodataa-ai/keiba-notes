// Formal v3.12 manifest gate; v3.11's pinned historical gate is left untouched.
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const old=json('e2e_validation/manifests/v3.11.json');
const now=json('e2e_validation/manifests/v3.12.json');
const latest=json('docs/data/latest_prompt.json');
const hist=json('docs/data/prompt_history.json');
const policy=json('docs/data/jra_v312_purchase_coverage_policy.json');
const supersession=json('docs/data/jra_ci_supersession_v312.json');
assert.equal(supersession.applies_to,'v3.12');
assert.equal(supersession.fail_closed_on_any_other_sha_mismatch,true);
const replacements=new Map(supersession.superseded_components.map(x=>[x.path,x]));
assert.equal(replacements.size,1,'only the explicitly approved historical v3.11 CI workflow may be superseded');
assert.equal(now.prompt_version,'v3.12');
assert.deepEqual(now.components.slice(0,old.components.length),old.components,
  'historical v3.11 SHA-pinned components must remain byte-identical');
assert(now.components.length>=old.components.length+16,'v3.12 components incomplete');
// Narrow v3.13 supersession: old SHA-pinned historical source remains available
// at the exact approved original commit. Only these two version-acceptance adapters
// may differ in the working tree; every model, historical bet, and original CI
// contract continues to be verified against v3.12's immutable manifest.
const v313Sup=latest.version==='v3.13'?json('docs/data/jra_v313_historical_adapter_v1.json'):null;
const v313Replacements=new Map((v313Sup?.superseded_components||[]).map(x=>[x.path,x]));
if(v313Sup){
 assert.deepEqual([...v313Replacements.keys()].sort(),[
  '.github/scripts/validate-jra-ci-forward-v312.mjs',
  '.github/scripts/validate-jra-prompt-v312.mjs'
 ],'v3.13 exception exceeds legacy pointer acceptance adapters');
 assert(/^[a-f0-9]{40}$/.test(v313Sup.historical_anchor_commit));
}
const unique=new Set();
for(const {path,git_blob_sha} of now.components){
 assert(!unique.has(path),'duplicate SHA pin for '+path);
 unique.add(path);
 assert(fs.existsSync(path),'missing v3.12 or baseline artifact '+path);
 const actual=execFileSync('git',['hash-object',path],{encoding:'utf8'}).trim();
 const ciReplacement=replacements.get(path);
 if(ciReplacement){
   assert.equal(git_blob_sha,ciReplacement.historical_blob_sha,
     'legacy v3.11 manifest SHA pin was altered: '+path);
   assert.equal(actual,ciReplacement.current_blob_sha,
     'CI compatibility workflow differs from audited v3.12 successor');
   // Older Actions workflows use fetch-depth=1. Load the known original
   // pre-release commit when the archived Git object is absent locally.
   const originalCommit=supersession.historical_base_commit_sha;
   assert(/^[0-9a-f]{40}$/.test(originalCommit),'unverified historical anchor commit');
   let originalPresent=false;
   try{
     originalPresent=execFileSync('git',['cat-file','-t',ciReplacement.historical_blob_sha],
       {encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim()==='blob';
   }catch{}
   if(!originalPresent){
     execFileSync('git',['fetch','--no-tags','--depth=1','origin',originalCommit],
       {encoding:'utf8',stdio:['ignore','pipe','pipe']});
   }
   assert.equal(execFileSync('git',['rev-parse',originalCommit+':'+path],{encoding:'utf8'}).trim(),
      ciReplacement.historical_blob_sha,'actual historical workflow differs from frozen v3.11 manifest');
   assert.equal(execFileSync('git',['cat-file','-t',ciReplacement.historical_blob_sha],{encoding:'utf8'}).trim(),
     'blob','original approved v3.11 workflow Git blob missing');
   assert(fs.readFileSync(path,'utf8').includes(ciReplacement.required_compatibility_marker),
     'compatibility check is missing from authorized successor CI workflow');
 } else if(v313Replacements.has(path)){
   const exception=v313Replacements.get(path);
   assert.equal(exception.original_blob_sha,git_blob_sha,'protected SHA pin cannot be replaced '+path);
   assert.equal(actual,exception.current_blob_sha,'unexpected version adapter source '+path);
   const ancestor=v313Sup.historical_anchor_commit;
   try{
     execFileSync('git',['cat-file','-e',ancestor+':'+path],{stdio:'ignore'});
   }catch{
     execFileSync('git',['fetch','--no-tags','--depth=1','origin',ancestor],
       {stdio:['ignore','ignore','pipe']});
   }
   assert.equal(execFileSync('git',['rev-parse',ancestor+':'+path],{encoding:'utf8'}).trim(),
    git_blob_sha,'the approved prior v3.12 validator must remain historically available');
 } else assert.equal(actual,git_blob_sha,'Git SHA mismatch '+path);
}
assert(hist.entries.some(x=>x.version==='v3.12'&&x.previous_version==='v3.11'&&x.path==='競馬予想_完全版プロンプト_v3.12.txt'),'v3.12 additive history missing');
assert.equal(policy.effective_prompt_version,'v3.12');
assert.equal(policy.purchase_budget_yen,6000);
assert.equal(policy.source_provenance.strict_quote_coverage,true);
assert.equal(policy.comparison.joint_outcome_union,true);
assert.equal(policy.report.max_pdf_pages,null);
assert(['v3.11','v3.12','v3.13'].includes(latest.version),'unexpected canonical pointer');
if(latest.version==='v3.12')
 assert.equal(latest.path,'競馬予想_完全版プロンプト_v3.12.txt');
const prompt=fs.readFileSync('競馬予想_完全版プロンプト_v3.12.txt','utf8');
for(const marker of ['[COV-00]','[COV-01]','[COV-02]','[COV-03]','[COV-04]',
  '6,000円','三連単','STEP1','オッズ','集合的中率','不採用'])
 assert(prompt.includes(marker),'v3.12 formal prompt missing '+marker);
console.log('PASS: v3.12 source and previous 42 immutable components are pinned and valid; current latest='+latest.version);
