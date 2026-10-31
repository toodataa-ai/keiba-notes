/* Immutable shared-engine diagnostics: no source images, no visual replay. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const {sweptRectangle}=require('./lib/race-swept-audit-v1.cjs');
const args=process.argv.slice(2),option=(key,otherwise)=>{const i=args.indexOf(key);return i<0?otherwise:args[i+1]};
const motion=option('--motion','legacy');
if(!['legacy','bounded-lateral-v4'].includes(motion))throw Error('AUDIT_MOTION_INVALID');
const seedText=option('--seeds','1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,2026,2027');
const seeds=seedText.split(',').map(Number);
if(!seeds.length||new Set(seeds).size!==seeds.length||seeds.some(x=>!Number.isInteger(x)||x<1||x>999999))throw Error('AUDIT_SEEDS_INVALID');
const root=path.resolve(__dirname,'../docs/lab'),g={};
const modules=['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1','race-ability-model-v1',
 'race-tokyo-ability90-v1','race-tokyo-lateral-policy-v4','race-cohort-speed-v1','race-sim-engine','race-lab-18-fixture-v1','race-clean-goal-view-v1','race-tokyo-2000-v1'];
const sourceHashes={};
for(const n of modules){const bytes=fs.readFileSync(path.join(root,n+'.js'));sourceHashes[n]=crypto.createHash('sha256').update(bytes).digest('hex');vm.runInNewContext(bytes.toString(),{window:g,globalThis:g});}
const rules={lengthMetres:2.55,widthMetres:.8,laneMetres:1.65,epsilonMetres:1e-6,
 description:'Axis-aligned horse rectangles in course-distance/lane coordinates; linear swept interpolation. Not measured horse silhouettes or proof of real-world collision safety.'};
function run(seed,dt=.08){
 const data=g.RaceTokyo2000.race({motion}),inputBefore=JSON.stringify(data),sim=g.RaceSimEngine.create(data,{seed,bias:'neutral'});
 const maxLane=sim.laneConfig.maxLane,laneMetres=sim.laneConfig.laneWidthM;
 let steps=0,pairs=0,endpointHits=0,sweptHits=0,launchEndpointHits=0,launchSweptHits=0,boundsViolations=0,backwardSteps=0;
 let runoffEndpointHits=0,allStateSweptHits=0;
 let maxLateral={mps:0},maxLateralVelocityJump={mps:0},minLane=Infinity,maxSeenLane=-Infinity;
 const examples=[],milestones=[],targets=[0,16,50,85,100,110,120,130,150,220,300,900,1145,1474.1,1600,1920,2000];
 const capture=()=>sim.state.horses.map(h=>({number:h.number,d:h.d,lane:h.lane,finished:h.finished,finishTime:h.finishTime,displayD:h.displayD,vLat:h.laneVelocity||0}));
 function landmark(){while(targets.length&&sim.state.leader>=targets[0]){const target=targets.shift();milestones.push({target,leader:sim.state.leader,t:sim.state.t,lanes:sim.state.horses.map(h=>({number:h.number,d:h.d,lane:h.lane}))});}}
 landmark();
 while(!sim.state.finished&&steps<5000){
  const before=capture(),oldTime=sim.state.t,oldLeader=sim.state.leader;
  sim.step(dt);steps++;const after=capture();
  for(let i=0;i<after.length;i++){
   const a=before[i],b=after[i];if(a.finished)continue;
   const mps=(b.lane-a.lane)*laneMetres/dt,jump=Math.abs(mps-a.vLat*laneMetres);
   if(!Number.isFinite(b.lane)||b.lane<0||b.lane>maxLane)boundsViolations++;
   if(b.d<a.d-1e-9)backwardSteps++;
   minLane=Math.min(minLane,b.lane);maxSeenLane=Math.max(maxSeenLane,b.lane);
   const pose={number:b.number,t:sim.state.t,d:b.d,leader:sim.state.leader};
   if(Math.abs(mps)>maxLateral.mps)maxLateral={mps:Math.abs(mps),signedMps:mps,...pose};
   if(jump>maxLateralVelocityJump.mps)maxLateralVelocityJump={mps:jump,finiteDifferenceMps2:jump/dt,...pose};
  }
  for(let i=0;i<after.length;i++)for(let j=i+1;j<after.length;j++){
   const a0=before[i],b0=before[j],a1=after[i],b1=after[j];
   const displayA0={d:a0.displayD,lane:a0.lane},displayA1={d:a1.displayD,lane:a1.lane};
   const displayB0={d:b0.displayD,lane:b0.lane},displayB1={d:b1.displayD,lane:b1.lane};
   if(sweptRectangle(displayA0,displayA1,displayB0,displayB1,{laneMetres}))allStateSweptHits++;
   if((a1.finished||b1.finished)&&Math.abs(a1.displayD-b1.displayD)<rules.lengthMetres-rules.epsilonMetres&&
    Math.abs(a1.lane-b1.lane)*laneMetres<rules.widthMetres-rules.epsilonMetres)runoffEndpointHits++;
   if(a0.finished||b0.finished)continue;
   pairs++;
   const fraction=h=>h.finished?Math.max(0,Math.min(1,(h.finishTime-oldTime)/dt)):1;
   const endFraction=Math.min(fraction(a1),fraction(b1));
   // Recover un-clipped distance rate until the interpolated wire crossing.
   const extend=(old,current)=>current.finished&&fraction(current)>0?
    {...current,d:old.d+(2000-old.d)/fraction(current)}:current;
   const ae=extend(a0,a1),be=extend(b0,b1);
   const swept=sweptRectangle(a0,ae,b0,be,{laneMetres,endFraction});
   const endpoint=!a1.finished&&!b1.finished&&Math.abs(a1.d-b1.d)<rules.lengthMetres-rules.epsilonMetres&&
    Math.abs(a1.lane-b1.lane)*laneMetres<rules.widthMetres-rules.epsilonMetres;
   if(endpoint){endpointHits++;if(oldLeader<=130)launchEndpointHits++;}
   if(swept){sweptHits++;if(oldLeader<=130)launchSweptHits++;
    if(examples.length<8)examples.push({pair:[a1.number,b1.number],fromTime:oldTime+dt*swept.from,toTime:oldTime+dt*swept.to,
     leaderBefore:oldLeader,endpointHit:endpoint,endFraction,before:[a0,b0],after:[a1,b1]});}
  }
  landmark();
 }
 if(JSON.stringify(data)!==inputBefore)throw Error('AUDIT_MUTATED_INPUT');
 const results=sim.standings().map(h=>({number:h.number,finishTime:h.finishTime,gap:h.finishTime-sim.state.firstFinishTime,displayD:h.displayD}));
 const signature=crypto.createHash('sha256').update(JSON.stringify(results)).digest('hex');
 return {seed,stepSeconds:dt,steps,pairSteps:pairs,maxLane,minLane,maxSeenLane,endpointHits,sweptHits,launchEndpointHits,launchSweptHits,
  boundsViolations,backwardSteps,runoffEndpointHits,allStateSweptHits,maxLateral,maxLateralVelocityJump,examples,milestones,
  all18Finished:sim.state.horses.every(h=>h.finished),all18RunoffComplete:sim.state.finished&&sim.state.horses.every(h=>h.displayD>=2032),
  motionStats:sim.labTokyoMotionStats||null,finalStraightPasses:sim.state.finalStraightPasses,results,resultSignature:signature};
}
const runs=seeds.map(seed=>run(seed));
const referenceSeed=seeds.includes(2026)?2026:seeds[0],again=run(referenceSeed),first=runs.find(x=>x.seed===referenceSeed);
if(JSON.stringify(first)!==JSON.stringify(again))throw Error('AUDIT_REPRODUCIBILITY_FAILURE');
const sensitivitySeeds=[...new Set([seeds[0],seeds.at(-1),referenceSeed])];
const stepSensitivity=sensitivitySeeds.map(seed=>{const original=runs.find(x=>x.seed===seed),smaller=run(seed,.04);return{
 seed,stepSeconds:.04,all18Finished:smaller.all18Finished,all18RunoffComplete:smaller.all18RunoffComplete,
 endpointHits:smaller.endpointHits,sweptHits:smaller.sweptHits,launchSweptHits:smaller.launchSweptHits,runoffEndpointHits:smaller.runoffEndpointHits,allStateSweptHits:smaller.allStateSweptHits,
 maxLateralMps:smaller.maxLateral.mps,maxLateralVelocityJumpMps:smaller.maxLateralVelocityJump.mps,
 winnerTimeChangeSeconds:smaller.results[0].finishTime-original.results[0].finishTime,
 sameFinishOrder:smaller.results.map(x=>x.number).join(',')===original.results.map(x=>x.number).join(',')};});
const physical=g.RaceCourseGeometry.get('tokyo_turf_2000');
const boundaryComparison=[85,100,110,120,130,150,220,300,900,1145,1474.1].map(d=>{const m=g.RaceCourseGeometry.metrics(physical,d,0);return{
 distance:d,physicalKind:m.kind,physicalBend:m.bend,physicalSegment:m.segment,
 illustrationCandidateKind:d<100?'line':d<300?'left-curve':d<900?'line':d<1474.1?'left-curve':'line',
 illustrationDistancesAreHypotheses:true};});
const report={schema:'tokyo-launch-audit-v4',courseId:'tokyo_turf_2000',canAnimate:false,approval:'not_approved',
 motion,sourceHashes,rules,seeds,referenceSeed,reproducible:true,runs,stepSensitivity,boundaryComparison,
 summary:{seedCount:runs.length,all18Finished:runs.every(r=>r.all18Finished),all18RunoffComplete:runs.every(r=>r.all18RunoffComplete),
  endpointHits:runs.reduce((s,r)=>s+r.endpointHits,0),sweptHits:runs.reduce((s,r)=>s+r.sweptHits,0),
  launchEndpointHits:runs.reduce((s,r)=>s+r.launchEndpointHits,0),launchSweptHits:runs.reduce((s,r)=>s+r.launchSweptHits,0),
  runoffEndpointHits:runs.reduce((s,r)=>s+r.runoffEndpointHits,0),allStateSweptHits:runs.reduce((s,r)=>s+r.allStateSweptHits,0),
  boundsViolations:runs.reduce((s,r)=>s+r.boundsViolations,0),backwardSteps:runs.reduce((s,r)=>s+r.backwardSteps,0),
  maxLateralMps:Math.max(...runs.map(r=>r.maxLateral.mps)),maxLateralVelocityJumpMps:Math.max(...runs.map(r=>r.maxLateralVelocityJump.mps)),emergencyStops:runs.reduce((s,r)=>s+(r.motionStats?.emergencyStops||0),0)},
 unresolved:['unmeasured-real-entry-angle','illustration/physical-boundary-mismatch','lateral-motion-naturalness','full-source-topology','real-time-1x/2x/4x','visual-approval']};
const out=option('--out',null);if(out){fs.mkdirSync(path.dirname(path.resolve(out)),{recursive:true});fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({summary:report.summary,stepSensitivity,boundaryComparison,canAnimate:false},null,2));
