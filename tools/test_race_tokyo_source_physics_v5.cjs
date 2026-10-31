'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto'),cp=require('node:child_process');
const inputPath=process.argv[2];if(!inputPath)throw Error('Usage: node test_race_tokyo_source_physics_v5.cjs /tmp/source/audit-local.json');
const g={crypto:crypto.webcrypto};
const modules=['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1','race-ability-model-v1','race-tokyo-ability90-v1','race-tokyo-lateral-policy-v4','race-cohort-speed-v1','race-sim-engine','race-lab-18-fixture-v1','race-clean-goal-view-v1','race-tokyo-2000-v1','race-tokyo-source-audit-v2','race-tokyo-source-physics-v5','race-tokyo-safety-v5'];
function load(old=false){const ctx={crypto:crypto.webcrypto};for(const n of modules){const text=old&&n==='race-sim-engine'?cp.execFileSync('git',['show','08d78b7ada38b2ef63f0765822aa9f0951fa2b0e:docs/lab/race-sim-engine.js']).toString():fs.readFileSync('docs/lab/'+n+'.js','utf8');
 vm.runInNewContext(text,{window:ctx,TextEncoder,setTimeout});}return ctx;}
(async()=>{
 const g=load(),input=JSON.parse(fs.readFileSync(inputPath,'utf8')),before=JSON.stringify(g.RaceCourseGeometry.COURSE);
 const originalPayload=g.RaceTokyoSourcePhysicsV5.payload(input),session=await g.RaceTokyoSourcePhysicsV5.prepare(input),route=g.RaceTokyoSourcePhysicsV5.inspect(session);
 assert.equal(crypto.createHash('sha256').update(originalPayload).digest('hex'),g.RaceTokyoSourcePhysicsV5.GEOMETRY_SHA);
 const edited=structuredClone(input);edited.sections[0].points[0][0]+=.01;
 await assert.rejects(g.RaceTokyoSourcePhysicsV5.prepare(edited),/UNRECOGNIZED|GAP/);
 const unknown=structuredClone(input);unknown.sourceSvgSha256='0'.repeat(64);
 await assert.rejects(g.RaceTokyoSourcePhysicsV5.prepare(unknown),/UNRECOGNIZED/);
 const fake={...session},data={...g.RaceTokyo2000.race({motion:'bounded-lateral-v4'}),labTokyoSourceModel:'source-linked-v5'};
 assert.throws(()=>g.RaceSimEngine.create(data),/SESSION_REQUIRED/);
 assert.throws(()=>g.RaceSimEngine.create(data,{labTokyoSourceSession:fake}),/SESSION_REQUIRED/);
 for(const altered of [{...data,scope:'OFFICIAL'},{...data,horses:data.horses.slice(1)},{...data,labTokyoMotion:undefined}])
  assert.throws(()=>g.RaceSimEngine.create(altered,{labTokyoSourceSession:session}),/SESSION_REQUIRED|頭数/);
 const privateGeo=g.RaceTokyoSourcePhysicsV5.resolve(data,session);
 assert.throws(()=>{privateGeo.get('tokyo_turf_2000').segments[1].from=130;},TypeError);
 const boundaries=route.boundaries();assert.deepEqual(Array.from(boundaries,s=>s.from),[0,100,300,900,1145,1474.1]);
 for(let d=301;d<899;d+=.5){const a=route.center(d),b=route.center(d+.1);assert.ok(Math.abs(a.y-b.y)<1e-6);assert.equal(route.metrics(d).kind,'straight');assert.ok(route.metrics(d).bend<1e-8);assert.ok(a.tx<-.999999);}
 assert.equal(route.metrics(110).kind,'turn');assert.ok(route.metrics(110).bend>0);
 assert.ok(route.metrics(1600).grade>0);assert.equal(route.metrics(1800).grade,0);
 assert.equal(route.metrics(1600).pathStretch,1);assert.ok(route.metrics(200,16).pathStretch>route.metrics(200,0).pathStretch);
 for(const d of [100,300,900,1145,1474.1,2000])for(const lane of [0,8,16]){
  const a=route.point(d-.001,lane),b=route.point(d+.001,lane);assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<.01,'continuous boundary');
 }
 // Recorded static checkpoints are inspection material; they cannot target race results.
 const alteredShots=structuredClone(input);alteredShots.numericalCheckpoints=[];
 const second=await g.RaceTokyoSourcePhysicsV5.prepare(alteredShots);
 const a=await g.RaceTokyoSafetyV5.run(session,2026,{yieldEvery:0}),b=await g.RaceTokyoSafetyV5.run(second,2026,{yieldEvery:0});
 assert.equal(JSON.stringify(a),JSON.stringify(b));assert.equal(JSON.stringify(g.RaceCourseGeometry.COURSE),before);
 const old=load(true);
 function digest(ctx,course,seed,sourceFlag=false){const p=ctx.RaceCourseGeometry.get(course),data={...ctx.RaceTokyo2000.race({motion:'bounded-lateral-v4'}),course_id:course,distance_m:p.distance_m,venue:p.venue,turn:p.turn,...(sourceFlag?{labTokyoSourceModel:'source-linked-v5'}:{})};
  const sim=ctx.RaceSimEngine.create(data,{seed,bias:'neutral'}),hash=crypto.createHash('sha256');hash.update(JSON.stringify(sim.state));let n=0;
  while(!sim.state.finished&&n++<5000){sim.step(.08);hash.update(JSON.stringify(sim.state));}assert.ok(sim.state.finished);return hash.digest('hex');}
 for(const course of ['tokyo_turf_2000','kyoto_turf_inner_2000','kyoto_turf_outer_1400'])for(const seed of [1,2026]){
  assert.equal(digest(g,course,seed),digest(old,course,seed));
  if(course!=='tokyo_turf_2000')assert.equal(digest(g,course,seed,true),digest(old,course,seed));
 }
 delete g.RaceTokyoSourcePhysicsV5;assert.throws(()=>g.RaceSimEngine.create(data,{labTokyoSourceSession:session}),/ADAPTER_MISSING/);
 console.log('PASS source geometry fingerprint/tamper, opaque session, original long straight, boundary continuity, final hill, snapshot independence, repeatability, global geometry unchanged, v4 full-state parity (3 courses x2 seeds), other-course flag isolation, missing adapter lock');
})().catch(e=>{console.error(e);process.exitCode=1;});
