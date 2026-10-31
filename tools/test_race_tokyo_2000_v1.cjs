'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const g={},load=n=>vm.runInNewContext(fs.readFileSync('docs/lab/'+n+'.js','utf8'),{window:g,globalThis:g});
['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1','race-ability-model-v1','race-cohort-speed-v1','race-sim-engine','race-lab-18-fixture-v1','race-clean-goal-view-v1','race-tokyo-2000-v1'].forEach(load);
const data=g.RaceTokyo2000.race(),legacy=g.RaceSimAbility;
const unrelated=['kyoto_turf_inner_2000','kyoto_turf_outer_1400','tokyo_turf_2000'].map(course_id=>({...data,course_id,labTokyoAbility90:false}));
const before=unrelated.map(r=>JSON.stringify(legacy.profile(r.horses[0],r,0)));
load('race-tokyo-ability90-v1');
assert.deepEqual(unrelated.map(r=>JSON.stringify(g.RaceSimAbility.profile(r.horses[0],r,0))),before);
assert.equal(g.RaceTokyo2000.status.canAnimate,false);
assert.throws(()=>g.RaceTokyo2000.create(),/UNVERIFIED/);
assert.equal(data.horses.length,18);
for(const h of data.horses){const p=g.RaceSimAbility.profile(h,data,0);for(const key of Object.keys(h.labAbility90)){assert.equal(p.displaySix[key],h.labAbility90[key]);assert.equal(p.six[key],50+(h.labAbility90[key]-90)/.3);}}
assert.throws(()=>g.RaceSimAbility.profile({...data.horses[0],labAbility90:{early:99}},data,0),/INVALID/);
const neutral={...data.horses[0],labAbility90:Object.fromEntries(Object.keys(data.horses[0].labAbility90).map(k=>[k,90]))};
assert.ok(Object.values(g.RaceSimAbility.profile(neutral,data,0).six).every(v=>v===50));
for(const width of [368,992]){let prev;
 for(const d of [1920,1950,1980,2000,2032]){const p=g.RaceTokyo2000.goalPosition(d,7,width,380);assert.ok(Math.abs(p.x-width*(.3+(2000-d)/100))<1e-8);if(prev)assert.ok(p.x<prev.x);prev=p;}}
// Numerical engine audit only: not proof that the unapproved source route is safe.
function run(){const sim=g.RaceSimEngine.create(data,{seed:2026,bias:'neutral'});for(let n=0;n<4000&&!sim.state.finished;n++)sim.step(.08);assert.ok(sim.state.finished);assert.ok(sim.state.horses.every(h=>h.finished&&h.displayD>=2032));return JSON.stringify(sim.standings().map(h=>[h.number,h.finishTime,h.d,h.displayD]));}
assert.equal(run(),run());
console.log('PASS: Tokyo blocked; 108 ability values; neutral normalization; other-course isolation; camera projection; numerical 18-runner reproducibility. Source safety/playback NOT certified.');
