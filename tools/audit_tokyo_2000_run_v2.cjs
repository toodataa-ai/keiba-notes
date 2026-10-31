/* Numerical/source-route candidate audit only. No public playback. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const input=process.argv[2];if(!input)throw Error('Provide local audit-local.json; do not publish that source material');
const manifest=JSON.parse(fs.readFileSync(input,'utf8')),g={};
for(const n of ['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1','race-ability-model-v1',
 'race-tokyo-ability90-v1','race-cohort-speed-v1','race-sim-engine','race-lab-18-fixture-v1','race-clean-goal-view-v1','race-tokyo-2000-v1','race-tokyo-source-audit-v2'])
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../docs/lab/',n+'.js'),'utf8'),{window:g,globalThis:g});
const route=g.RaceTokyoSourceAudit.build(manifest);
let maxStep=0,maxBoundaryJump=0,maxBoundaryAngle=0,maxStraightDeviation=0,checks=0;
for(let lane=0;lane<=manifest.maxLane;lane++){
 let prev=route.point(0,lane);
 for(let d=.25;d<=2120;d+=.25){const p=route.point(d,lane);maxStep=Math.max(maxStep,Math.hypot(p.x-prev.x,p.y-prev.y));prev=p;checks++;}
 for(const d of [100,300,900,1145,1474.1,2000]){
  const a=route.point(d-.001,lane),b=route.point(d+.001,lane);
  maxBoundaryJump=Math.max(maxBoundaryJump,Math.hypot(a.x-b.x,a.y-b.y));
  maxBoundaryAngle=Math.max(maxBoundaryAngle,Math.acos(Math.min(1,Math.max(-1,a.tx*b.tx+a.ty*b.ty))));
 }
 const y=route.point(301,lane).y;
 for(let d=301;d<899;d++)maxStraightDeviation=Math.max(maxStraightDeviation,Math.abs(route.point(d,lane).y-y));
}
assert.ok(maxStep<.5,{maxStep});assert.ok(maxBoundaryJump<.01,{maxBoundaryJump});
assert.ok(maxBoundaryAngle<.003,{maxBoundaryAngle});assert.ok(maxStraightDeviation<.001,{maxStraightDeviation});
assert.ok(route.sourceHalfWidth>9+route.discRadius,'PROBE_TOUCHES_ROUTE_EDGE');
const start=route.center(0),at100=route.center(100),turn=route.center(130);
assert.ok(Math.abs(start.x-at100.x)<.001&&at100.y<start.y&&turn.x<at100.x);
const targets=g.RaceTokyo2000.checkpoints.filter(d=>d<=2000);
function run(seed){
 const sim=g.RaceSimEngine.create(g.RaceTokyo2000.race(),{seed,bias:'neutral'});let target=0,maxLaneSpeed=0,overlapFrames=0,launchOverlapFrames=0;const checkpoints=[];
 const capture=(distance)=>({distance,leader:sim.state.leader,t:sim.state.t,horses:sim.state.horses.map(h=>({number:h.number,d:h.d,displayD:h.displayD,lane:h.lane}))});
 checkpoints.push(capture(0));target++;
 for(let tick=0;tick<4000&&!sim.state.finished;tick++){
  const before=sim.state.horses.map(h=>h.lane);sim.step(.08);
  for(const [i,h] of sim.state.horses.entries()){
   maxLaneSpeed=Math.max(maxLaneSpeed,Math.abs(h.lane-before[i])/.08);
   route.point(h.displayD,h.lane);
  }
  const active=sim.state.horses.filter(h=>!h.finished);
  for(let i=0;i<active.length;i++)for(let j=i+1;j<active.length;j++){
   if(Math.abs(active[i].d-active[j].d)<2.55-1e-6&&Math.abs(active[i].lane-active[j].lane)*1.65<.8){
    overlapFrames++;if(sim.state.leader<=130)launchOverlapFrames++;
   }
  }
  while(target<targets.length&&sim.state.leader>=targets[target])checkpoints.push(capture(targets[target++]));
 }
 assert.ok(sim.state.finished&&sim.state.horses.every(h=>h.finished&&h.displayD>=2032));
 checkpoints.push(capture(2032));
 const results=sim.standings().map(h=>({number:h.number,time:h.finishTime,gap:h.finishTime-sim.state.firstFinishTime}));
 return {checkpoints,results,maxLaneSpeed,overlapFrames,launchOverlapFrames,finalStraightPasses:sim.state.finalStraightPasses};
}
const one=run(2026);assert.deepEqual(one,run(2026),'SEED_NOT_REPRODUCIBLE');
const report={schema:'tokyo-source-audit-v2',sourcePptxSha256:manifest.sourcePptxSha256,checks,
 maxStepPxPerQuarterM:maxStep,maxBoundaryJumpPx:maxBoundaryJump,maxBoundaryAngleRad:maxBoundaryAngle,
 maxStraightDeviationPx:maxStraightDeviation,minPathEdgeClearancePx:route.sourceHalfWidth-9-route.discRadius,
 startHeading:Math.atan2(start.ty,start.tx),turnHeading:Math.atan2(turn.ty,turn.tx),
 physicalEngine:'UNCHANGED existing Tokyo approximate metrics',numerical:one,canAnimate:false,
 unverified:['source-raster-occupancy','source-path-topology','physical-geometry-alignment','multi-seed-collision-safety','1x-2x-4x-playback','visual-approval']};
manifest.numericalCheckpoints=one.checkpoints;
fs.writeFileSync(input,JSON.stringify(manifest,null,2)+'\n');
fs.writeFileSync(path.join(path.dirname(input),'numeric-audit.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,numerical:{checkpoints:one.checkpoints.length,finishers:one.results.length,passes:one.finalStraightPasses,overlapFrames:one.overlapFrames,launchOverlapFrames:one.launchOverlapFrames,maxLaneSpeed:one.maxLaneSpeed}},null,2));
