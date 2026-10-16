/* Stage v0.36: real crossing-time gaps, no finish-line convergence and
 * no visual inversion during post-line runoff. Pre-race reports only.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root='docs/staging/',W={};
const courseCanvas={hidden:false,getContext:()=>({clearRect:()=>{}})};
const document={getElementById:id=>id==='tokyoCourseOverlay'||id==='kyotoCourseOverlay'?courseCanvas:null,
 querySelector:()=>null};
for(const name of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js',
 'race-umapot-overlay-v1.js']){
 vm.runInNewContext(fs.readFileSync(root+name,'utf8').replace('setup();',''),
  {window:W,globalThis:W,document});
}
const txt=s=>String(s||'').replace(/<[^>]*>/g,'').trim();
function load(file){
 const entries=[...fs.readFileSync(file,'utf8').matchAll(/<section class="page horse-page">([\s\S]*?)<\/section>/g)].map(x=>x[1]);
 assert.equal(entries.length,18);
 return entries.map(q=>{
  const m=txt((q.match(/<h1>(.*?)<\/h1>/)||[])[1]).match(/^(\d+)番\s+(.+?)\s+([◎○▲△×])$/);
  assert.ok(m);
  const grades=[...(q.match(/<table class="factor-grid">([\s\S]*?)<\/table>/)||[])[1]
   .matchAll(/class="grade [^"]*">([^<]*)<\/span>/g)].map(x=>x[1]);
  assert.equal(grades.length,9);
  const meta=W.RaceRunnerStyle.inferFromLastRace(txt((q.match(/<p class="assessment">([\s\S]*?)<\/p>/)||[])[1]));
  const runTable=(q.match(/<table class="run-table">([\s\S]*?)<\/table>/)||[])[1]||'';
  const recentRuns=[...runTable.matchAll(/<tr>([\s\S]*?)<\/tr>/g)]
   .map(z=>[...z[1].matchAll(/<td>([\s\S]*?)<\/td>/g)].map(v=>txt(v[1])))
   .filter(a=>a.length===5).slice(0,4)
   .map(a=>({date:a[0],venue:a[1],distance_m:Number((a[2].match(/芝(\d+)m/)||[])[1])||null,
     finish:Number((a[3].match(/(\d+)着/)||[])[1])||null}));
  const win=(q.match(/モデル単勝確率[:：]\s*([\d.]+)%/)||[])[1];assert.ok(win);
  return {number:Number(m[1]),name:m[2],mark:m[3],
    grade:txt((q.match(/class="horse-score"[\s\S]*?class="grade [^"]*">([^<]*)<\/span>/)||[])[1]),
    pace_grade:grades[1],factorGrades:grades,recentRuns,
    win_pct:Number(win),style:meta.style,styleMeta:meta};
 });
}
let checked=0,maxGap=0;
for(const [courseID,raceID,file] of [
 ['tokyo_turf_2000','2026-10-12-october-stakes','docs/reports/2026-10-12-october-stakes-v315-readable-v103.html'],
 ['kyoto_turf_outer_1400','2026-10-12-swan-stakes','docs/reports/2026-10-12-swan-stakes-v315-readable-v103.html']
]){
 const profile=W.RaceCourseGeometry.get(courseID),field=load(file);
 const race={id:raceID,course_id:courseID,venue:profile.venue,turn:profile.turn,
   distance_m:profile.distance_m,field_size:field.length,horses:field};
 for(const seed of [1,2,3,4,11,18,31,38,46,77,2026]){
  const sim=W.RaceSimEngine.create(race,{seed,pace:'auto',bias:'neutral'});
  let ticks=0;
  while(!sim.state.finished && ticks++<3000)sim.step(.1);
  assert.ok(sim.state.finished,'all horses finish and run 32m beyond');
  const all=sim.standings();
  assert.equal(all.length,18);
  assert.ok(all.every(h=>h.finished&&Number.isFinite(h.finishTime)&&h.displayD>=profile.distance_m+32));
  assert.ok(Math.abs(sim.state.firstFinishTime-all[0].finishTime)<1e-9,
   'winner clock equals earliest interpolated crossing time');
  for(let i=1;i<all.length;i++){
   assert.ok(all[i].finishTime>=all[i-1].finishTime,'rank matches exact finish time');
   assert.ok(all[i].displayD<=all[i-1].displayD+1e-7,
     'no fake finish-line tie or inversion after the line');
   const dt=all[i].finishTime-all[i-1].finishTime;
   if(dt>.12)assert.ok(all[i-1].displayD-all[i].displayD>.6,
     'time gap must remain spatially visible');
  }
  const gap=all[1].finishTime-all[0].finishTime;
  assert.ok(gap>=0&&gap<2,'stage ordinary 2000/1400m frontrunner gap plausibility');
  maxGap=Math.max(maxGap,gap);
  if(seed===2026){
   const painted=[];
   W.RaceUmapotOverlay.draw(sim.state,race,'leader',false,(_,no)=>painted.push(no));
   const visible=all.filter(h=>h.displayD<=profile.distance_m+40);
   assert.equal(painted.length,visible.length,'do not stack off-map winners at finish');
   assert.ok(visible.length<18,'fast finishers exit the official drawing');
   for(const h of visible)assert.ok(painted.includes(h.number));
  }
  checked++;
 }
}
const html=fs.readFileSync(root+'race-simulator.html','utf8');
assert.ok(html.includes('race-sim-engine.js?v=20261016-38'));
assert.ok(html.includes('race-umapot-overlay-v1.js?v=20261015-37'));
assert.ok(html.includes('Finish spacing v0.36'));
assert.ok(html.includes('全馬が最低32m駆け抜け'));
console.log('PASS_V036_FINISH_GAP_SPACING_AND_NO_OVERTAKE',checked,'scenarios, max second-place gap',maxGap.toFixed(2));
