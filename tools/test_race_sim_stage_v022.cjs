/* v0.22 stage-only: 6 pre-race traits, lane discipline and continuous joins. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const W={};const root='docs/staging/';
for(const f of ['race-course-geometry-v1.js','race-lane-ai-v1.js','race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js'])
 vm.runInNewContext(fs.readFileSync(root+f,'utf8'),{window:W,globalThis:W},{filename:f});
vm.runInNewContext(fs.readFileSync(root+'race-umapot-overlay-v1.js','utf8').replace('setup();',''),{
 window:W,globalThis:W,document:{getElementById:()=>null,querySelector:()=>null}
});
const keys=['early','cruise','burst','sustain','stamina','acceleration'];
for(const id of ['tokyo_turf_2000','kyoto_turf_outer_1400']){
 const profile=W.RaceCourseGeometry.get(id),cfg=W.RaceLaneAI.config(profile);
 assert.ok(W.RaceUmapotOverlay.validate(profile),'mapped reference remains within frame');
 for(const boundary of profile.segments.slice(1)){
  for(const lane of [0,4,8]){
   for(const mapper of [W.RaceCourseGeometry.point,W.RaceUmapotOverlay.point]){
    const before=mapper(profile,boundary.from-.02,lane),after=mapper(profile,boundary.from+.02,lane);
    assert.ok(Math.hypot(after.x-before.x,after.y-before.y)<.12,
      'continuous sector joins '+id+' '+boundary.from);
   }
  }
  const before=W.RaceCourseGeometry.metrics(profile,boundary.from-.02,3);
  const after=W.RaceCourseGeometry.metrics(profile,boundary.from+.02,3);
  assert.ok(Math.abs(before.pathStretch-after.pathStretch)<.004,'no drag jump at landmark');
 }
 const straight=profile.segments.find(s=>s.kind==='straight'&&s.to-s.from>100);
 const startD=(straight.from+straight.to)/2;
 const h={number:99,d:startD,lane:3,desiredLane:3,lastChange:-100,finished:false};
 const ahead={number:100,d:startD+9,lane:3,finished:false};
 assert.equal(W.RaceLaneAI.plan(h,[h,ahead],cfg,
   W.RaceCourseGeometry.metrics(profile,startD,3),'neutral',50),null,
   'do not go 3 lanes outside 9m behind a horse in the first half');
 const lastD=profile.distance_m-55;
 const closer={...h,d:lastD,blocked:false},leader={...ahead,d:lastD+6};
 assert.equal(W.RaceLaneAI.plan(closer,[closer,leader],cfg,
   W.RaceCourseGeometry.metrics(profile,lastD,3),'neutral',130)?.mode,'outward',
   'overtaking remains allowed in the finishing straight');
 const field=['nige','senko','sashi','oikomi'].map((style,i)=>{
  const first=[1,3,8,12][i],styleMeta={
   source:'pre_race_report_last_run',field:18,first,last:first+2,style
  };
  const horse={number:i+1,name:'fixture'+i,mark:['◎','○','▲','△'][i],
   win_pct:25,style,styleMeta,factorGrades:['B','B','B','B','B','B','B','B',i%2?'A':'B'],recentRuns:[]};
  const ability=W.RaceSimAbility.profile(horse,{venue:profile.venue,distance_m:profile.distance_m},25);
  assert.deepEqual(Object.keys(ability.six),keys);
  assert.ok(Object.values(ability.six).every(x=>Number.isInteger(x)&&x>=0&&x<=100));
  return horse;
 });
 const sim=W.RaceSimEngine.create({id:'v022-'+id,course_id:id,
  venue:profile.venue,turn:profile.turn,distance_m:profile.distance_m,horses:field},{seed:2026});
 assert.ok(sim.state.horses.every(h=>keys.every(k=>Number.isInteger(h.six[k]))));
 let steps=0;while(!sim.state.finished&&steps++<2400)sim.step(.16);
 assert.ok(sim.state.finished,'all horse markers complete 32m runoff');
 console.log('PASS_V022_SIX_TRAITS_CONTINUOUS_COURSE_TACTICAL_LANES',profile.venue);
}
const html=fs.readFileSync(root+'race-simulator.html','utf8');
assert.ok(/Stage v0\.\d+/.test(html)&&html.includes('id="runnerSixTraits"'),
  'stage revision may advance while six-trait UI remains supported');
console.log('PASS_V022_STAGE_UI_NON_PRODUCTION');