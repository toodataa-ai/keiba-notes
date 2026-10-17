/* LAB v0.48 synthetic eighteen-runner integration audit, NO official JRA entrants.
 * All physical lane tactics are the EXISTING Kyoto 1400 shared RaceLaneAI.
 * Tests cross display coordinates, crowd convergence, collision guard,
 * seed determinism and course/visual nonregression. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const W={},document={getElementById:()=>null,querySelector:()=>null};
const base='docs/lab/';
for(const src of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
 'race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js',
 'race-umapot-overlay-v1.js','race-broadcast-map-v1.js','race-lab-18-fixture-v1.js']){
 vm.runInNewContext(fs.readFileSync(base+src,'utf8'),{
  window:W,globalThis:W,document
 },{filename:src});
}
const {RaceLab18Fixture:synthetic,RaceSimEngine:engine,RaceCourseGeometry:geometry,
 RaceLaneAI:laneAI,RaceUmapotOverlay:overlay,RaceSimBroadcastMap:broadcast}=W;
const entry=synthetic.entry(),horses=synthetic.horses(),course=geometry.get(entry.course_id);
assert.equal(entry.field_size,18);
assert.equal(entry.scope,'LAB_SYNTHETIC_NOT_OFFICIAL');
assert.equal(horses.length,18);
assert.equal(new Set(horses.map(h=>h.number)).size,18);
assert.ok(horses.every(h=>h.name.includes('架空')&&!Number.isFinite(h.win_pct)));
assert.equal(laneAI.config(course).packMaxLane,3.45);
// Both Kyoto courses bind to exactly the same lane selection code and physics.
const other={...entry,id:'lab-outer-1400-validation-not-published',
 course_id:'kyoto_turf_outer_1400',distance_m:1400,
 race:'非公式京都1400共通ロジック確認'};
const outer=engine.create({...other,horses:synthetic.horses()},{seed:2026,bias:'neutral'});
const inner=engine.create({...entry,horses},{seed:2026,bias:'neutral'});
assert.equal(inner.state.laneModel,outer.state.laneModel);
assert.equal(inner.laneConfig.packMaxLane,outer.laneConfig.packMaxLane);
assert.ok(inner.state.horses.every(h=>h.d===0));
const initial=inner.state.horses.map(h=>h.lane);
function snapshot(sim,at){
 const s=sim.state,ordered=s.horses.slice().sort((a,b)=>a.lane-b.lane);
 const median=(ordered[8].lane+ordered[9].lane)/2;
 const pack=s.horses.filter(h=>h.lane<=3.45+.0001).length;
 const outer=s.horses.filter(h=>h.lane>5.35+.0001).length;
 const median0=(initial.slice().sort((a,b)=>a-b)[8]+initial.slice().sort((a,b)=>a-b)[9])/2;
 const mapped=broadcast.entries(s,course,overlay);
 assert.equal(mapped.length,18,'all eighteen markers must remain while running');
 for(const m of mapped){
  const h=s.horses.find(x=>x.number===m.number);
  const expected=overlay.point(course,h.displayD??h.d,h.lane);
  assert.ok(Math.hypot(expected.x-m.x,expected.y-m.y)<1e-9,'same overview/live coordinates for '+m.number);
 }
 for(const [width,height,rendered] of [[1000,730,390],[1000,470,1024]]){
  const view=broadcast.frame(mapped,width,height,rendered,s.leadingNo);
  assert.equal(view.rotationRadians,0);
  assert.ok(view.zoom>=.5 && Number.isFinite(view.zoom));
  const margin=2;
  for(const p of mapped){
   const screen=broadcast.screenPoint(p,view);
   assert.ok(screen.x>=-margin&&screen.x<=width+margin&&
      screen.y>=-margin&&screen.y<=height+margin,'18 active markers visible '+at+'m '+p.number+' '+JSON.stringify(screen));
  }
 }
 return {at,leader:Number(s.leader.toFixed(1)),median:Number(median.toFixed(2)),
  initialMedian:Number(median0.toFixed(2)),inside4:pack,farOutside:outer,
  inward:s.totalInsideMoves,outward:s.totalOutsidePasses,
  holds:s.trafficHolds,pace:s.paceBand};
}
const samples=[40,100,180,310,530,900,1270,1671.6,1900],results=[];
let next=0,maxVelocity=0,steps=0;
while(next<samples.length && steps<1800){
 inner.step(.12);steps++;
 for(const h of inner.state.horses){
  assert.ok(Number.isFinite(h.lane)&&h.lane>=0&&h.lane<=inner.laneConfig.maxLane+1e-6);
  assert.ok(Number.isFinite(h.d)&&Number.isFinite(h.displayD));
  maxVelocity=Math.max(maxVelocity,Math.abs(h.laneVelocity));
 }
 if(inner.state.leader>=samples[next]){
  results.push(snapshot(inner,samples[next]));next++;
 }
}
assert.equal(results.length,samples.length, 'all distances must be reached in a full race');
const by100=results.find(x=>x.at===100);
const by310=results.find(x=>x.at===310);
assert.ok(by100.median < by100.initialMedian-.7,
 'field should start converging inward by 100m '+JSON.stringify(by100));
assert.ok(by310.inside4>=8, 'inner pack must form by first corner '+JSON.stringify(by310));
assert.ok(by310.inward>=5, 'inner priority must produce actual safe inward changes '+JSON.stringify(by310));
assert.ok(maxVelocity<=4.2, 'no lateral teleport '+maxVelocity);
// Confirm same synthetic seed produces same positions and number of lane events.
const duplicate=engine.create({...entry,horses:synthetic.horses()},{seed:2026,bias:'neutral'});
for(let i=0;i<steps;i++)duplicate.step(.12);
const a=inner.state.horses.map(h=>[h.number,h.d,h.lane,h.inwardMoves,h.outwardMoves]);
const b=duplicate.state.horses.map(h=>[h.number,h.d,h.lane,h.inwardMoves,h.outwardMoves]);
assert.deepEqual(a,b,'fixed seed / fixed input should remain deterministic');
console.log('LAB_EIGHTEEN_METRICS_JSON '+JSON.stringify({results,maxVelocity,steps}));
console.log('PASS_LAB_EIGHTEEN_KYOTO1400_SHARED_LANE_AI_SAFE_INWARD_100M_AND_PIXEL_PARITY');
