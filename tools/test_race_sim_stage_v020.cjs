/* v0.20 staging-only physics regression; synthetic balanced abilities. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const stage={},root='docs/staging/';
for(const file of ['race-course-geometry-v1.js','race-lane-ai-v1.js','race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js']){
 vm.runInNewContext(fs.readFileSync(root+file,'utf8'),{window:stage,globalThis:stage},{filename:file});
}
const styles=['nige','nige','senko','senko','senko','senko','sashi','sashi','sashi','sashi','sashi','sashi','oikomi','oikomi','oikomi','oikomi','unknown','unknown'];
const horses=styles.map((style,i)=>({number:i+1,name:'test'+i,mark:['◎','○','▲','△','×'][i%5],grade:'B',win_pct:5.5,style,pace_grade:'B',factorGrades:Array(9).fill('B'),recentRuns:[]}));
function race(id,seed){
 const p=stage.RaceCourseGeometry.get(id);
 const sim=stage.RaceSimEngine.create({id:'balanced-'+id,course_id:id,venue:p.venue,turn:p.turn,distance_m:p.distance_m,horses},{seed,pace:'auto',bias:'neutral'});
 let steps=0;while(!sim.state.finished&&steps++<2600)sim.step(.16);
 assert(sim.state.finished,'race including 32m runoff finishes');
 assert(sim.state.horses.every(h=>h.finished&&Number.isFinite(h.finishTime)&&h.displayD>=sim.state.distance+31.99));
 assert(sim.state.horses.every(h=>h.lane>=0&&h.lane<=sim.laneConfig.maxLane));
 return sim;
}
for(const id of ['tokyo_turf_2000','kyoto_turf_outer_1400']){
 const p=stage.RaceCourseGeometry.get(id),a=stage.RaceCourseGeometry.point(p,p.distance_m-1),b=stage.RaceCourseGeometry.point(p,p.distance_m+1);
 assert((b.x-a.x)*(p.turn==='右'?-1:1)>0,'physical finish direction');
 const wins={};
 for(let seed=1;seed<=8;seed++){
  const a=race(id,seed),b=race(id,seed);
  const style=a.standings()[0].style;wins[style]=(wins[style]||0)+1;
  assert.deepEqual(a.standings().map(x=>[x.number,x.finishTime]),b.standings().map(x=>[x.number,x.finishTime]),'reproducible seed');
 }
 if(p.turn==='右'){
  assert((wins.nige||0)<8&&Object.keys(wins).length>=2,'no scripted escape monopoly');
 }
 console.log('PASS_SIM_STAGE_V020',id,JSON.stringify(wins));
}
const src=fs.readFileSync(root+'race-simulator.js','utf8'),match=src.match(/function goalScreenPosition\([^]*?\n\}/);
assert(match,'goal-screen projection present');
const fn=vm.runInNewContext(match[0]+';goalScreenPosition');
for(const turn of ['左','右']){
 const x=turn==='右'?300:700,dir=turn==='右'?-1:1;
 const a=fn(999,2,1000,1000,470,8,turn),b=fn(1001,2,1000,1000,470,8,turn);
 assert((a.x-x)*dir<0&&(b.x-x)*dir>0,'goal camera keeps right/left course direction');
}
console.log('PASS_SIM_STAGE_V020_DIRECTION');
