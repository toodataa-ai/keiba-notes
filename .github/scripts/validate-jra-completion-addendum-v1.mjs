// Formal JRA run orchestration only; model and immutable prior SHA pins remain untouched.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
const latest=JSON.parse(fs.readFileSync('docs/data/latest_prompt.json','utf8'));
const history=JSON.parse(fs.readFileSync('docs/data/prompt_history.json','utf8'));
const p=latest.mandatory_execution_addendum;
const sectionTags=['[COMP-00]','[COMP-01]','[COMP-02]','[COMP-03]','[COMP-04]','[COMP-05]'];
function errors(record,source){
  const out=[];
  if(record?.version!=='v1'||record?.path!=='docs/operations/jra_run_completion_addendum_v1.txt')
    out.push('official addendum path/version wrong');
  if(record?.read_each_new_jra_run!==true)out.push('not mandatory for every run');
  if(record?.scope!=='execution_orchestration_and_completion_only')out.push('prediction scope unexpectedly changed');
  if(typeof source!=='string'||source.length<1400)out.push('execution addendum truncated');
  for(const tag of sectionTags)if(!source.includes(tag))out.push('missing '+tag);
  for(const marker of ['途中終了禁止','公開','全件','進捗','具体的','発走前','GitHub','PDF','停止を許す','無限再試行禁止'.replace('無限再試行禁止','無限再試行')])
    if(!source.includes(marker))out.push('missing execution condition '+marker);
  return out;
}
assert.equal(latest.version,'v3.11','pinned JRA model remains v3.11');
assert.equal(latest.path,'競馬予想_完全版プロンプト_v3.11.txt','official formal prompt filename changed');
assert(p&&fs.existsSync(p.path),'mandatory execution addendum is absent');
const content=fs.readFileSync(p.path,'utf8');
assert.deepEqual(errors(p,content),[],'execution contract failed');
const gitSha=execFileSync('git',['hash-object',p.path],{encoding:'utf8'}).trim();
assert.equal(gitSha,p.git_blob_sha,'execution addendum SHA pin changed');
assert(latest.rule.includes('MANDATORY EXECUTION ADDENDUM') &&
  latest.rule.includes('CONTINUE WITHOUT EARLY TERMINATION') &&
  latest.rule.includes(p.path) &&
  latest.rule.includes('actual public HTTP/file verification'),
  'canonical latest_prompt.json must demand complete-unless-blocked run and actual public evidence');
assert(history.execution_addenda?.some(x=>x.id==='jra-completion-v1'&&x.path===p.path&&x.applies_to_prompt_version==='v3.11'),
  'historical execution-policy log not appended');
assert.deepEqual(errors(p,content.replace('[COMP-03]','[REMOVED]')).includes('missing [COMP-03]'),true,
  'negative regression failed to detect a lost blocker/stop rule');
assert.deepEqual(errors({...p,read_each_new_jra_run:false},content).includes('not mandatory for every run'),true,
  'negative regression failed to detect optional policy');
console.log('PASS JRA v3.11 mandatory completion-unless-blocked addendum: six sections, immutable content SHA, history, negative regressions');
