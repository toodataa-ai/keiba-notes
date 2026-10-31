/* Compare against a checkout of the exact PR base. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..'),base=process.argv[2];
if(!base)throw Error('Usage: node tools/compare-shared-course-v1.cjs BASE_CHECKOUT');
const files=['race-course-geometry-v1.js','race-lane-ai-v1.js','race-runner-style-v1.js','race-ability-model-v1.js','race-cohort-speed-v1.js','race-sim-engine.js','race-lab-18-fixture-v1.js','race-real-shuka-2026-fixture-v1.js','race-clean-course-v1.js'];
function load(dir){const c=vm.createContext({URLSearchParams});for(const f of files){const p='docs/lab/'+f;vm.runInContext(fs.readFileSync(path.join(dir,p),'utf8'),c,{filename:p});}return c;}
const before=load(base),after=load(root);
const json=x=>JSON.parse(JSON.stringify(x));
for(const fixture of ['RaceLab18Fixture','RaceRealShuka2026Fixture'])for(const scale of ['90-v1','legacy-50'])for(const seed of [2026,1,75]){
 function run(c){const f=c[fixture],race={...f.entry(),horses:f.horses({abilityScale:scale}),...(scale==='90-v1'?{labAbilityScale:scale}:{})};const engine=c.RaceSimEngine.create(race,{seed,bias:'neutral'});let steps=0;while(!engine.state.finished&&steps++<6000)engine.step(.08);assert(engine.state.finished);assert(engine.state.horses.every(h=>h.finished));return json(engine.state);}
 assert.deepEqual(run(after),run(before));assert.deepEqual(run(after),run(after));
}
for(let d=0;d<=2000;d++)for(let lane=0;lane<=14;lane++)assert.deepEqual(json(after.RaceCleanCourse.point(d,lane)),json(before.RaceCleanCourse.point(d,lane)));
// Common 90-centred display must not modify legacy physics for prestart grades.
for(const course_id of ['tokyo_turf_2000','kyoto_turf_outer_1400','niigata_turf_1000']){
 const h={factorGrades:Array(9).fill('B'),recentRuns:[]},race={course_id,distance_m:2000};
 const legacy=after.RaceSimAbility.profile(h,race,0),display=after.RaceSimAbility.profile(h,{...race,labAbilityScale:'90-v1'},0);
 assert.deepEqual(json(legacy.six),json(display.six));assert.equal(display.neutral,90);
}
console.log('PASS: 12 complete race states + repeated runs; 30,015 Kyoto positions exact; common display scale preserves physical traits');
