/* Stage v0.21: deterministic pre-race real-report simulation and goal view. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const W={},root='docs/staging/';
for(const file of ['race-course-geometry-v1.js','race-lane-ai-v1.js','race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js'])
 vm.runInNewContext(fs.readFileSync(root+file,'utf8'),{window:W,globalThis:W},{filename:file});
const txt=s=>String(s||'').replace(/<[^>]*>/g,'').trim();
function load(file){
 const blocks=[...fs.readFileSync(file,'utf8').matchAll(/<section class="page horse-page">([\s\S]*?)<\/section>/g)].map(x=>x[1]);
 assert.equal(blocks.length,18);
 return blocks.map(q=>{
  const m=txt((q.match(/<h1>(.*?)<\/h1>/)||[])[1]).match(/^(\d+)番\s+(.+?)\s+([◎○▲△×])$/);
  assert.ok(m);
  const g=[...(q.match(/<table class="factor-grid">([\s\S]*?)<\/table>/)||[])[1].matchAll(/class="grade [^"]*">([^<]*)<\/span>/g)].map(x=>x[1]);
  assert.equal(g.length,9);
  const meta=W.RaceRunnerStyle.inferFromLastRace(txt((q.match(/<p class="assessment">([\s\S]*?)<\/p>/)||[])[1]));
  const tbody=(q.match(/<table class="run-table">([\s\S]*?)<\/table>/)||[])[1]||'';
  const recentRuns=[...tbody.matchAll(/<tr>([\s\S]*?)<\/tr>/g)]
   .map(z=>[...z[1].matchAll(/<td>([\s\S]*?)<\/td>/g)].map(v=>txt(v[1])))
   .filter(a=>a.length===5).slice(0,4).map(a=>({date:a[0],venue:a[1],distance_m:Number((a[2].match(/芝(\d+)m/)||[])[1])||null,finish:Number((a[3].match(/(\d+)着/)||[])[1])||null}));
  const pct=(q.match(/モデル単勝確率[:：]\s*([\d.]+)%/)||[])[1];assert.ok(pct);
  return {number:Number(m[1]),name:m[2],mark:m[3],grade:txt((q.match(/class="horse-score"[\s\S]*?class="grade [^"]*">([^<]*)<\/span>/)||[])[1]),factorGrades:g,pace_grade:g[1],win_pct:Number(pct),style:meta.style,styleMeta:meta,recentRuns};
 });
}
function trial(course,field,seed){
 const p=W.RaceCourseGeometry.get(course),sim=W.RaceSimEngine.create({id:'v021-'+course,venue:p.venue,turn:p.turn,course_id:course,distance_m:p.distance_m,horses:field},{seed,pace:'auto',bias:'neutral'});
 let n=0;
 while(!sim.state.finished&&n++<2600)sim.step(.16);
 assert.ok(sim.state.finished&&sim.state.straightEntryOrder?.length===18,'all finish');
 assert.ok(sim.state.horses.every(x=>x.finished&&x.displayD>=p.distance_m+31.99),'32m runoff');
 assert.ok(sim.state.horses.every(x=>x.lane>=0&&x.lane<=sim.laneConfig.maxLane),'stays on track');
 assert.ok(sim.state.firstFinishTime>p.distance_m/18.2&&sim.state.firstFinishTime<p.distance_m/15.7,'duration');
 return sim;
}
for(const [course,file] of [
 ['tokyo_turf_2000','docs/reports/2026-10-12-october-stakes-v315-readable-v103.html'],
 ['kyoto_turf_outer_1400','docs/reports/2026-10-12-swan-stakes-v315-readable-v103.html']
]){
 const p=W.RaceCourseGeometry.get(course),field=load(file),wins={},gains=[];
 for(let seed=1;seed<=20;seed++){
  const a=trial(course,field,seed),b=trial(course,field,seed);
  assert.deepEqual(a.standings().map(x=>x.finishTime),b.standings().map(x=>x.finishTime),'same seed same order');
  wins[a.standings()[0].style]=(wins[a.standings()[0].style]||0)+1;
  const entry=new Map(a.state.straightEntryOrder.map((no,i)=>[no,i]));
  gains.push(Math.max(...a.standings().map((x,i)=>entry.get(x.number)-i)));
 }
 assert.ok(Object.keys(wins).length>=2,'no runaway win monopoly');
 assert.ok(Math.max(...gains)>=4,'overtake several positions on straight');
 console.log('PASS_STAGE_V021',p.venue,JSON.stringify({wins,maxGain:Math.max(...gains)}));
}
const goalSource=fs.readFileSync(root+'race-simulator.js','utf8').match(/function goalScreenPosition\([^]*?\n\}/);
assert.ok(goalSource);const goal=vm.runInNewContext(goalSource[0]+';goalScreenPosition');
for(const turn of ['左','右']){
 const origin=goal(1000,2,1000,1000,470,10,turn),behind=goal(820,2,1000,1000,470,10,turn);
 assert.ok(behind.x>0&&behind.x<1000,'rear horse shown near goal');
 assert.equal(Math.sign(goal(1001,2,1000,1000,470,10,turn).x-origin.x),turn==='右'?-1:1);
}
console.log('PASS_STAGE_V021_GOAL_DIRECTION_AND_VISIBILITY');