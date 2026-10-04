import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const readJson=(p)=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));

const latest=readJson('docs/data/latest_prompt.json');
const history=readJson('docs/data/prompt_history.json');
const entries=Array.isArray(history.entries)?history.entries:[];
const errors=[];

if(!latest.version) errors.push('latest_prompt.json: version is required');
if(!latest.path) errors.push('latest_prompt.json: path is required');
if(!entries.length) errors.push('prompt_history.json: entries must not be empty');

const seen=new Set();
for(const entry of entries){
  const key=entry.version||'(missing version)';
  if(seen.has(key)) errors.push(`prompt_history.json: duplicate version ${key}`);
  seen.add(key);

  for(const field of ['version','date','path','summary','changes','reason']){
    if(!(field in entry)) errors.push(`prompt_history.json: ${key} is missing ${field}`);
  }
  if(!Array.isArray(entry.changes)){
    errors.push(`prompt_history.json: ${key}.changes must be an array`);
  }else if(entry.source!=='baseline'&&entry.changes.length===0){
    errors.push(`prompt_history.json: ${key}.changes must describe at least one improvement`);
  }
  if(!entry.summary) errors.push(`prompt_history.json: ${key}.summary must not be empty`);
  if(!entry.reason) errors.push(`prompt_history.json: ${key}.reason must not be empty`);
  if(entry.path&&!fs.existsSync(path.join(root,entry.path))){
    errors.push(`prompt_history.json: ${key} points to missing file ${entry.path}`);
  }
}

const current=entries.find(e=>e.version===latest.version);
if(!current){
  errors.push(`prompt_history.json: latest version ${latest.version} has no history entry`);
}else if(current.path!==latest.path){
  errors.push(`prompt history path mismatch for ${latest.version}: ${current.path} != ${latest.path}`);
}

if(latest.path&&!fs.existsSync(path.join(root,latest.path))){
  errors.push(`latest_prompt.json points to missing file ${latest.path}`);
}

if(errors.length){
  console.error('Prompt history validation failed:');
  for(const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(`Prompt history OK: latest=${latest.version}, entries=${entries.length}`);
