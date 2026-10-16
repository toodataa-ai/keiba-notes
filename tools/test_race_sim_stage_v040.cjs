/* Stage v0.40 – shared slope/energy-dependent late-closing regression.
 * This test never uses official post-race outcomes as simulation inputs.
 * Winning orders may legitimately change from v0.39; time is the actual
 * physical wire-crossing instant, not corrected after the race.
 */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root='docs/staging/',W={};
for(const f of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js']){
 vm.runInNewContext(fs.readFileSync(root+f,'utf8'),{window:W,globalThis:W});
}
const E=W.RaceSimEngine,G=W.RaceCourseGeometry;
const tokyo=G.get('tokyo_turf_2000'),kyoto=G.get('kyoto_turf_outer_1400');
assert.equal(E.closingTurnOpportunity(tokyo),0,'do not compound Tokyo closers');
assert.ok(E.closingTurnOpportunity(kyoto)>.95,'Kyoto downhill momentum modeled from course altitudes');
const good={style:'sashi',six:{burst:57,sustain:57,acceleration:57}};
const poor={style:'sashi',six:{burst:39,sustain:39,acceleration:39}};
const runaway={style:'nige',six:{burst:57,sustain:57,acceleration:57}};
const nearFinish=75,early=800;
assert.equal(E.closingTurnResponse(good,nearFinish,tokyo,'H'),0);
assert.equal(E.closingTurnResponse(runaway,nearFinish,kyoto,'H'),0);
assert.equal(E.closingTurnResponse(good,early,kyoto,'H'),0);
assert.ok(E.closingTurnResponse(good,nearFinish,kyoto,'H')>
 E.closingTurnResponse(poor,nearFinish,kyoto,'H'),
 'good late kick must matter more than style label alone');
assert.ok(E.closingTurnResponse(good,nearFinish,kyoto,'H')>
 E.closingTurnResponse(good,nearFinish,kyoto,'S'),
 'a genuine contested pace favors a remaining late reserve');
assert.ok(E.closingTurnResponse(good,nearFinish,kyoto,'H')<=.32+1e-9,
 'maximum extra speed must stay strictly bounded');
const styles=['nige','nige','senko','senko','senko','senko',
 'sashi','sashi','sashi','sashi','sashi','sashi',
 'oikomi','oikomi','oikomi','oikomi','unknown','unknown'];
const horses=styles.map((style,i)=>({number:i+1,name:'runner'+(i+1),style,
 mark:'△',grade:'B',win_pct:5.5,pace_grade:'B',
 factorGrades:Array(9).fill('B'),recentRuns:[]}));
const results=[];
for(const p of [tokyo,kyoto]){
 let runs=0,pairs=0,frontWins=0,backWins=0;
 for(const seed of [1,4,7,18,31,77,2026]){
  const race={id:'v040-'+p.id,course_id:p.id,venue:p.venue,
   turn:p.turn,distance_m:p.distance_m,horses};
  const sim=E.create(race,{seed,pace:'auto',bias:'neutral'});
  let steps=0;while(!sim.state.finished&&steps++<2800)sim.step(.1);
  assert.ok(sim.state.finished,'18 horses complete and pass goal');
  const order=sim.standings();
  assert.ok(order.every(x=>Number.isFinite(x.finishTime)&&x.finished));
  assert.ok(order.slice(1).every((x,i)=>x.finishTime>=order[i].finishTime));
  assert.ok(Math.abs(sim.state.firstFinishTime-order[0].finishTime)<1e-8);
  const rank=sim.state.straightEntryOrder.indexOf(order[0].number)+1;
  frontWins+=rank===1;
  backWins+=rank>=5;
  pairs+=sim.state.finalStraightPasses;
  runs++;
 }
 assert.ok(pairs>runs*6,'genuine overtakes remain possible on '+p.id);
 results.push({course:p.id,runs,frontWins,backWins,realPasses:pairs});
}
const html=fs.readFileSync(root+'race-simulator.html','utf8');
const source=fs.readFileSync(root+'race-sim-engine.js','utf8');
assert.ok(source.includes('closingTurnOpportunity(profile)'));
assert.ok(source.includes('closingTurnResponse(h,remaining,profile,pace)'));
assert.ok(html.includes('race-sim-engine.js?v=20261016-41'));
assert.ok(html.includes('Closing balance v0.40'));
assert.ok(html.includes('瞬発力・持続力・加速特性'));
console.log('PASS_V040_GENERIC_TERRAIN_CLOSING_CONTEST_NO_TARGET_RANK',JSON.stringify(results));
