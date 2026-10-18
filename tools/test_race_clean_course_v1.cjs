/* Independent LAB clean vector course gate — no JPEG, no image-derived
 * green stripe, no official prediction mutation, 18 synthetic horses only. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root='docs/lab/',window={},scripts=[
'race-course-geometry-v1.js','race-lane-ai-v1.js','race-runner-style-v1.js',
'race-ability-model-v1.js','race-sim-engine.js','race-lab-18-fixture-v1.js',
'race-clean-course-v1.js'];
for(const file of scripts)vm.runInNewContext(fs.readFileSync(root+file,'utf8'),
 {window,globalThis:window},{filename:file});
const course=window.RaceCleanCourse;
assert.equal(course.validate(),true);
assert.equal(course.distance,2000);
assert.equal(course.sections.length,7);
assert.equal(course.jraDimensions.homeStraightA,328.4);
assert.equal(course.jraDimensions.lapInnerA,1782.8);
assert.equal(course.jraDimensions.firstTurnDistanceM,308.7);
assert.deepEqual(Array.from([course.jraDimensions.minTurfWidthM,course.jraDimensions.maxTurfWidthM]),[24,38]);
assert.deepEqual(Array.from(course.sections.filter(s=>s.kind==='straight').map(s=>[s.from,s.to])),
 [[0,308.7],[720,1270],[1671.6,2000]]);
// Exact geometry invariants: straight headings cannot vary with distance.
for(const s of course.sections.filter(s=>s.kind==='straight')){
 const a=course.center(s.from+0.1),b=course.center((s.from+s.to)/2),c=course.center(s.to-0.1);
 assert.ok(Math.hypot(a.tx-b.tx,a.ty-b.ty)<1e-9,'STRAIGHT_ANGLE_CHANGED_'+s.from);
 assert.ok(Math.hypot(c.tx-b.tx,c.ty-b.ty)<1e-9,'STRAIGHT_ANGLE_CHANGED_'+s.to);
 const v={x:c.x-a.x,y:c.y-a.y};
 const cross=(b.x-a.x)*v.y-(b.y-a.y)*v.x;
 assert.ok(Math.abs(cross)<.001,'STRAIGHT_CROOKED_'+s.name);
}
for(const join of [308.7,530,720,1270,1435,1671.6]){
 const a=course.center(join-.001),b=course.center(join+.001);
 assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<.012,'JOIN_POSITION_JUMP_'+join);
 assert.ok(Math.hypot(a.tx-b.tx,a.ty-b.ty)<.003,'JOIN_DIRECTION_JUMP_'+join);
}
const anchors=new Map([[0,[350,317]],[308.7,[178,303]],[530,[165,203]],
 [720,[208,161]],[1270,[463,136]],[1435,[510,197]],
 [1671.6,[490,317]],[2000,[294,317]]]);
for(const [d,c] of anchors){
 const p=course.center(d);
 assert.ok(Math.hypot(p.x-c[0],p.y-c[1])<1e-4,'UMAPOT_ANCHOR_'+d);
}
const horses=window.RaceLab18Fixture.horses(),entry=window.RaceLab18Fixture.entry();
const sim=window.RaceSimEngine.create({...entry,horses},{seed:2026,bias:'neutral'});
assert.equal(sim.state.horses.length,18);
const other=window.RaceSimEngine.create({...entry,horses:window.RaceLab18Fixture.horses(),
 id:'lab-outer-1400-comparison',course_id:'kyoto_turf_outer_1400',distance_m:1400},
 {seed:2026,bias:'neutral'});
assert.equal(sim.state.laneModel,other.state.laneModel);
assert.equal(sim.laneConfig.packMaxLane,other.laneConfig.packMaxLane);
let worstOffset=0,insideRatio=0,samples=0;
for(let d=0;d<=2000;d+=5){
 const rails=course.rails(d);
 for(let lane=0;lane<=14;lane+=2){
  const p=course.point(d,lane),ratio=course.fraction(lane);
  const projected={x:rails.inner.x+(rails.outer.x-rails.inner.x)*ratio,
   y:rails.inner.y+(rails.outer.y-rails.inner.y)*ratio};
  worstOffset=Math.max(worstOffset,Math.hypot(p.x-projected.x,p.y-projected.y));
  assert.ok(ratio>0&&ratio<1,'lane must be inside turf band');
  samples++;
 }
}
assert.ok(worstOffset<1e-8);
const targets=[0,100,310,530,900,1270,1672,1900,2000],snapshots=[];let target=0;
for(let i=0;i<1600&&!sim.state.finished;i++){
 if(sim.state.leader>=targets[target]){
  const points=course.runners(sim.state);
  assert.equal(points.length,18,'all 18 exact coordinates in both views');
  assert.ok(points.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
  snapshots.push({d:targets[target],in4:sim.state.horses.filter(h=>h.lane<=3.45).length,
    leader:sim.state.leadingNo});
  target++;if(target>=targets.length)break;
 }
 sim.step(.12);
}
assert.equal(snapshots.length,targets.length,'all race sections tested');
assert.ok(snapshots.find(x=>x.d===100).in4>=8,'inner convergence by 100m');
assert.ok(snapshots.find(x=>x.d===310).in4>=8,'inside remains preferred');
const html=fs.readFileSync(root+'race-clean-course-v1.html','utf8');
const app=fs.readFileSync(root+'race-clean-course-app-v1.js','utf8');
assert.ok(html.includes('race-clean-course-v1.js?v=20261018-2'));
assert.ok(html.includes('race-clean-course-app-v1.js?v=20261018-2'));
assert.ok(html.includes('umapot.com/data/powerpoint/kyoto_couse/kyoto_couse_1.jpg'));
assert.ok(!html.includes('race-turf-corridor-v1.js'));
assert.ok(!app.includes('drawImage('));
assert.ok(!app.includes('track(map.ctx,overview)'));
assert.ok(app.includes('Math.max(3.4,Math.min(7.2'));
assert.ok(app.includes('RaceSimEngine.create('));
assert.ok(app.includes('point(')||app.includes('model.runners('));
console.log('PASS_LAB_CLEAN_COURSE_STRICT_STRAIGHTS_C1_CURVES_AND_TURF_BAND',samples);
console.log('PASS_LAB_CLEAN_COURSE_SHARED_KYOTO1400_LANE_ENGINE_18_HORSES',JSON.stringify(snapshots));
