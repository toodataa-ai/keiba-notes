#!/usr/bin/env node
// Protect read-only JRA post-race presentation routing without modifying pre-race predictions.
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const read=p=>readFileSync(p,'utf8');
const db=JSON.parse(read('docs/data/races.json'));
const prod=read('docs/assets/results.js'),stage=read('docs/staging/assets/results.js');
const week=read('docs/assets/week.js');
const expected={
  '2026-10-12-october-stakes':{short:'tokyo11',stake:1800,payout:0,profit:-1800,win:false},
  '2026-10-12-swan-stakes':{short:'kyoto11',stake:2400,payout:9380,profit:6980,win:true}
};
const vmSource=(script,functions)=>{
  const header=script.split('(async()=>')[0];
  assert.notEqual(header,script,'expected async render tail');
  const c={};
  runInNewContext(header+'\n;globalThis.__functions={'+functions.join(',')+'};',c,{timeout:5000});
  return c.__functions;
};
const s=vmSource(stage,['jraReadableLinks','betPanel']);
const w=vmSource(week,['jraReadableLinks']);
assert(!prod.includes('JRA_V102_READABLE_REPORT_ALIASES'),
  'production must remain untouched until user approves the stage');
const preview=read('docs/staging/results.html');
assert(preview.includes('src="assets/results.js?v=20261013-settlement-v104"'),
  'production-mirror staging must not enable the unapproved lab-only renderer');
assert(!preview.includes('src="staging/assets/results.js'),
  'lab-only renderer should remain inert in staging');
assert(read('docs/results.html').includes('src="assets/results.js?v=20261013-settlement-v104"'));
const links=[];
for(const [id,perf] of Object.entries(expected)){
  const r=db.races.find(x=>x.id===id);
  assert(r && r.status==='reviewed' && r.purchase_strategy_version==='v3.15');
  assert.equal(r.performance.stake_yen,perf.stake);
  assert.equal(r.performance.payout_yen,perf.payout);
  assert.equal(r.performance.profit_yen,perf.profit);
  assert.equal(r.performance.ticket_hit,perf.win);
  assert.equal(r.final_bets.length,r.settlements.length);
  assert.equal(r.settlements.reduce((n,x)=>n+x.stake_yen,0),perf.stake);
  assert.equal(r.settlements.reduce((n,x)=>n+x.payout_yen,0),perf.payout);
  const newLinks=s.jraReadableLinks(r);
  const asPredicted={...r,status:'predicted'};
  assert.deepEqual(JSON.parse(JSON.stringify(newLinks)),
    JSON.parse(JSON.stringify(w.jraReadableLinks(asPredicted))),
    id+': must match existing officially approved week display aliases');
  assert.equal(r.report.includes('-readable-'),false,'sealed registry original not rewritten');
  assert.notEqual(r.report,newLinks.report);
  assert.notEqual(r.pdf,newLinks.pdf);
  const htmlFile='docs/'+newLinks.report,pdfFile='docs/'+newLinks.pdf;
  assert(existsSync(htmlFile) && existsSync(pdfFile),'approved readable HTML and PDF must exist');
  const html=read(htmlFile);
  assert(!html.includes('<strong>overall_grade</strong>'),'no raw model fields');
  assert(!html.includes('<strong>past_performances</strong>'),'no raw prior races');
  assert(html.includes('総合評価') && html.includes('①〜⑨ 評価内訳'),'Japanese grade grid and labels');
  assert.equal((html.match(/<section class="page horse-page">/g)||[]).length,r.field_size);
  const marks=[...html.matchAll(/<h1>\d+番[^<]+　([◎○▲△×])<\/h1>/g)].map(m=>m[1]);
  assert.equal(marks.length,r.field_size);
  assert.deepEqual(marks,[...marks].sort((a,b)=>'◎○▲△×'.indexOf(a)-'◎○▲△×'.indexOf(b)));
  const pdf=readFileSync(pdfFile);
  assert(pdf.length>10000 && pdf.subarray(0,5).toString()==='%PDF-');
  const stagePdf=readFileSync('docs/staging/jra-v315-20261012/'+perf.short+'.pdf');
  assert(pdf.equals(stagePdf),'readable public PDF must equal already-reviewed staging PDF bytes');
  // Guard against accidentally routing archived historical source to a different race.
  assert.deepEqual(JSON.parse(JSON.stringify(s.jraReadableLinks({...r,report:'reports/unknown.html'}))),
    {report:'reports/unknown.html',pdf:r.pdf});
  assert.deepEqual(JSON.parse(JSON.stringify(s.jraReadableLinks({...r,purchase_strategy_version:'v3.13'}))),
    {report:r.report,pdf:r.pdf});
  const panel=s.betPanel(r);
  assert(panel.includes('購入合計') && panel.includes('払戻合計'));
  assert(panel.includes(perf.stake.toLocaleString('ja-JP')+'円'));
  assert(panel.includes(perf.payout.toLocaleString('ja-JP')+'円'));
  assert(panel.includes(Math.abs(perf.profit).toLocaleString('ja-JP')+'円'));
  links.push({id,html:newLinks.report,pdf:newLinks.pdf,profit:perf.profit});
}
const other=db.races.find(x=>x.id==='2026-10-11-ireland-trophy');
assert(other);
assert.deepEqual(JSON.parse(JSON.stringify(s.jraReadableLinks(other))),
  {report:other.report,pdf:other.pdf},'unrelated race must not be redirected');
assert.equal((stage.match(/function ticketKey\(type,selection\)/g)||[]).length,1);
assert(stage.includes("const display=jraReadableLinks(r);"));
assert(stage.includes('${encodeURI(display.report)}'));
assert(stage.includes('${encodeURI(display.pdf)}'));
console.log('PASS_JRA_REVIEWED_PRESENTATION_LINKS_PAYOUT_UNCHANGED '+JSON.stringify(links));
