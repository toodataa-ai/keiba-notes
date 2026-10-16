/* Stage v0.37: eliminate false Kyoto 4C climb/dip from interpolation.
 * This validates SOURCE IMAGE registration, not a replacement for the actual
 * Kyoto three-corner ascent and descent in race physics.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const base='docs/staging/',W={},doc={getElementById:()=>null,querySelector:()=>null};
for(const p of ['race-course-geometry-v1.js','race-umapot-overlay-v1.js']){
 vm.runInNewContext(fs.readFileSync(base+p,'utf8').replace('setup();',''),
   {window:W,globalThis:W,document:doc});
}
const geo=W.RaceCourseGeometry,over=W.RaceUmapotOverlay;
const k=geo.get('kyoto_turf_outer_1400'),t=geo.get('tokyo_turf_2000');
assert.ok(over.validate(k)&&over.validate(t));
const registered=[
 [775,43],[805,45],[830,52],[860,46],[890,36],[920,25],
 [950,16],[970,13],[996.3,10]
];
for(const [d,pixels] of registered)
 assert.ok(Math.abs(over.outwardShiftPx(k,d)-pixels)<.00001,
   'registered outer turf anchor unchanged at '+d);
// Turning-point continuity, not just positional continuity. The previous
// smoothstep interpolation forced 0 slope at each control knot and repeatedly
// twisted the velocity vector at 805, 830, 860, 890, 920 and 950m.
const heading=d=>{
 const a=over.point(k,d-.25,0),b=over.point(k,d+.25,0);
 return Math.atan2(b.y-a.y,b.x-a.x);
};
const angleDelta=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
let maxCurvature=0,maxWobble=0,totalTurn=0;
for(let d=800;d<=970;d++){
 const prev=heading(d-1),now=heading(d),next=heading(d+1);
 const left=angleDelta(now,prev),right=angleDelta(next,now);
 const curvature=Math.abs(right)*180/Math.PI;
 const second=Math.abs(right-left)*180/Math.PI;
 maxCurvature=Math.max(curvature,maxCurvature);
 maxWobble=Math.max(maxWobble,second);
 totalTurn+=curvature;
 // Explicitly retain inside/outside lane width and track alignment.
 const a=over.point(k,d,0),b=over.point(k,d,4);
 assert.ok(a.x>=440 && Math.hypot(b.x-a.x,b.y-a.y)>8, 'Kyoto outside turf and lane clearance at '+d);
}
assert.ok(maxCurvature<6.7,'4C course heading still jerks by '+maxCurvature+' degrees/m');
assert.ok(maxWobble<4.9,'4C artificial up-down twist '+maxWobble);
assert.ok(totalTurn/171<1.5,'4C repeated pitch wobble '+totalTurn/171);
// The stage-only image offset MUST NOT rewrite any 3C hill gradient.
assert.ok(geo.height(k,575)>geo.height(k,850));
assert.ok(geo.slope(k,700)<0);
for(const d of [0,60,130,570,675,830,970,1500,2000]){
 const original=over.point(t,d,0);
 assert.ok(Number.isFinite(original.x)&&Number.isFinite(original.y));
 assert.equal(over.outwardShiftPx(t,d),0,'Tokyo untouched');
}
const html=fs.readFileSync(base+'race-simulator.html','utf8');
assert.ok(html.includes('race-umapot-overlay-v1.js?v=20261015-37'));
assert.ok(html.includes('Kyoto curve v0.37'));
console.log('PASS_V037_KYOTO_4C_SMOOTH_OUTER_BEND',
 'mean heading change', (totalTurn/171).toFixed(2), 'maximum wobble',maxWobble.toFixed(2));
