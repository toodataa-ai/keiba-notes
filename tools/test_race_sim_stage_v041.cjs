/* Stage Shuka one-runner demonstration; asserts sealed JRA input isolation. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root='docs/staging/',w={};
for(const path of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js']){
 vm.runInNewContext(fs.readFileSync(root+path,'utf8'),{window:w,globalThis:w});
}
const src=fs.readFileSync(root+'race-simulator.js','utf8');
const html=fs.readFileSync(root+'race-simulator.html','utf8');
const manifest=JSON.parse(fs.readFileSync(root+'race-sim-manifest-v1.json','utf8'));
const horse={number:1,name:'仮の1頭（デモ）',mark:'△',grade:'B',pace_grade:'B',
 factorGrades:Array(9).fill('B'),style:'senko',recentRuns:[],win_pct:NaN};
const entry={id:'stage-shuka-inner-one-runner-demo-v1',demo_mode:'shuka_single_horse_v1',
 venue:'京都',turn:'右',distance_m:2000,course_id:'kyoto_turf_inner_2000',
 date:'2026-10-18',field_size:1,number:11,race:'秋華賞コース（仮1頭）',
 surface:'芝',horses:[horse]};
assert.doesNotThrow(()=>w.RaceSimEngine.validData(entry));
for(const mutate of [
 {...entry,demo_mode:null},
 {...entry,course_id:'kyoto_turf_outer_1400'},
 {...entry,field_size:18},
 {...entry,horses:[{...horse,name:'実在馬'}]},
 {...entry,horses:[{...horse,number:2}]}
])assert.throws(()=>w.RaceSimEngine.validData(mutate),/出走頭数が不正/);
assert.equal(manifest.races.length,2,'existing sealed races untouched');
assert.ok(manifest.races.every(x=>x.field_size===18));
assert.equal(manifest.races.some(x=>x.id===entry.id||x.course_id===entry.course_id),false);
for(const seed of [1,18,2026]){
 const sim=w.RaceSimEngine.create(entry,{seed});
 let n=0;while(!sim.state.finished&&n++<3000)sim.step(.1);
 assert.equal(sim.state.finished,true,'demo horse must finish');
 assert.equal(sim.standings().length,1);
 assert.ok(sim.state.splitTime>40&&sim.state.splitTime<80);
 assert.ok(sim.state.firstFinishTime>110&&sim.state.firstFinishTime<140);
 assert.equal(sim.state.paceContestants,0,'lone demo has no field contest');
 assert.ok(sim.standings()[0].displayD>2032);
}
assert.ok(html.includes('id="singleDemoNotice"'));
assert.ok(html.includes('race-simulator.js?v=20261016-43'));
assert.ok(html.includes('race-sim-engine.js?v=20261016-41'));
assert.ok(src.includes("params.get('demo')==='shuka-one'?DEMO_ID"));
assert.ok(src.includes("catalog=[...(registry.races||[]),demoEntry()]"));
assert.ok(src.includes("if(isDemo(entry))"));
assert.ok(src.includes("ui.focus.innerHTML='<option value=\"leader\">仮の1頭を追跡"));
assert.ok(src.includes("const [dbRes,reportRes]=await Promise.all"));
assert.ok(src.includes('updateCourseReference();reset(false)'));
assert.ok(src.includes("if(fieldSize===1&&number===1&&typeof race!=='undefined'&&isDemo(race))"));
assert.ok(src.includes('drawLicensedOverlay(state);'));
assert.ok(src.includes("isDemo(race)?'試走完了'"));
console.log('PASS_STAGE_SHUKA_ONE_RUNNER_DEMO_GATED_3_SEEDS_SEALED_JRA_UNTOUCHED');
