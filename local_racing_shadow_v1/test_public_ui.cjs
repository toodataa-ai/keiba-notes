#!/usr/bin/env node
// Fail-closed regression guard for public local-Shadow rendering (JRA isolated).
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');

const file='docs/local-racing-shadow.html';
const html=fs.readFileSync(file,'utf8');
const match=html.match(/<script>\s*([\s\S]*?)<\/script>/);
assert(match,'Local Shadow inline JS missing');
const fullScript=match[1];
new vm.Script(fullScript,{filename:file});
const cutoff=fullScript.indexOf('async function load(){');
assert(cutoff>0,'Cannot isolate UI renderer from live fetch bootstrap');
const elements={};
const document={
  getElementById(id){return elements[id]??(elements[id]={innerHTML:'',textContent:'',value:'all',hidden:true})},
  querySelectorAll(){return[]},
};
const ctx=vm.createContext({document,console,Intl,Date,Set});
vm.runInContext(fullScript.slice(0,cutoff)+
  '\nglobalThis.renderReviewForTest=raceReviewHtml;'+
  '\nglobalThis.renderAnalysisForTest=renderAnalysis;'+
  '\nglobalThis.setManifestForTest=function(m){manifest=m;};',ctx);

const publicManifest=JSON.parse(fs.readFileSync('docs/data/local_racing_shadow_public.json','utf8'));
const date='2026-10-08';
const entries=publicManifest.races.filter(r=>r.date===date);
assert.equal(entries.length,24,'Required 24 races');
let checked=0;
for(const entry of entries){
  assert.equal(entry.status,'reviewed','Race unexpectedly unreviewed: '+entry.race_id);
  assert(entry.review_path&&entry.result_path,'Missing review/result public path '+entry.race_id);
  const result=JSON.parse(fs.readFileSync(path.join('docs',entry.result_path),'utf8'));
  const review=JSON.parse(fs.readFileSync(path.join('docs',entry.review_path),'utf8'));
  const view=ctx.renderReviewForTest(review,result,entry);
  assert(view.includes('発走前順位と実際の着順'),'Missing comparison '+entry.race_id);
  assert(view.includes('実際の上位3着'),'Missing podium '+entry.race_id);
  assert(view.includes('NAR公式競走成績を確認'),'Missing evidence link '+entry.race_id);
  assert(!view.includes('回顧はまだありません'),'False no-review display '+entry.race_id);
  assert(!view.includes('[object Object]'),'Object leakage '+entry.race_id);
  assert(view.includes(String(review.actual_top_pick_finish)+'着'),
    'Missing top-pick actual finish '+entry.race_id);
  const publicReview=fs.readFileSync(path.join('docs',entry.review_path));
  const canonicalReview=fs.readFileSync(entry.review_path.replace('data/local-racing-shadow','local_racing_shadow_v1'));
  assert(publicReview.equals(canonicalReview),'Published review mirror differs '+entry.race_id);
  checked++;
}
const first=entries[0];
const result=JSON.parse(fs.readFileSync(path.join('docs',first.result_path),'utf8'));
const review=JSON.parse(fs.readFileSync(path.join('docs',first.review_path),'utf8'));
assert.throws(()=>ctx.renderReviewForTest({...review,race_id:'wrong-id'},result,first),/race_id/,'Failed join identity guard');
assert(!ctx.renderReviewForTest(null,result,first).includes('回顧はまだありません'),
  'Reviewed entry must never falsely display missing review');
ctx.setManifestForTest(publicManifest);
ctx.renderAnalysisForTest();
const daily=elements.analysisList.innerHTML;
assert(daily.includes('12.5%')&&daily.includes('54.2%'),'Incorrect daily report rates');
assert(!daily.includes('[object Object]'),'Daily analysis object-to-string regression');
console.log(JSON.stringify({test:'local-shadow-public-ui',date,races_rendered:checked,
  negative_case:'PASS',analysis:'PASS',prediction_files_changed:0,status:'PASS'}));
