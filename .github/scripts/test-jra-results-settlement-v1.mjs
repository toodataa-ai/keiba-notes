#!/usr/bin/env node
// Regression guard for the STAGING results renderer. This test never writes race data.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const source=readFileSync('docs/staging/assets/results.js','utf8');
const previewHtml=readFileSync('docs/staging/results.html','utf8');
const productionHtml=readFileSync('docs/results.html','utf8');
assert(previewHtml.includes('src="staging/assets/results.js?v=20261013-settlement1"'),
  'staging must load its dedicated new renderer');
assert(productionHtml.includes('src="assets/results.js?v='),
  'production HTML must continue using the untouched production renderer');
const db=JSON.parse(readFileSync('docs/data/races.json','utf8'));
const element={innerHTML:''};
const context={
  console,
  document:{getElementById:()=>element},
  fetch:async()=>{throw new Error('disabled in read-only offline test');}
};
// The script defines the production-equivalent betPanel function and then performs
// an unrelated async document fetch. Expose only the pure rendering helpers.
runInNewContext(source+'\n;globalThis.__test={betPanel,ticketKey};',context,{timeout:5000});
const {betPanel,ticketKey}=context.__test;
const statuses=html=>[...html.matchAll(/class="bet-status[^"]*">([^<]+)<\/span>/g)].map(x=>x[1]);
const checked=db.races.filter(r=>r.date>='2026-10-10'&&r.date<='2026-10-12'
  && r.status==='reviewed'
  && Array.isArray(r.final_bets)&&r.final_bets.length
  && Array.isArray(r.settlements)&&r.settlements.length);
assert.equal(checked.length,6,'expected six settled JRA main races for the 2026-10-10 to 2026-10-12 weekend');
for(const r of checked){
  const html=betPanel(r);
  const got=statuses(html);
  assert.equal(got.length,r.final_bets.length,r.id+': all bets visible');
  assert(!got.includes('結果不明'),r.id+': final bets should all be settled');
  assert.equal(got.filter(s=>s==='的中').length,r.settlements.filter(s=>s.hit===true).length,r.id+': wins');
  assert.equal(got.filter(s=>s==='ハズレ').length,r.settlements.filter(s=>s.hit===false).length,r.id+': misses');
  assert(html.includes('払戻合計'),r.id+': payout summary visible');
}
const swan=checked.find(r=>r.id==='2026-10-12-swan-stakes');
const october=checked.find(r=>r.id==='2026-10-12-october-stakes');
assert(swan&&october,'Oct 12 JRA races present');
let swanHtml=betPanel(swan);
assert.equal(statuses(swanHtml).length,24);
assert.equal(statuses(swanHtml).filter(s=>s==='的中').length,1);
assert.equal(statuses(swanHtml).filter(s=>s==='ハズレ').length,23);
assert(swanHtml.includes('払戻 9,380円'),'winning trio payout 9380');
assert(swanHtml.includes('6,980円'),'winning race net gain 6980');
assert.equal(statuses(betPanel(october)).filter(s=>s==='ハズレ').length,18);
assert.equal(ticketKey('三連複',[1,4,9]),ticketKey('三連複','9-1-4'),'trio is unordered');
assert.equal(ticketKey('馬連',[4,2]),ticketKey('馬連',[2,4]),'quinella is unordered');
assert.notEqual(ticketKey('馬単',[4,2]),ticketKey('馬単',[2,4]),'exacta is ordered');
assert.notEqual(ticketKey('三連単',[1,4,9]),ticketKey('三連単',[9,4,1]),'trifecta is ordered');
const reversed=JSON.parse(JSON.stringify(swan));
reversed.final_bets[7].selection=[9,4,1];
assert.equal(statuses(betPanel(reversed)).filter(s=>s==='的中').length,1,'unordered trio identity');
const incomplete=JSON.parse(JSON.stringify(swan));
incomplete.settlements=incomplete.settlements.filter(s=>s.bet_id!=='B08');
incomplete.performance.hit_bets=[];
assert.equal(statuses(betPanel(incomplete)).filter(s=>s==='結果不明').length,1,
  'genuinely unidentifiable ticket must not be guessed as a loss');
const duplicate=JSON.parse(JSON.stringify(swan));
duplicate.settlements.push({...duplicate.settlements[7],bet_id:'AMBIGUOUS'});
duplicate.performance.hit_bets=[];
assert.equal(statuses(betPanel(duplicate)).filter(s=>s==='結果不明').length,1,
  'ambiguous settlement identities must not be guessed');
const totalBets=checked.reduce((n,r)=>n+r.final_bets.length,0);
console.log('PASS_JRA_STAGING_RESULTS_SETTLEMENT: races='+checked.length+' bets='+totalBets
+' swan=1/24 win payout=9380 profit=6980; october=0/18; ordered/unordered/missing/ambiguous=PASS');
