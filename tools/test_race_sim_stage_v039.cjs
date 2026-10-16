/* Stage v0.39 generic course-transition regression.
 * Stage presentation only: same physics, fixed results, all-course shared
 * centerline and bounded follow-camera acceleration, with no Kyoto constants.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const base='docs/staging/',W={};
for(const n of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js']){
 vm.runInNewContext(fs.readFileSync(base+n,'utf8'),{window:W,globalThis:W});
}
const G=W.RaceCourseGeometry;
const ui=fs.readFileSync(base+'race-simulator.js','utf8');
const traceSource=ui.slice(ui.indexOf('const raceTrackTraceCache='),ui.indexOf('function strokePath(',ui.indexOf('const raceTrackTraceCache=')));
assert.ok(traceSource.startsWith('const raceTrackTraceCache=new WeakMap();'));
const painters=new Function('RaceCourseGeometry',traceSource+';return {traceRace,traceRacePoints};')(G);
const camSource=ui.slice(ui.indexOf('function frameEntireField('),ui.indexOf('window.RaceSimCamera='));
const cams=new Function('RaceCourseGeometry',camSource+';return {frameEntireField,stableCameraFrame};')(G);
let checkedPoints=0, checkedFrames=0,maximumAccel=0;
const style=['nige','nige','senko','senko','senko','senko',
 'sashi','sashi','sashi','sashi','sashi','sashi',
 'oikomi','oikomi','oikomi','oikomi','unknown','unknown'];
for(const id of ['tokyo_turf_2000','kyoto_turf_outer_1400']){
 const profile=G.get(id),points=painters.traceRacePoints(profile);
 assert.equal(points.length,Math.ceil(profile.distance_m)+1,
   'generic one-metre active rail sampling');
 assert.equal(points,painters.traceRacePoints(profile),'cache path on repeated frames');
 const commands=[],ctx={beginPath:()=>commands.push(['begin']),moveTo:(x,y)=>commands.push(['move',x,y]),
  lineTo:(x,y)=>commands.push(['line',x,y])};
 painters.traceRace(ctx,profile);
 assert.equal(commands.length,points.length+1,'active track uses continuous lineTo');
 for(let i=0;i<points.length;i+=11){
  const d=profile.distance_m*i/(points.length-1),centre=G.center(profile,d),p=points[i];
  assert.ok(Math.hypot(p.x-centre.x,p.y-centre.y)<1e-8,'painted track on horse source spline');
  // Horse number positions differ from centre ONLY by their physical lane offset.
  const horse=G.point(profile,d,4);
  const dot=(horse.x-centre.x)*centre.tx+(horse.y-centre.y)*centre.ty;
  assert.ok(Math.abs(dot)<1e-6,'no longitudinal path remapping');
  checkedPoints++;
 }
 for(const boundary of profile.segments.slice(1).map(s=>s.from)){
  const a=G.center(profile,boundary-.05),b=G.center(profile,boundary+.05);
  assert.ok(Math.hypot(b.x-a.x,b.y-a.y)<.11,
    'generic smooth bend/straight join at '+id+':'+boundary);
 }
 const horses=style.map((runningStyle,i)=>({number:i+1,name:'runner'+(i+1),style:runningStyle,
  mark:'△',grade:'B',win_pct:5.5,pace_grade:'B',factorGrades:Array(9).fill('B'),recentRuns:[]}));
 const sim=W.RaceSimEngine.create({id:'generic-camera-'+id,course_id:id,
  venue:profile.venue,turn:profile.turn,distance_m:profile.distance_m,horses},{seed:2026});
 let frame=null,n=0,peak=0,viewable=0;
 while(!sim.state.finished&&n++<3000){
  sim.step(.1);
  const target=cams.frameEntireField(sim.state.horses,profile,'follow',1000,730,390);
  const current=cams.stableCameraFrame(target,frame,sim.state.t,1000,730,390);
  assert.ok(Number.isFinite(current.zoom)&&current.zoom>.01);
  assert.ok(Number.isFinite(current.origin.x)&&Number.isFinite(current.origin.y));
  if(frame){
   const dt=current.time-frame.time;
   const acceleration=Math.hypot(current.panVelocity.x-frame.panVelocity.x,
     current.panVelocity.y-frame.panVelocity.y)/dt;
   peak=Math.max(peak,acceleration);
   assert.ok(acceleration<=12*profile.mapUnitsPerMeter+.0001,
    'scale-normalized camera must not B-dash at any track boundary');
  }
  for(const h of sim.state.horses){
   const p=G.point(profile,h.displayD??h.d,h.lane);
   const x=current.anchor.x+current.zoom*(p.x-current.origin.x);
   const y=current.anchor.y+current.zoom*(p.y-current.origin.y);
   assert.ok(x>=0&&x<=1000&&y>=0&&y<=730,'all horse numbers stay inside frame');
  }
  if(sim.state.leader>=profile.distance_m-profile.straight_m-80&&
     sim.state.leader<=profile.distance_m-profile.straight_m+100)viewable++;
  checkedFrames++;frame=current;
 }
 assert.ok(sim.state.finished,'all runners cross and run off');
 assert.ok(viewable>40,'corner and straight sampled at full speed');
 maximumAccel=Math.max(maximumAccel,peak);
}
const html=fs.readFileSync(base+'race-simulator.html','utf8');
assert.ok(html.includes('race-course-geometry-v1.js?v=20261016-40'));
assert.ok(html.includes('race-simulator.js?v=20261016-39'));
assert.ok(html.includes('Shared transitions v0.39'));
assert.ok(html.includes('全競馬場共通の連続走行スプライン'));
console.log('PASS_V039_SHARED_RACING_LINE_AND_CAMERA_SMOOTHING',checkedPoints,
 'track samples',checkedFrames,'frames',maximumAccel.toFixed(2),'peak accel');
