/* Staging v0.23: one continuous racing line, no discontinuous checkpoints. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const W={},root='docs/staging/';
for(const f of ['race-course-geometry-v1.js','race-lane-ai-v1.js','race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js'])
 vm.runInNewContext(fs.readFileSync(root+f,'utf8'),{window:W,globalThis:W},{filename:f});
vm.runInNewContext(fs.readFileSync(root+'race-umapot-overlay-v1.js','utf8').replace('setup();',''),
 {window:W,globalThis:W,document:{getElementById:()=>null,querySelector:()=>null}});
for(const id of ['tokyo_turf_2000','kyoto_turf_outer_1400']){
 const c=W.RaceCourseGeometry.get(id);
 assert.ok(W.RaceUmapotOverlay.validate(c));
 assert.equal(typeof W.RaceCourseGeometry.continuousLine,'function');
 let maxJump=0,maxYaw=0,minRun=Infinity,maxRun=0,maxGrade=0;
 for(let d=1;d<c.distance_m-2;d+=.5){
  const p=W.RaceCourseGeometry.point(c,d-.5,6),q=W.RaceCourseGeometry.point(c,d+.5,6);
  const travel=Math.hypot(q.x-p.x,q.y-p.y);
  minRun=Math.min(minRun,travel);maxRun=Math.max(maxRun,travel);
  assert.ok(travel>.20&&travel<.85,'no whole-course positional jump');
  let angle=Math.atan2(p.ty,p.tx)-Math.atan2(q.ty,q.tx);
  angle=Math.abs(Math.atan2(Math.sin(angle),Math.cos(angle)));
  maxYaw=Math.max(maxYaw,angle);
  assert.ok(angle<.035,'no abrupt heading change at any metre');
  const a=W.RaceCourseGeometry.metrics(c,d-.5,6),b=W.RaceCourseGeometry.metrics(c,d+.5,6);
  const grade=Math.abs(a.grade-b.grade);maxGrade=Math.max(maxGrade,grade);
  assert.ok(grade<.006,'no one-frame grade impulse');
 }
 for(const segment of c.segments.slice(1))for(const lane of [0,6,8]){
  const a=W.RaceCourseGeometry.point(c,segment.from-.04,lane);
  const b=W.RaceCourseGeometry.point(c,segment.from+.04,lane);
  const x=W.RaceUmapotOverlay.point(c,segment.from-.04,lane);
  const y=W.RaceUmapotOverlay.point(c,segment.from+.04,lane);
  const g=Math.hypot(a.x-b.x,a.y-b.y),ov=Math.hypot(x.x-y.x,x.y-y.y);
  maxJump=Math.max(maxJump,g,ov);
  assert.ok(g<.11&&ov<.11,'main and reference maps continuous at every join');
 }
 const end=c.distance_m,from=W.RaceCourseGeometry.point(c,end,4),through=W.RaceCourseGeometry.point(c,end+32,4);
 assert.ok(Math.hypot(from.x-through.x,from.y-through.y)>6,'continuous finish/runoff');
 console.log('PASS_V023_GLOBAL_SPLINE',id,JSON.stringify({
  maxBoundaryTravel:+maxJump.toFixed(4),maxYawRad:+maxYaw.toFixed(5),
  perMetreTravelRange:[+minRun.toFixed(3),+maxRun.toFixed(3)],
  maxGradeChange:+maxGrade.toFixed(5)}));
}
const page=fs.readFileSync(root+'race-simulator.html','utf8');
assert.ok(/Stage v0\.\d+/.test(page)&&page.includes('一本の連続スプライン'));
console.log('PASS_V023_STAGE_ONLY_CHECKPOINTS');