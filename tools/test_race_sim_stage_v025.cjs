/* Stage v0.25 regression: compact 3-4 abreast PRE-RACE pack, no video trickery.
 * Same frozen source reports as all older simulator tests, no betting changes. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const W={},dir='docs/staging/';
for(const file of ['race-course-geometry-v1.js','race-lane-ai-v1.js','race-runner-style-v1.js','race-ability-model-v1.js','race-sim-engine.js'])
 vm.runInNewContext(fs.readFileSync(dir+file,'utf8'),{window:W,globalThis:W},{filename:file});
const txt=v=>String(v||'').replace(/<[^>]*>/g,'').trim();
function load(file){
 const sections=[...fs.readFileSync(file,'utf8').matchAll(/<section class="page horse-page">([\s\S]*?)<\/section>/g)];
 assert.equal(sections.length,18);
 return sections.map(x=>{
  const q=x[1],h=txt((q.match(/<h1>(.*?)<\/h1>/)||[])[1]);
  const m=h.match(/^(\d+)番\s+(.+?)\s+([◎○▲△×])$/);assert.ok(m);
  const grades=[...(q.match(/<table class="factor-grid">([\s\S]*?)<\/table>/)||[])[1]
    .matchAll(/class="grade [^"]*">([^<]*)<\/span>/g)].map(x=>x[1]);
  assert.equal(grades.length,9);
  const meta=W.RaceRunnerStyle.inferFromLastRace(txt((q.match(/<p class="assessment">([\s\S]*?)<\/p>/)||[])[1]));
  const recentRuns=[...((q.match(/<table class="run-table">([\s\S]*?)<\/table>/)||[])[1]||'').matchAll(/<tr>([\s\S]*?)<\/tr>/g)]
    .map(z=>[...z[1].matchAll(/<td>([\s\S]*?)<\/td>/g)].map(c=>txt(c[1])))
    .filter(a=>a.length===5).slice(0,4).map(a=>({date:a[0],venue:a[1],
      distance_m:Number((a[2].match(/芝(\d+)m/)||[])[1])||null,
      finish:Number((a[3].match(/(\d+)着/)||[])[1])||null}));
  const win=(q.match(/モデル単勝確率[:：]\s*([\d.]+)%/)||[])[1];assert.ok(win);
  return {number:+m[1],name:m[2],mark:m[3],style:meta.style,styleMeta:meta,
   grade:'B',factorGrades:grades,pace_grade:grades[1],win_pct:+win,recentRuns};
 });
}
for(const [id,file] of [
 ['tokyo_turf_2000','docs/reports/2026-10-12-october-stakes-v315-readable-v103.html'],
 ['kyoto_turf_outer_1400','docs/reports/2026-10-12-swan-stakes-v315-readable-v103.html']
]){
 const c=W.RaceCourseGeometry.get(id),field=load(file),snapshots=[];
 for(const seg of c.segments.slice(1)){
  const d=seg.from;
  const a=W.RaceCourseGeometry.point(c,d-1,2),b=W.RaceCourseGeometry.point(c,d,2),
    z=W.RaceCourseGeometry.point(c,d+1,2);
  const first=Math.hypot(b.x-a.x,b.y-a.y),second=Math.hypot(z.x-b.x,z.y-b.y);
  assert.ok(Math.abs(second/first-1)<.035,'no jump in apparent speed at sector '+id+'/'+d);
 }
 for(const seed of [1,2,3,2026]){
  const sim=W.RaceSimEngine.create({id:'v025-'+id,venue:c.venue,turn:c.turn,
   course_id:id,distance_m:c.distance_m,horses:field},{seed,pace:'auto',bias:'neutral'});
  const results={seed};
  for(const mark of [300,800]){
   let steps=0;while(sim.state.leader<mark&&steps++<1800)sim.step(.12);
   const horses=sim.state.horses;
   const inner=horses.filter(h=>h.lane<=3.70).length;
   const laneGroups=[0,1,2,3].map(n=>horses.filter(h=>h.lane>=n&&h.lane<n+1).length);
   const maxLane=Math.max(...horses.map(h=>h.lane));
   assert.ok(inner>=14,'at least 14 of 18 within first 4 horse widths');
   assert.ok(laneGroups.filter(x=>x>=2).length>=3,'not a single-file procession');
   assert.ok(maxLane<=5.5,'no persistent 10+ wide race formation');
   results[mark]={within4:inner,maxLane:+maxLane.toFixed(2),lanes:laneGroups};
  }
  snapshots.push(results);
 }
 console.log('PASS_V025_COMPACT_MULTI_FILE_PACK_AND_SEAM_SPEED',id,JSON.stringify(snapshots));
}
// Reproduce the user's screenshot at Kyoto with 589m remaining: the leader
// has covered 811m, and 18 must be free to merge inside its original lane 3.3.
const kyoto=W.RaceCourseGeometry.get('kyoto_turf_outer_1400');
const field=load('docs/reports/2026-10-12-swan-stakes-v315-readable-v103.html');
let insideBy589=0;
for(const seed of [1,2,3,4,5,6,7,8]){
 const sim=W.RaceSimEngine.create({id:'screen-replay-kyoto-589m',
    course_id:kyoto.id,venue:kyoto.venue,turn:kyoto.turn,
    distance_m:kyoto.distance_m,horses:field},
   {seed,pace:'auto',bias:'neutral'});
 let ticks=0;while(sim.state.leader<811&&ticks++<1900)sim.step(.12);
 assert.ok(ticks<1900,'replay reached 589m to go');
 const h18=sim.state.horses.find(h=>h.number===18);
 assert.ok(h18.preferredLane>=3.2,'outer gate assigned expected baseline lane');
 if(h18.lane<2.7)insideBy589++;
 assert.ok(sim.state.horses.filter(h=>h.lane<=3.7).length>=14,'compact bend formation');
 assert.ok(sim.state.horses.filter(h=>h.lane<.6).length<=10,'avoid single-file rail');
}
assert.ok(insideBy589>=5,'in most replicates #18 joins open inner lanes before the straight');
const prof=W.RaceCourseGeometry.get('kyoto_turf_outer_1400');
const cfg=W.RaceLaneAI.config(prof);
const segment=W.RaceCourseGeometry.metrics(prof,811,3.3);
assert.equal(segment.isFinalStraight,false,'589m remaining is still before home straight');
const open={number:18,d:811,lane:3.3,desiredLane:3.3,preferredLane:3.3,lastChange:-100,finished:false};
assert.equal(W.RaceLaneAI.plan(open,[open],cfg,segment,'neutral',50)?.mode,'inward',
 'clear inward passage beats outer-horse preferredLane');
const innerBlocker={number:12,d:811.2,lane:2.6,finished:false};
const collision={...open};
const selected=W.RaceLaneAI.plan(collision,[collision,innerBlocker],cfg,segment,'neutral',50);
if(selected)assert.ok(W.RaceLaneAI.laneSafe(collision,[collision,innerBlocker],selected.lane,cfg),
 'never pass through the blocking runner');
const html=fs.readFileSync(dir+'race-simulator.html','utf8');
assert.ok(/Stage v0\.\d+/.test(html)&&html.includes('安全な内側の進路'));
console.log('PASS_V025_KYOTO_18_OUTER_ISOLATION_REGRESSION',{insideBy589});
