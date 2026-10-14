/* v0.27 JRA traced turf plan – geometry shape, scale, continuity and future fields.
 * Data provenance: official JRA plane maps; no GPS/official surveyed path claim. */
'use strict';
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const W={};
for(const file of ['race-course-geometry-v1.js','race-lane-ai-v1.js','race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js'])
 vm.runInNewContext(fs.readFileSync('docs/staging/'+file,'utf8'),{window:W,globalThis:W});
for(const id of ['tokyo_turf_2000','kyoto_turf_outer_1400']){
 const c=W.RaceCourseGeometry.get(id);
 assert.ok(W.RaceCourseGeometry.validate(c));
 assert.match(c.sourcePlan.shapeMethod,/not surveyed GPS/);
 assert.match(c.sourcePlan.provider,/JRA/);
 const all=c.background.flatMap(s=>s[0]==='M'?[[s[1],s[2]]]:[[s[1],s[2]],[s[3],s[4]],[s[5],s[6]]]);
 const xs=all.map(x=>x[0]),ys=all.map(x=>x[1]);
 const width=Math.max(...xs)-Math.min(...xs),height=Math.max(...ys)-Math.min(...ys);
 const ratio=width/height;
 assert.ok(ratio>=2&&ratio<=2.6,'source traced courses are no longer squashed 3.3:1');
 assert.ok(c.mapUnitsPerMeter>.4&&c.mapUnitsPerMeter<.85,'real-world lane separation maps to drawing scale');
 const final=c.segments.at(-1);
 assert.ok(Math.abs(final.to-final.from-c.straight_m)<1e-5);
 for(const s of c.segments.slice(1)){
  for(const lane of [0,2,4,7]){
   const p=W.RaceCourseGeometry.point(c,s.from-.04,lane);
   const q=W.RaceCourseGeometry.point(c,s.from+.04,lane);
   assert.ok(Math.hypot(p.x-q.x,p.y-q.y)<.12,'continuous position at every landmark');
  }
 }
 let minMove=Infinity,maxMove=0,maxDirection=0;
 for(let d=1;d<=c.distance_m-2;d+=.5){
  const p=W.RaceCourseGeometry.point(c,d-.5,3);
  const q=W.RaceCourseGeometry.point(c,d+.5,3);
  const step=Math.hypot(p.x-q.x,p.y-q.y);
  minMove=Math.min(minMove,step);maxMove=Math.max(maxMove,step);
  const delta=Math.atan2(Math.sin(Math.atan2(p.ty,p.tx)-Math.atan2(q.ty,q.tx)),
   Math.cos(Math.atan2(p.ty,p.tx)-Math.atan2(q.ty,q.tx)));
  maxDirection=Math.max(maxDirection,Math.abs(delta));
  assert.ok(step>.18&&step<.90,'no sudden movement on official-map trace');
  assert.ok(Math.abs(delta)<.035,'no heading jerk');
 }
 const visual=W.RaceCourseGeometry.point(c,500,4),inner=W.RaceCourseGeometry.point(c,500,0);
 assert.ok(Math.hypot(visual.x-inner.x,visual.y-inner.y)<6.5,'physical lane width appears in proportion to track');
 console.log('PASS_V027_OFFICIAL_PLAN_TRACE',JSON.stringify({id,sourceAspect:+ratio.toFixed(3),
  minStep:+minMove.toFixed(3),maxStep:+maxMove.toFixed(3),maxTurn:+maxDirection.toFixed(5)}));
}
const html=fs.readFileSync('docs/staging/race-simulator.html','utf8');
assert.match(html,/value="sim" selected/);
assert.match(html,/Stage v0\.27/);
assert.match(html,/width="580" height="410"/);
assert.ok(!html.includes('id="paceSelect"')&&!html.includes('id="cameraSelect"'));
console.log('PASS_V027_STAGE_SHAPE_REGISTRATION_AND_DEFAULT');
