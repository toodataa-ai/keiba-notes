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
// Correction audit: Kyoto1400/2000 must share physics; log *actual*
// physical longitudinal spread rather than diagnose apparent SVG clumping
// from screen pixels. This does not change the common engine or odds.
const physical=window.RaceSimEngine.create(
 {...entry,horses:window.RaceLab18Fixture.horses()},
 {seed:2026,bias:'neutral'});
const physicalDistances=[100,200,300,400,500,600,700,800,900,1000,
 1100,1200,1300,1400,1500,1600,1700,1800,1900],physicalPacks=[];
let bucket=0;
for(let i=0;i<2000&&bucket<physicalDistances.length&&!physical.state.finished;i++){
 if(physical.state.leader>=physicalDistances[bucket]){
  const sorted=physical.state.horses.slice().sort((a,b)=>b.d-a.d);
  const front=sorted.slice(0,Math.min(5,sorted.length));
  const maxD=sorted[0].d,minD=sorted.at(-1).d;
  physicalPacks.push({
    d:physicalDistances[bucket],
    simClock:Number(physical.state.t.toFixed(1)),
    actualFullPackGapM:Number((maxD-minD).toFixed(1)),
    within10m:sorted.filter(h=>maxD-h.d<=10).length,
    frontMeanEffortDebt:Number((front.reduce((a,h)=>a+h.effortDebt,0)/front.length).toFixed(3)),
    frontMeanFatigue:Number((front.reduce((a,h)=>a+h.fatigue,0)/front.length).toFixed(3)),
    pacePressure:Number(physical.state.pacePressure.toFixed(3))
  });
  bucket++;continue;
 }
 physical.step(.12);
}
assert.equal(physicalPacks.length,physicalDistances.length);
const contractions=physicalPacks.slice(1).map((p,i)=>({
 from:physicalPacks[i].d,to:p.d,
 contractM:Number((physicalPacks[i].actualFullPackGapM-p.actualFullPackGapM).toFixed(1)),
 fromGapM:physicalPacks[i].actualFullPackGapM,toGapM:p.actualFullPackGapM
})).sort((a,b)=>b.contractM-a.contractM);
console.log('KYOTO1400_SHARED_PHYSICAL_PACK_GAPS',JSON.stringify(physicalPacks));
console.log('TOP_PHYSICAL_CONTRACTIONS_100M',JSON.stringify(contractions.slice(0,5)));
assert.ok(physicalPacks.every(x=>Number.isFinite(x.actualFullPackGapM)));
const html=fs.readFileSync(root+'race-clean-course-v1.html','utf8');
const app=fs.readFileSync(root+'race-clean-course-app-v1.js','utf8');
assert.ok(html.includes('race-clean-course-v1.js?v=20261018-14'));
assert.ok(html.includes('race-clean-course-app-v1.js?v=20261019-21'));
assert.ok(html.includes('race-clean-goal-view-v1.js?v=20261019-20'));
assert.ok(app.includes('const scale=mini?.48:(points.length>=12?(compact?.78:.84):.90)'));
assert.ok(app.includes('const paintCamera=pixelAlignedCamera(lastCamera,live.ctx)'));
assert.ok(app.includes('backdrop(paintCamera)'));
assert.ok(app.includes('...paintCamera,w:live.w,h:live.h'));
assert.ok(app.includes('visualLaneState.set(h.number,{d:smoothD,lane:smoothLane})'));
assert.ok(app.includes('alongBlend=1-Math.exp(-dt/.070)'));
assert.ok(app.includes('laneBlend=1-Math.exp(-dt/.21)'));
assert.ok(app.includes('const blend=1-Math.exp(-dt/.20)'));
assert.ok(!app.includes('previous+(desiredLane-previous)*alpha'));

assert.ok(html.includes('race-clean-curve-camera-v1.js?v=20261019-19'));
assert.ok(!html.includes('race-clean-distance-camera-v1.js'));
assert.ok(!html.includes('id="distanceCamera"'));
const curveSrc=fs.readFileSync(root+'race-clean-curve-camera-v1.js','utf8');
assert.ok(curveSrc.includes("imageUnmodified:true,physicsUnmodified:true"));
assert.ok(curveSrc.includes("publisher-svg-uniform-affine-only"));
assert.ok(curveSrc.includes('smoothingRadiusM:RADIUS'));
assert.ok(curveSrc.includes('MAX_GAIN=1.45'));
assert.ok(app.includes('cameraLensGain:'));
assert.ok(app.includes("CURVE_LENS_ENABLED=new URLSearchParams(location.search).get('lens')!=='off'"));
assert.ok(app.includes('lastCamera.scale+(target.scale-lastCamera.scale)*blend'));
assert.ok(app.includes('Math.min(2000,leaderDistance-10)'));
assert.ok(app.includes('unchangedBackgroundAffineOnly:true'));
assert.ok(html.includes('race-course-image-geometry-v1.js?v=20261019-21'));
const sharedSource=fs.readFileSync(root+'race-course-image-geometry-v1.js','utf8');
assert.ok(sharedSource.includes('courseSpecificSlopeOverrides:0'));
assert.ok(sharedSource.includes('globalOptimizationPasses:optimizationPasses'));
assert.ok(sharedSource.includes('immutableSharedEngine:true'));
assert.ok(!sharedSource.includes('1270'));
assert.ok(!sharedSource.includes('kyoto'));
assert.ok(!sharedSource.includes('tokyo'));
assert.ok(app.includes("get('geometry')!=='legacy'"));


assert.ok(!app.includes('RaceCleanDistanceCamera'));
assert.ok(!app.includes('ctx.drawImage('));
assert.ok(html.includes('race-clean-goal-view-v1.js?v=20261019-20'));
assert.ok(html.includes('id="goalCamera"'));
const kyoto1400=fs.readFileSync(root+'race-simulator.html','utf8');
assert.ok(kyoto1400.includes('race-sim-engine.js?v=20261016-41'));
assert.ok(html.includes('race-sim-engine.js?v=20261016-41'));
assert.ok(kyoto1400.includes('race-lane-ai-v1.js?v=20261015-25'));
assert.ok(html.includes('race-lane-ai-v1.js?v=20261015-25'));
const goal=fs.readFileSync(root+'race-clean-goal-view-v1.js','utf8');
assert.ok(goal.includes('const scale=.81,rad=13.5*scale'));
assert.ok(goal.includes("turn==='右'?-1:1"));
assert.ok(goal.includes('drawGoalPost('));
assert.ok(goal.includes('function laneStep('));
assert.ok(goal.includes('step=laneStep(height,maxLane)/pullback;'));
assert.ok(goal.includes("mode:'kyoto1400-goal-camera'"));
assert.ok(app.includes('state.goalCamera||state.firstFinishTime!==null'));
assert.ok(app.includes('goalCameraSwitchDistance:1920'));
assert.ok(app.includes("scale:(w<540?8.8:9.7)*"));
assert.ok(html.includes('assets/kyoto-umapot-course-clean-v8.svg'));
const sourceSVG=fs.readFileSync(root+'assets/kyoto-umapot-course-clean-v8.svg','utf8');
assert.ok(sourceSVG.startsWith('<svg')&&sourceSVG.includes('width="620" height="430"'));
assert.ok(!sourceSVG.includes('<text'));
assert.ok(!html.includes('race-turf-corridor-v1.js'));
assert.ok(!app.includes('ctx.drawImage(original,0,0,targetWidth,targetHeight)'));
assert.ok(html.includes('id="liveCourseImage"'));
assert.ok(!html.includes('id="liveCourseHiRes"'));
assert.equal((html.match(/kyoto-umapot-course-clean-v8.svg/g)||[]).length,2);
assert.ok(app.includes('backdrop(paintCamera);'));
assert.ok(!app.includes('function track('));
assert.ok(!app.includes('track(live.ctx'));
assert.ok(!app.includes("ctx.lineTo(p.actual.x,p.actual.y)"));
assert.ok(app.includes('actualNumberCircles:true,paintedTrack:false,leaderLines:false'));
assert.ok(!app.includes('const IMAGE_SCALE=4'));
assert.ok(!app.includes('track(map.ctx,overview)'));
assert.ok(app.includes("scale:(w<540?8.8:9.7)*"));
assert.ok(app.includes('RaceSimEngine.create('));
assert.ok(html.includes('race-clean-turf-mask-v1.js?v=20261019-21'));
const surface=fs.readFileSync(root+'race-clean-turf-mask-v1.js','utf8');
assert.ok(surface.includes('activateSharedGeometry'));
assert.ok(surface.includes('greenPixels++'));
assert.ok(!surface.includes('image.naturalWidth!==W'));
assert.ok(surface.includes('image.naturalWidth<=0'));
assert.ok(app.includes('function sourceImageReady('));
assert.ok(app.includes('sourceLoaded=sourceImageReady(a)'));
assert.ok(app.includes('broadcastLoaded=sourceImageReady(b)'));
assert.ok(!app.includes('a.naturalWidth===620'));
assert.ok(!app.includes('image?.naturalWidth===620'));

assert.ok(surface.includes('MIN_INNER_OFFSET=1.60'));
assert.ok(surface.includes('CLEARANCE=1.95'));
assert.ok(surface.includes('hiddenRailBridges:gaps'));
assert.ok(surface.includes('function trace('));
assert.ok(surface.includes('MAX_SPAN=17.5'));
assert.ok(surface.includes('const ARC_ANCHORS=Object.freeze([0,308.7,530,720,1270,1435,1671.6,2000])'));
assert.ok(surface.includes('slopes=ARC_ANCHORS.map('));
assert.ok(surface.includes('const leftRate=(junctionArc-thirdArc)'));
assert.ok(surface.includes("turn1435ArcBlend:'validated-local-arc-correction'"));
assert.ok(surface.includes('physicalMarkersUnchanged:true'));
assert.ok(surface.includes('immutableSharedEngine:true'));
assert.ok(surface.includes('const mapped=[]'));
assert.ok(surface.includes('const target=hermite('));
assert.ok(surface.includes('const d=sourceDistance(raceD)'));
assert.ok(surface.includes('sourceDistanceTable=buildSourceArcMap()'));
assert.ok(surface.includes('b.low=Math.max(b.low,a.low-SLOPE)'));
assert.ok(surface.includes('b.high=Math.min(b.high,a.high+SLOPE)'));
assert.ok(surface.includes('maxLane0FromInner'));
assert.ok(surface.includes('SMOOTH_RADIUS=19'));
assert.ok(surface.includes('const wanted=5.0;'));
assert.ok(surface.includes('const end=point(2000,lane),before=point(1990,lane)'));
assert.ok(app.includes('FINISH_SEQUENCE_MS=3200'));
assert.ok(html.includes('id="finishBanner"'));
assert.ok(app.includes('finishSequenceActive=true;'));
assert.ok(app.includes('const coast=6*'));
assert.ok(app.includes('finishSequenceDone'));
assert.ok(!app.includes('if(state.finished){playing=false'));

assert.ok(app.includes('displayPoints(state)'));
assert.ok(app.includes('visualLaneState=new Map()'));
assert.ok(app.includes('cameraFor(points,live.w,live.h,chosen,focusNo'));
assert.ok(app.includes('frameSample:()=>('));
assert.ok(app.includes("scale:(w<540?8.8:9.7)*"));
assert.ok(!app.includes('const group=points.filter(p=>Math.abs(p.d-focus.d)<=80)'));
assert.ok(!surface.includes('const optimal=clamp(predicted'));
assert.ok(!surface.includes('const half=Math.min(9'));
assert.ok(surface.includes('function discOnTurf('));
assert.ok(surface.includes('function runners(state)'));
assert.ok(app.includes('points=displayPoints(state)'));
assert.ok(app.includes('return turf.runners(state);'));
assert.ok(app.includes('turfBadDiscs:'));
assert.ok(!app.includes('const state=engine.state,points=model.runners(state)'));
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
assert.ok(app.includes('const leaderDistance=Math.max(...points.map(p=>p.d));'));
assert.equal(typeof window.RaceLaneAI.plan,'function');
assert.equal(typeof window.RaceLaneAI.launchStepSafe,'function');
assert.ok(sim.state.totalInsideMoves>=8,'Kyoto 1400 shared engine must execute inward moves');
assert.ok(!app.includes('for(const s of W.sections)'));
assert.ok(html.includes('id="runningOrder"'));
assert.ok(app.includes('point(')||app.includes('model.runners('));
console.log('PASS_LAB_UNALTERED_PUBLISHER_CLEAN_SVG_AND_COMPACT_NUMBERS',samples);
console.log('PASS_LAB_CLEAN_COURSE_SHARED_KYOTO1400_LANE_ENGINE_18_HORSES',JSON.stringify(snapshots));
