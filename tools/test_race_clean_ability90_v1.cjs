'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root='docs/lab/',window={};
for(const name of ['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1',
 'race-ability-model-v1','race-cohort-speed-v1','race-sim-engine',
 'race-lab-18-fixture-v1','race-real-shuka-2026-fixture-v1','race-clean-goal-view-v1'])
 vm.runInNewContext(fs.readFileSync(root+name+'.js','utf8'),{window,globalThis:window});
const clean=x=>JSON.parse(JSON.stringify(x));
const fixtures={synthetic:window.RaceLab18Fixture,shuka2026:window.RaceRealShuka2026Fixture};
const keys=['early','cruise','burst','sustain','stamina','acceleration'];
const comparison=[];
function entry(trial,ability){
 const f=fixtures[trial];return {...f.entry(),horses:f.horses({abilityScale:ability}),
  ...(ability==='90-v1'?{labAbilityScale:ability}:{})};
}
function run(trial,ability,span=100,seed=2026){
 const data=entry(trial,ability),input=JSON.stringify(data);
 const sim=window.RaceSimEngine.create(data,{seed,bias:'neutral'}),signs=new Map();
 const milestones={},pairCounts={all:0,after1000:0,finalStraight:0};
 for(let tick=0;tick<4000&&!sim.state.finished;tick++){
  sim.step(.08);const s=sim.state,active=s.horses.filter(h=>!h.finished);
  for(let i=0;i<active.length;i++)for(let j=i+1;j<active.length;j++){
   const a=active[i],b=active[j],gap=a.d-b.d,k=a.number+':'+b.number;
   if(Math.abs(gap)<.25)continue;
   const sign=Math.sign(gap),previous=signs.get(k);
   if(previous!==undefined&&sign!==previous&&s.leader>100){
    pairCounts.all++;if(s.leader>1000)pairCounts.after1000++;
    if(s.leader>1671.6)pairCounts.finalStraight++;
   }signs.set(k,sign);
  }
  for(const d of [1000,1920,1950,1980,2000])if(!milestones[d]&&s.leader>=d){
   const ds=s.horses.map(h=>h.displayD),leader=Math.max(...ds);
   const positions=s.horses.map(h=>({number:h.number,...window.RaceCleanGoalView.goalScreenPosition(
    h.displayD,h.lane,2000,368,356,14,'右',1,span)}));
   const visible=positions.filter(p=>p.x>=-10.935&&p.x<=378.935);
   const pairs=threshold=>visible.reduce((n,a,i)=>n+visible.slice(i+1).filter(b=>Math.hypot(a.x-b.x,a.y-b.y)<threshold).length,0);
   milestones[d]={leader,packGapM:leader-Math.min(...ds),within10m:ds.filter(x=>leader-x<=10).length,
    visible:visible.length,touching:pairs(21.87),severe:pairs(12.0285)};
  }
 }
 assert(sim.state.finished);assert.equal(JSON.stringify(data),input,'input data must stay immutable');
 const order=sim.standings();
 return {trial,ability,span,seed,splitTime:sim.state.splitTime,winnerTime:order[0].finishTime,
  lastTime:order.at(-1).finishTime,engineFinalStraightPasses:sim.state.finalStraightPasses,pairCounts,milestones,
  results:order.map(h=>({number:h.number,time:h.finishTime,gap:h.finishTime-order[0].finishTime})),
  abilities:sim.state.horses.map(h=>({number:h.number,style:h.style,
   values:clean(h.abilityProfile.displaySix||h.six),physics:clean(h.six)}))};
}
for(const trial of Object.keys(fixtures)){
 const legacy=run(trial,'legacy-50'),modern=run(trial,'90-v1');
 assert.deepEqual(modern,run(trial,'90-v1'),'same seed must reproduce every metric');
 for(const ability of ['legacy-50','90-v1']){
  const a=run(trial,ability,100),b=run(trial,ability,290);
  assert.deepEqual(a.results,b.results,'camera must never change results');
  assert.equal(a.splitTime,b.splitTime);assert.deepEqual(a.pairCounts,b.pairCounts);
  assert.equal(a.milestones[1920].visible,0,'100m span starts offscreen');
  comparison.push(a,b);
  console.log('ABILITY90_COMPARISON',JSON.stringify(a));
  console.log('ABILITY90_COMPARISON',JSON.stringify(b));
 }
 const scores=modern.abilities.flatMap(h=>Object.values(h.values));
 assert(scores.every(v=>v>=82&&v<=98));
 const mean=scores.reduce((a,b)=>a+b,0)/scores.length;assert(mean>=88&&mean<=93);
 if(trial==='shuka2026'){
  assert.deepEqual(modern.results,legacy.results,'prestart grade conversion preserves race results');
  assert.equal(modern.splitTime,legacy.splitTime);
 }else{
  assert.equal(new Set(modern.abilities.map(h=>JSON.stringify(h.values))).size,18);
  assert(modern.abilities.filter(h=>h.style==='nige').every(h=>h.values.early>h.values.burst));
  assert(modern.abilities.filter(h=>h.style==='oikomi').every(h=>h.values.burst>h.values.early));
  assert(modern.pairCounts.finalStraight>0,'late runners must still contest positions');
 }
 assert(Math.abs(modern.splitTime-legacy.splitTime)<3,'no blanket speed boost at 1000m');
 assert(Math.abs(modern.winnerTime-legacy.winnerTime)<3,'no blanket finishing-time collapse');
 assert.notDeepEqual(run(trial,'90-v1',100,2027).results,modern.results,'seed still affects race variation');
}
// A neutral 90 profile feeds the exact old neutral 50 values to all engine
// terms (including stamina and downhill response), without engine changes.
const neutral=entry('synthetic','90-v1');neutral.horses[0].labAbility90=Object.fromEntries(keys.map(k=>[k,90]));
const profile=window.RaceSimAbility.profile(neutral.horses[0],neutral,0);
assert(keys.every(k=>profile.six[k]===50&&profile.displaySix[k]===90));
for(const course of ['kyoto_turf_outer_1400','tokyo_turf_2000']){
 const h=neutral.horses[0],race={...neutral,course_id:course};
 const modern=clean(window.RaceSimAbility.profile(h,race,0));
 const legacy=clean(window.RaceSimAbility.profile(h,{...race,labAbilityScale:undefined},0));
 const {displaySix,scale,neutral:centre,legacyPointsPerScore,...physics}=modern;
 assert.deepEqual(physics,legacy,'common display must preserve all physical terms and evidence');
 assert.equal(centre,90);assert.equal(scale,'90-v1');
 assert(keys.every(k=>displaySix[k]===90&&modern.six[k]===50));
 assert.equal(legacy.displaySix,undefined,'old callers keep opt-in isolation');
}
console.log('PASS_LAB_ABILITY90_NEUTRAL_REPRODUCIBLE_CAMERA_INDEPENDENT_SHARED_DISPLAY_PHYSICS_UNCHANGED');
if(process.env.LAB_QA_JSON)fs.writeFileSync(process.env.LAB_QA_JSON,JSON.stringify({
 seed:2026,stepSeconds:.08,metrics:comparison},null,2)+'\n');

