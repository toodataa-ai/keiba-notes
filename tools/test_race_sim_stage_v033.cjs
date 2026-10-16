/* Stage v0.33: Tokyo 2000m race duration and sectional-time coherence.
 * Only sealed pre-race inputs are loaded. Neither official finishing order
 * nor post-race winning time is used as a simulation target.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const base='docs/staging/',W={};
for(const name of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js']){
 vm.runInNewContext(fs.readFileSync(base+name,'utf8'),{window:W,globalThis:W});
}
const geo=W.RaceCourseGeometry,eng=W.RaceSimEngine;
const tokyo=geo.get('tokyo_turf_2000'),kyoto=geo.get('kyoto_turf_outer_1400');
assert.ok(eng.sectionalSpeedAdjustment(tokyo,0)<-1);
assert.ok(eng.sectionalSpeedAdjustment(tokyo,2000)>0);
assert.equal(eng.sectionalSpeedAdjustment(kyoto,0),0);
assert.equal(eng.sectionalSpeedAdjustment(kyoto,700),0);
assert.equal(eng.classifySplitPace(tokyo,55.3),'H');
assert.equal(eng.classifySplitPace(tokyo,59.2),'S');
assert.equal(eng.classifySplitPace(kyoto,34.8),'M');
assert.equal(eng.classifySplitPace(tokyo,null),null);
const txt=s=>String(s||'').replace(/<[^>]*>/g,'').trim();
function load(file){
 const blocks=[...fs.readFileSync(file,'utf8').matchAll(/<section class="page horse-page">([\s\S]*?)<\/section>/g)].map(x=>x[1]);
 assert.equal(blocks.length,18,'complete pre-race field');
 return blocks.map(q=>{
  const m=txt((q.match(/<h1>(.*?)<\/h1>/)||[])[1]).match(/^(\d+)番\s+(.+?)\s+([◎○▲△×])$/);
  assert.ok(m);
  const grades=[...(q.match(/<table class="factor-grid">([\s\S]*?)<\/table>/)||[])[1]
    .matchAll(/class="grade [^"]*">([^<]*)<\/span>/g)].map(x=>x[1]);
  assert.equal(grades.length,9);
  const meta=W.RaceRunnerStyle.inferFromLastRace(txt(
    (q.match(/<p class="assessment">([\s\S]*?)<\/p>/)||[])[1]));
  const rows=(q.match(/<table class="run-table">([\s\S]*?)<\/table>/)||[])[1]||'';
  const recentRuns=[...rows.matchAll(/<tr>([\s\S]*?)<\/tr>/g)]
   .map(z=>[...z[1].matchAll(/<td>([\s\S]*?)<\/td>/g)].map(v=>txt(v[1])))
   .filter(a=>a.length===5).slice(0,4).map(a=>({date:a[0],venue:a[1],
    distance_m:Number((a[2].match(/芝(\d+)m/)||[])[1])||null,
    finish:Number((a[3].match(/(\d+)着/)||[])[1])||null}));
  const pct=(q.match(/モデル単勝確率[:：]\s*([\d.]+)%/)||[])[1];
  assert.ok(pct);
  return {number:Number(m[1]),name:m[2],mark:m[3],
   grade:txt((q.match(/class="horse-score"[\s\S]*?class="grade [^"]*">([^<]*)<\/span>/)||[])[1]),
   factorGrades:grades,pace_grade:grades[1],win_pct:Number(pct),
   style:meta.style,styleMeta:meta,recentRuns};
 });
}
function run(course,raceID,horses,seed){
 const sim=eng.create({id:raceID,venue:course.venue,turn:course.turn,
  course_id:course.id,distance_m:course.distance_m,horses},{seed,pace:'auto',bias:'neutral'});
 let steps=0;
 while(!sim.state.finished&&steps++<3000)sim.step(.1);
 assert.ok(sim.state.finished,'race and runoff finish');
 assert.ok(sim.state.splitTime>0&&sim.state.firstFinishTime>sim.state.splitTime);
 assert.equal(sim.state.splitPaceBand,eng.classifySplitPace(course,sim.state.splitTime));
 assert.ok(sim.state.horses.every(x=>x.finished&&x.finishTime>0));
 return sim.state;
}
const tokyoRunners=load('docs/reports/2026-10-12-october-stakes-v315-readable-v103.html');
for(const seed of [18,31,77,2026]){
 const state=run(tokyo,'2026-10-12-october-stakes',tokyoRunners,seed);
 // Broad historical-scale sanity ranges, NOT matching the known race result:
 // 1000m must not recur at 55.3s under an ordinary turf 2000m scenario.
 assert.ok(state.splitTime>=58&&state.splitTime<61,
  'TOKYO_2000_UNREALISTIC_1000M '+state.splitTime);
 assert.ok(state.firstFinishTime>=117&&state.firstFinishTime<122,
  'TOKYO_2000_UNREALISTIC_FINISH '+state.firstFinishTime);
 console.log('TOKYO_STAGE_TIMING',seed,state.splitTime.toFixed(2),state.firstFinishTime.toFixed(2));
}
const kyotoRunners=load('docs/reports/2026-10-12-swan-stakes-v315-readable-v103.html');
const kyotoState=run(kyoto,'2026-10-12-swan-stakes',kyotoRunners,2026);
assert.ok(kyotoState.firstFinishTime>=79&&kyotoState.firstFinishTime<84,
 'KYOTO_UNINTENDED_PACE_CHANGE');
const html=fs.readFileSync(base+'race-simulator.html','utf8');
const css=fs.readFileSync(base+'race-simulator.css','utf8');
const ui=fs.readFileSync(base+'race-simulator.js','utf8');
assert.ok(html.includes('race-sim-engine.js?v=20261016-38'));
assert.ok(html.includes('race-simulator.js?v=20261016-39'));
assert.ok(html.includes('race-simulator.css?v=20261016-34'));
assert.ok(css.includes('#elapsed{font-size:clamp(18px,2.8vw,25px)'));
assert.ok(css.includes('@media(max-width:500px){#elapsed{font-size:18px'));
assert.ok(ui.includes('通過時計ペース ')&&ui.includes('state.splitPaceBand'));
assert.ok(ui.includes('序盤の競り合い最大'));
console.log('PASS_V033_TOKYO_2000_SPEED_AND_SECTIONAL_PACE_AND_MOBILE_CLOCK');
