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
assert.equal(now.prompt_version,'v3.12');
assert.deepEqual(now.components.slice(0,old.components.length),old.components,
  'historical v3.11 SHA-pinned components must remain byte-identical');
assert(now.components.length>=old.components.length+16,'v3.12 components incomplete');
const unique=new Set();
for(const {path,git_blob_sha} of now.components){
 assert(!unique.has(path),'duplicate SHA pin for '+path);
 unique.add(path);
 assert(fs.existsSync(path),'missing v3.12 or baseline artifact '+path);
 assert.equal(execFileSync('git',['hash-object',path],{encoding:'utf8'}).trim(),git_blob_sha,
   'Git SHA mismatch '+path);
}
assert(hist.entries.some(x=>x.version==='v3.12'&&x.previous_version==='v3.11'&&x.path==='競馬予想_完全版プロンプト_v3.12.txt'),'v3.12 additive history missing');
assert.equal(policy.effective_prompt_version,'v3.12');
assert.equal(policy.purchase_budget_yen,6000);
assert.equal(policy.source_provenance.strict_quote_coverage,true);
assert.equal(policy.comparison.joint_outcome_union,true);
assert.equal(policy.report.max_pdf_pages,null);
assert(['v3.11','v3.12'].includes(latest.version),'unexpected canonical pointer');
if(latest.version==='v3.12')
 assert.equal(latest.path,'競馬予想_完全版プロンプト_v3.12.txt');
const prompt=fs.readFileSync('競馬予想_完全版プロンプト_v3.12.txt','utf8');
for(const marker of ['[COV-00]','[COV-01]','[COV-02]','[COV-03]','[COV-04]',
  '6,000円','三連単','STEP1','オッズ','集合的中率','不採用'])
 assert(prompt.includes(marker),'v3.12 formal prompt missing '+marker);
console.log('PASS: v3.12 source and previous 42 immutable components are pinned and valid; current latest='+latest.version);
