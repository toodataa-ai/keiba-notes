/* Synthetic mathematical fixtures only; no publisher source coordinates. */
'use strict';const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),g={};
vm.runInNewContext(fs.readFileSync('docs/lab/race-tokyo-source-audit-v2.js','utf8'),{window:g});
const src={courseId:'tokyo_turf_2000',sourcePptxSha256:g.RaceTokyoSourceAudit.PPTX_SHA,
 sourceSvgSha256:'a'.repeat(64),canAnimate:false,distanceAnchorsSurveyed:false,width:620,height:620*9/13,
 maxLane:16,laneOffset:9,discRadius:.6,strokeWidth:24,sections:[
 {from:0,to:100,kind:'line',points:[[470,300],[470,150]]},
 {from:100,to:300,kind:'cubic',points:[[470,150],[470,120],[440,100],[400,100]]},
 {from:300,to:900,kind:'line',points:[[400,100],[180,100]]},
 {from:900,to:1145,kind:'arc',center:[180,150],radius:50,angles:[-Math.PI/2,-Math.PI]},
 {from:1145,to:1474.1,kind:'arc',center:[180,150],radius:50,angles:[-Math.PI,-3*Math.PI/2]},
 {from:1474.1,to:2000,kind:'line',points:[[180,200],[300,200]]},
 {from:2000,to:2120,kind:'line',points:[[300,200],[300+120*120/525.9,200]]}]};
const route=g.RaceTokyoSourceAudit.build(src);assert.equal(route.canAnimate,false);
assert.ok(route.point(0,0).x<route.center(0).x,'LEFT_TURN_INNER_IS_WEST_ON_CHUTE');
assert.ok(route.point(500,0).y>route.center(500).y,'LEFT_TURN_INNER_IS_SOUTH_ON_BACKSTRETCH');
let last=-1;
for(let d=0;d<=2120;d+=.25){const s=route.arcAt(d);assert.ok(s>last);last=s;for(let lane=0;lane<=16;lane++)assert.ok(Number.isFinite(route.point(d,lane).x));}
for(const d of [100,300,900,1145,1474.1,2000]){
 const a=route.point(d-.0001,8),b=route.point(d+.0001,8);assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<.001);
}
for(let lane=0;lane<=16;lane++)for(let d=301;d<899;d++)assert.ok(Math.abs(route.point(d,lane).y-route.point(301,lane).y)<.00001);
for(const change of [{maxLane:14},{canAnimate:true},{width:621},{sourcePptxSha256:'b'.repeat(64)},{strokeWidth:Infinity}])
 assert.throws(()=>g.RaceTokyoSourceAudit.build({...src,...change}),/INVALID/);
for(const [d,lane] of [[-1,8],[2121,8],[100,17],[NaN,8]])assert.throws(()=>route.point(d,lane),/OUT_OF_RANGE/);
// The built mapping owns its sampled geometry and is not changed by caller edits.
const before=JSON.stringify(route.point(300,8));src.sections[2].points[0][0]=0;assert.equal(JSON.stringify(route.point(300,8)),before);
console.log('PASS Tokyo source-local mathematical mapping, monotonicity, 16-lane bounds, invalid-input rejection; source/playback approval remains false');
