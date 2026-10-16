/* Stage-only Shuka Sho inner 2000m acceptance test.
 * Synthetic runners exist only in this test harness, NEVER in the public
 * manifest, page, STEP1 report, predictions or JRA final bets.
 */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),vm=require('node:vm');
const dir='docs/staging/',w={};
for(const file of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js']){
 vm.runInNewContext(fs.readFileSync(dir+file,'utf8'),{window:w,globalThis:w});
}
const G=w.RaceCourseGeometry,p=G.get('kyoto_turf_inner_2000');
const blueprint=JSON.parse(fs.readFileSync(dir+'weekend-main-course-blueprints-20261017.json','utf8'));
const approved=blueprint.courses.find(x=>x.course_id===p?.id);
assert.ok(p&&approved&&G.validate(p));
assert.equal(p.user_approved_stage_geometry,true);
assert.equal(approved.approval.status,'user_approved_illustration');
assert.equal(approved.approval.real_horse_replay_requires_pre_race_frozen_report,true);
assert.equal(blueprint.safe_for_live_simulator,false,'missing prereport blocks public runners');
assert.equal(p.venue,'京都');assert.equal(p.turn,'右');
assert.equal(p.distance_m,2000);assert.equal(p.lap_m,1782.8);
assert.equal(p.straight_m,328.4);assert.equal(p.elevation_range_m,3.1);
assert.equal(p.segments.length,7);
for(let i=0;i<7;i++){
 const actual=p.segments[i],ref=approved.segments[i];
 assert.equal(actual.from,approved.segment_bounds[i]);
 assert.equal(actual.to,approved.segment_bounds[i+1]);
 for(let j=0;j<4;j++)for(let axis=0;axis<2;axis++){
  assert.ok(Math.abs(actual['p'+j][axis]-ref[j][axis])<.0001,'approved XY must match');
 }
}
assert.ok(Math.hypot(p.segments[0].p0[0]-p.segments.at(-1).p3[0],
 p.segments[0].p0[1]-p.segments.at(-1).p3[1])>70,'distinct START and GOAL');
assert.equal(G.metrics(p,1671.6,0).isFinalStraight,true);
assert.equal(G.metrics(p,1671.59,0).isFinalStraight,false);
assert.ok(G.metrics(p,1435,4).pathStretch>G.metrics(p,1435,0).pathStretch);
let maxStep=0;
for(let d=0;d<2000;d++){
 const a=G.center(p,d),b=G.center(p,d+1);
 const delta=Math.hypot(b.x-a.x,b.y-a.y);
 maxStep=Math.max(maxStep,delta);
 assert.ok(Number.isFinite(a.x)&&Number.isFinite(a.y)&&delta<4,
  'course must be continuous and no 4C teleport at '+d);
 for(const lane of [0,3,7]){const point=G.point(p,d,lane);
  assert.ok(Number.isFinite(point.x)&&Number.isFinite(point.y));
 }
}
const manifest=JSON.parse(fs.readFileSync(dir+'race-sim-manifest-v1.json','utf8'));
assert.equal(manifest.status,'STAGING_RESEARCH_ONLY');
assert.equal(manifest.races.some(x=>x.course_id===p.id),false,
 'must not start real-horse sim before JRA fixed pre-race report exists');
const publicPage=fs.readFileSync(dir+'weekend-main-course-review.html','utf8');
const js=fs.readFileSync(dir+'weekend-main-course-review-v1.js','utf8');
assert.match(publicPage,/race-course-geometry-v1\.js\?v=20261016-40/);
assert.match(publicPage,/走行線の試走（コースの位置確認のみ）/);
assert.match(js,/user_approved_illustration/);
assert.match(js,/sharedSplineSvg/);
assert.match(js,/setProbeDistance/);
assert.doesNotMatch(js,/RaceSimEngine\.create|parseHorseReport/);
const simulator=fs.readFileSync(dir+'race-simulator.js','utf8');
const simHTML=fs.readFileSync(dir+'race-simulator.html','utf8');
assert.ok(simHTML.includes('id="genericCourseCanvas"'));
assert.ok(simHTML.includes('race-course-geometry-v1.js?v=20261016-40'));
assert.ok(simHTML.includes('race-simulator.js?v=20261016-40'));
assert.ok(simulator.includes("ui.map=canUseGeneric?$('genericCourseCanvas'):null;"));
assert.ok(simulator.includes("if(!['tokyo_turf_2000','kyoto_turf_outer_1400'].includes(race.course_id))return;"));
assert.ok(simulator.includes('drawLicensedOverlay(state);'));
assert.ok(simulator.includes('drawCourse();'));
// Physics smoke test, test-only generated field, no report writes.
const styles=['nige','nige','senko','senko','senko','senko',
 'sashi','sashi','sashi','sashi','sashi','sashi',
 'sashi','sashi','oikomi','oikomi','oikomi','oikomi'];
let complete=0;
for(const seed of [1,18,2026]){
 const horses=styles.map((style,i)=>({number:i+1,name:'TEST-'+(i+1),style,
  grade:'B',mark:'△',pace_grade:'B',factorGrades:Array(9).fill('B'),
  recentRuns:[],win_pct:100/18}));
 const sim=w.RaceSimEngine.create({id:'test-only-inner-course',
  course_id:p.id,venue:'京都',turn:'右',distance_m:2000,horses},{seed});
 let ticks=0;
 while(!sim.state.finished&&ticks++<3000)sim.step(.1);
 assert.ok(sim.state.finished,'all horses must complete');
 assert.equal(sim.standings().length,18);
 assert.ok(sim.state.splitTime>53&&sim.state.splitTime<75,
  '1000m intermediate time');
 assert.ok(sim.state.firstFinishTime>110&&sim.state.firstFinishTime<135,
  'finish time within smoke bounds');
 const arr=sim.standings();
 assert.ok(arr.every((h,i)=>h.finished&&h.displayD>=2032&&
   (i===0||h.finishTime>=arr[i-1].finishTime)));
 assert.ok(Math.abs(sim.state.firstFinishTime-arr[0].finishTime)<1e-6);
 complete++;
}
console.log('PASS_STAGE_SHUKA_COURSE_ENGINE_REHEARSAL',complete,
 'synthetic TEST-ONLY seeds','max px/m',maxStep.toFixed(2),'NO PUBLIC HORSE DATA');
