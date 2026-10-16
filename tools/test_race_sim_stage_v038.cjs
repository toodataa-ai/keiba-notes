/* Stage v0.38: highlight genuine straight overtakes WITHOUT changing
 * horse coordinates, physics, race times or number-driven map positions.
 * Golden results were updated for the explicitly versioned v0.40 shared physics model.
 */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const dir='docs/staging/',W={};
for(const f of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js'])
 vm.runInNewContext(fs.readFileSync(dir+f,'utf8'),{window:W,globalThis:W});
const ui=fs.readFileSync(dir+'race-simulator.js','utf8');
const page=fs.readFileSync(dir+'race-simulator.html','utf8');
function func(name){
 const m=ui.match(new RegExp('function '+name+'\\([^]*?\\n\\}'));
 assert.ok(m,'missing pure view routine '+name);
 return new Function('RaceCourseGeometry',m[0]+';return '+name)(W.RaceCourseGeometry);
}
const project=func('projectRaceNumbers'),recent=func('recentOvertake');
const styles=['nige','nige','senko','senko','senko','senko',
 'sashi','sashi','sashi','sashi','sashi','sashi',
 'oikomi','oikomi','oikomi','oikomi','unknown','unknown'];
const horses=styles.map((style,i)=>({number:i+1,name:'H'+(i+1),style,
 mark:'△',grade:'B',win_pct:5.5,pace_grade:'B',
 factorGrades:Array(9).fill('B'),recentRuns:[]}));
const fixtures=[
 // course, seed, winning horse, winning time, top six numbers in v0.40
 ['tokyo_turf_2000',1,11,121.42463920558448,[11,9,4,5,7,2]],
 ['tokyo_turf_2000',2026,18,121.80322331941704,[18,11,14,9,5,6]],
 ['kyoto_turf_outer_1400',1,6,83.84356987806018,[6,9,8,12,2,10]],
 ['kyoto_turf_outer_1400',2026,8,83.61277934372269,[8,1,3,6,12,2]]
];
let totalSignals=0;
for(const [id,seed,winner,winningTime,topSix] of fixtures){
 const p=W.RaceCourseGeometry.get(id);
 const sim=W.RaceSimEngine.create({id:'visual-test-'+id,course_id:id,
  venue:p.venue,turn:p.turn,distance_m:p.distance_m,horses},{seed});
 assert.equal(sim.state.lastVisualPass,null);
 let checks=0,steps=0;
 while(!sim.state.finished&&steps++<2800){
  const before=new Map(sim.state.horses.map(h=>[h.number,{d:h.d,finished:h.finished}]));
  const stamp=sim.state.lastVisualPass?.t;
  sim.step(.1);
  const pass=sim.state.lastVisualPass;
  if(!pass||pass.t===stamp)continue;
  const attacker=sim.state.horses.find(h=>h.number===pass.attackerNo);
  const victim=sim.state.horses.find(h=>h.number===pass.victimNo);
  assert.ok(before.get(pass.attackerNo).d<before.get(pass.victimNo).d,
   'must originate behind the passed horse');
  assert.ok(attacker.d>victim.d,'must really cross to the front');
  assert.ok(!attacker.finished&&!victim.finished,'no fake after-goal pass');
  assert.ok(pass.t>=0&&pass.t<=sim.state.t,'pass timestamp grounded');
  assert.ok(recent(sim.state)?.attackerNo===pass.attackerNo,'caption is real crossing');
  assert.equal(recent({...sim.state,t:pass.t+2.3},2.2),null,
   'overtake caption expires');
  if(sim.state.firstFinishTime===null)
   assert.ok(recent({...sim.state,goalCamera:true}),
    'keep genuine passing highlight in last 80m goal camera');
  else assert.equal(recent(sim.state),null,'hide pass after winner finishes');
  const focus=sim.state.leadingNo,anchor={x:500,y:370};
  const args=[sim.state.horses,p,{x:300,y:150},5,1000,730,
   focus,sim.state.leadingNo,anchor];
  const base=project(...args),lit=project(...args,pass.attackerNo);
  assert.equal(base.length,18);assert.equal(lit.length,18);
  for(const a of base){
   const b=lit.find(h=>h.number===a.number);
   assert.ok(b,'horse not removed by highlight');
   assert.equal(a.x,b.x,'no fake horizontal overtaking offset');
   assert.equal(a.y,b.y,'no fake vertical overtaking offset');
  }
  assert.equal(lit.at(-1).number,pass.attackerNo,
   'attacker must paint ON TOP of overlapping horses');
  assert.equal(lit.filter(v=>v.passing).length,1);
  checks++;
 }
 assert.ok(sim.state.finished&&checks>=3,'multiple actual passes observed');
 const order=sim.standings();
 assert.equal(order[0].number,winner,'model finishing order not changed');
 assert.ok(Math.abs(order[0].finishTime-winningTime)<1e-7,
  'model elapsed time unchanged, not merely displayed differently');
 assert.deepEqual(order.slice(0,6).map(h=>h.number),topSix,
  'all top-six results preserved');
 assert.ok(sim.state.finalStraightPasses>=checks);
 totalSignals+=checks;
}
assert.ok(totalSignals>=25,'visibility signals should be frequent enough to matter');
assert.ok(ui.includes("const latestPass=recentOvertake(state,2.2);"));
assert.ok(ui.includes('ctx.arc(x,y,radius+7*scale'));
assert.ok(ui.includes('const passingNo=recentOvertake(state)?.attackerNo??null;'),
 'final 80m goal camera must preserve the real-pass highlight');
assert.ok(ui.includes('race.field_size,runner.number===passingNo);'));
assert.ok(ui.includes('target.number,state.leadingNo,anchor,activePass?.attackerNo??null'));
assert.ok(page.includes('race-sim-engine.js?v=20261016-40'));
assert.ok(page.includes('race-simulator.js?v=20261016-39'));
assert.ok(page.includes('Overtake view v0.38'));
console.log('PASS_V038_REAL_OVERTAKES_NO_FAKE_POSITIONS_GOLDEN_RESULTS',totalSignals);
