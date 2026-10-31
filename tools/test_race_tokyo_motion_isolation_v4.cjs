'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict'),cp=require('node:child_process');
const reference='5412362f21309842797d9bfb12fd63f817d2ef2b',oldSource=cp.execFileSync('git',['show',reference+':docs/lab/race-sim-engine.js']);
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(sha(oldSource),'5ef55f7de258283afb201be05cbccc4bba270aa9b099c83d57eae8d431927bb4');
const currentSource=fs.readFileSync('docs/lab/race-sim-engine.js');
function load(engineSource){const g={};
 for(const n of ['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1','race-ability-model-v1','race-tokyo-ability90-v1','race-tokyo-lateral-policy-v4','race-cohort-speed-v1','race-sim-engine','race-lab-18-fixture-v1','race-clean-goal-view-v1','race-tokyo-2000-v1'])
  vm.runInNewContext((n==='race-sim-engine'?engineSource:fs.readFileSync('docs/lab/'+n+'.js')).toString(),{window:g,globalThis:g});
 return g;
}
function digest(g,courseId,seed,flag=false){const p=g.RaceCourseGeometry.get(courseId),base=g.RaceTokyo2000.race();
 const data={...base,course_id:p.id,distance_m:p.distance_m,venue:p.venue,turn:p.turn,...(flag?{labTokyoMotion:'bounded-lateral-v4'}:{})};
 const sim=g.RaceSimEngine.create(data,{seed,bias:'neutral'}),hash=crypto.createHash('sha256');let ticks=0;
 hash.update(JSON.stringify(sim.state));while(!sim.state.finished&&ticks++<4000){sim.step(.08);hash.update(JSON.stringify(sim.state));}
 assert.ok(sim.state.finished);return{ticks,stateSequenceSha256:hash.digest('hex')};
}
const old=load(oldSource),g=load(currentSource),rows=[];
for(const courseId of ['tokyo_turf_2000','kyoto_turf_inner_2000','kyoto_turf_outer_1400'])for(const seed of [1,2026]){
 const expected=digest(old,courseId,seed),actual=digest(g,courseId,seed);assert.deepEqual(actual,expected);
 if(courseId!=='tokyo_turf_2000')assert.deepEqual(digest(g,courseId,seed,true),expected,'Tokyo flag must not affect another course');
 rows.push({courseId,seed,...actual});
}
const valid=g.RaceTokyo2000.race({motion:'bounded-lateral-v4'}),cfg=g.RaceLaneAI.config(g.RaceCourseGeometry.get(valid.course_id));
assert.throws(()=>g.RaceTokyoLateralV4.create({...valid,scope:'OFFICIAL'},cfg),/INVALID/);
assert.throws(()=>g.RaceTokyoLateralV4.create({...valid,course_id:'kyoto_turf_inner_2000'},cfg),/INVALID/);
assert.ok(g.RaceSimEngine.create(valid,{seed:2026}).labTokyoMotionStats);
assert.equal(g.RaceSimEngine.create(g.RaceTokyo2000.race(),{seed:2026}).labTokyoMotionStats,undefined);
delete g.RaceTokyoLateralV4;assert.throws(()=>g.RaceSimEngine.create(valid,{seed:2026}),/MISSING/);
assert.throws(()=>g.RaceTokyo2000.create(),/UNVERIFIED/);
const report={referenceCommit:reference,referenceSourceSha256:sha(oldSource),currentSourceSha256:sha(currentSource),runtime:process.version,rows,canAnimate:false};
const outIndex=process.argv.indexOf('--out');if(outIndex>=0){const out=process.argv[outIndex+1];fs.mkdirSync(path.dirname(path.resolve(out)),{recursive:true});fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');}
console.log('PASS full default-state sequence parity against reference Git source (3 courses x 2 seeds), other-course opt-in isolation, invalid scope/missing module rejection, animation remains locked');
