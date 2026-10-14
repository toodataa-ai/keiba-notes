/* Staging v0.31 timing, splits, podium in real on-track crossing order. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const dir='docs/staging/',app={};
for(const name of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js']){
 vm.runInNewContext(fs.readFileSync(dir+name,'utf8'),{window:app,globalThis:app});
}
const source=fs.readFileSync(dir+'race-simulator.js','utf8');
const f=source.match(/function dur\(t\)\{[\s\S]*?\n\}/);
const p=source.match(/function firstThree\(state\)\{[\s\S]*?\n\}/);
assert.ok(f&&p);
const format=vm.runInNewContext(f[0]+';dur');
const podium=vm.runInNewContext(p[0]+';firstThree');
for(const [t,expected] of [
 [0,'0.0'],[59.99,'59.9'],[60,'1.00.0'],[62.39,'1.02.3'],
 [119.95,'1.59.9'],[120,'2.00.0'],[123.89,'2.03.8']])
 assert.equal(format(t),expected,'racing format '+t);
const styles=['nige','nige','senko','senko','senko','senko',
 'sashi','sashi','sashi','sashi','sashi','sashi',
 'oikomi','oikomi','oikomi','oikomi','unknown','unknown'];
const horses=styles.map((style,i)=>({number:i+1,name:'runner'+(i+1),style,mark:'△',
 grade:'B',win_pct:5.5,pace_grade:'B',factorGrades:Array(9).fill('B'),recentRuns:[]}));
for(const [id,splitD] of [['tokyo_turf_2000',1000],['kyoto_turf_outer_1400',600]]){
 const course=app.RaceCourseGeometry.get(id);
 const sim=app.RaceSimEngine.create({id:'splits-'+id,course_id:id,
   venue:course.venue,turn:course.turn,distance_m:course.distance_m,horses},
   {seed:18,pace:'auto',bias:'neutral'});
 let ticks=0,firstAt=null,sawSplit=false,sawFinishChanges=0;
 while(!sim.state.finished&&ticks++<2500){
   const previous=sim.state.leader,before=sim.state.horses.filter(h=>h.finished).length;
   sim.step(.1);
   const now=sim.state.horses.filter(h=>h.finished).length;
   if(previous<splitD&&sim.state.leader>=splitD){
     assert.equal(sim.state.splitDistanceM,splitD);
     assert.ok(sim.state.splitTime<=sim.state.t&&sim.state.splitTime>=sim.state.t-.100001);
     sawSplit=true;
   }
   if(now>before&&before<3){
     const top=podium(sim.state);
     assert.equal(top.length,Math.min(now,3),'podium appears progressively');
     if(firstAt===null)firstAt=top[0].finishTime;
     assert.ok(top.every(h=>h.finishTime<=sim.state.t));
     for(let j=1;j<top.length;j++)assert.ok(top[j-1].finishTime<=top[j].finishTime);
     sawFinishChanges++;
   }
 }
 assert.ok(sim.state.finished&&sawSplit&&sawFinishChanges>0);
 assert.ok(Math.abs(firstAt-sim.state.firstFinishTime)<1e-8);
 assert.ok(sim.state.firstFinishTime<sim.state.t,'winner time before runoff stops');
 assert.equal(podium(sim.state).length,3);
 console.log('PASS_V031_RACING_TIMES',id,splitD,format(sim.state.splitTime),
  format(sim.state.firstFinishTime),podium(sim.state).map(x=>x.name));
}
const html=fs.readFileSync(dir+'race-simulator.html','utf8');
const css=fs.readFileSync(dir+'race-simulator.css','utf8');
assert.ok(html.includes('Stage v0.31'));
assert.ok(html.includes('id="podium"')&&html.includes('id="splitTime"'));
assert.ok(source.includes('state.firstFinishTime??state.t'));
assert.ok(css.includes('.finish-podium')&&css.includes('#elapsed{font-size:'));
console.log('PASS_V031_BROADCAST_CLOCK_PODIUM_SPLITS_UI');
