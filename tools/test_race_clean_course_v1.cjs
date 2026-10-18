/* LAB original-photo broadcast + numbers-only gate; fixture horses only.
 * Source image is linked, not stored or raster-reconstructed in repository. */
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
assert.deepEqual(Array.from([course.jraDimensions.minTurfWidthM,course.jraDimensions.maxTurfWidthM]),[27,38]);
assert.equal(course.widthMetres,27);
assert.equal(course.widthMetres,27);
assert.equal(course.railKnotCount,60);
for(let d=0;d<=2000;d+=5){
 const r=course.rails(d);assert.ok(r.widthPx>17&&r.widthPx<39,'VARIABLE_WIDTH_'+d);
}
assert.equal(course.densePointCount,2001);
assert.equal(course.denseSpacingM,1);
for(let d=0;d<=2000;d+=.25){
 const pos=course.center(d),next=course.center(Math.min(2000,d+.25));
 assert.ok(Math.hypot(next.x-pos.x,next.y-pos.y)<.8,'SMOOTH_PATH_'+d);
 assert.ok(Math.hypot(next.tx-pos.tx,next.ty-pos.ty)<.06,'SMOOTH_TANGENT_'+d);
}
assert.deepEqual(Array.from(course.sections.filter(s=>s.kind==='straight').map(s=>[s.from,s.to])),
 [[0,308.7],[720,1270],[1671.6,2000]]);
// Faithful image registration: only actual uncurved straight cores are
// forced straight. Curve transitions start earlier in the source drawing.
for(const [from,to] of [[0,60],[1760,1990]]){
 const a=course.center(from+2),b=course.center((from+to)/2),c=course.center(to-2);
 assert.ok(Math.hypot(a.ty-b.ty,b.ty-c.ty)<.014,'STRAIGHT_CORE_CHANGED_'+from);
}
for(const join of [308.7,530,720,1270,1435,1671.6]){
 const a=course.center(join-.001),b=course.center(join+.001);
 assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<.012,'JOIN_POSITION_JUMP_'+join);
 assert.ok(Math.hypot(a.tx-b.tx,a.ty-b.ty)<.003,'JOIN_DIRECTION_JUMP_'+join);
}
const anchors=new Map([[0,[350,317.5]],[309,[210,309.3]],[530,[168.05,218.2]],
 [720,[225.25,163]],[1270,[463.95,116.9]],[1435,[529.95,214.4]],
 [1672,[489.6,312.7]],[2000,[294,317.5]]]);
for(const [d,c] of anchors){
 const p=course.center(d);
 assert.ok(Math.hypot(p.x-c[0],p.y-c[1])<1.8,'UMAPOT_ANCHOR_'+d);
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
assert.ok(html.includes('race-clean-course-v1.js?v=20261018-9'));
assert.ok(html.includes('race-clean-course-app-v1.js?v=20261018-9'));
assert.ok(html.includes('assets/kyoto-umapot-course-clean-v8.svg'));
const sourceSVG=fs.readFileSync(root+'assets/kyoto-umapot-course-clean-v8.svg','utf8');
assert.ok(sourceSVG.startsWith('<svg')&&sourceSVG.includes('width="620" height="430"'));
assert.ok(!sourceSVG.includes('<text'));
assert.ok(!html.includes('race-turf-corridor-v1.js'));
assert.ok(!app.includes('ctx.drawImage(original,0,0,targetWidth,targetHeight)'));
assert.ok(html.includes('id="liveCourseImage"'));
assert.ok(!html.includes('id="liveCourseHiRes"'));
assert.equal((html.match(/kyoto-umapot-course-clean-v8.svg/g)||[]).length,2);
assert.ok(app.includes('backdrop(lastCamera);'));
assert.ok(!app.includes('function track('));
assert.ok(!app.includes('track(live.ctx'));
assert.ok(!app.includes("ctx.lineTo(p.actual.x,p.actual.y)"));
assert.ok(app.includes('actualNumberCircles:true,paintedTrack:false,leaderLines:false'));
assert.ok(!app.includes('const IMAGE_SCALE=4'));
assert.ok(!app.includes('track(map.ctx,overview)'));
assert.ok(app.includes('Math.max(2.3,Math.min(w<540?8.2:9.6'));
assert.ok(app.includes('RaceSimEngine.create('));
assert.ok(app.includes('updateRunningOrder('));
assert.ok(!app.includes('placeReadableLabels('));
assert.ok(!app.includes('function roundedWaku('));
assert.ok(app.includes('raceNumberMarker(ctx,p.number,x,y,scale'));
assert.ok(app.includes('const radius=13.5*scale;'));
assert.ok(app.includes("ctx.strokeStyle=focused?'#e9af30':waku.border"));
assert.ok(!app.includes('radius+4.3*scale'));
assert.ok(!app.includes('focused?15.5:13.5'));
assert.ok(!app.includes('p.number===focused?(compact?'));
assert.ok(app.includes('markerRadiusSpreadPx:'));
assert.ok(app.includes('directMarkerMaxError:'));
assert.ok(app.includes('Math.abs(p.d-focus.d)<=80'));
assert.equal(typeof window.RaceLaneAI.plan,'function');
assert.equal(typeof window.RaceLaneAI.launchStepSafe,'function');
assert.ok(sim.state.totalInsideMoves>=8,'Kyoto 1400 shared engine must execute inward moves');
assert.ok(!app.includes('for(const s of W.sections)'));
assert.ok(html.includes('id="runningOrder"'));
assert.ok(app.includes('point(')||app.includes('model.runners('));
console.log('PASS_LAB_UNALTERED_PUBLISHER_CLEAN_SVG_AND_COMPACT_NUMBERS',samples);
console.log('PASS_LAB_CLEAN_COURSE_SHARED_KYOTO1400_LANE_ENGINE_18_HORSES',JSON.stringify(snapshots));
