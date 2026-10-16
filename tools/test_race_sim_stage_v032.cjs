/* Stage-only regression: Tokyo turf 2000m chute must stay on the outer turf
 * pocket of the UmaPot illustration, not cut across its white separator into
 * the adjacent inside course. These are approximate source-image pixels, not
 * surveying/GPS points. No physics, prediction or betting code is involved.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root='docs/staging/',W={};
for(const file of ['race-course-geometry-v1.js','race-umapot-overlay-v1.js']){
 const js=fs.readFileSync(root+file,'utf8').replace('setup();','');
 vm.runInNewContext(js,{window:W,globalThis:W});
}
const overlay=W.RaceUmapotOverlay,geo=W.RaceCourseGeometry;
const t=geo.get('tokyo_turf_2000'),k=geo.get('kyoto_turf_outer_1400');
assert.ok(overlay.validate(t)&&overlay.validate(k));
// Image-space bounds reconstructed against the displayed reference-map turf
// pocket. They intentionally reject the previous inward rail displacement
// at 60–100m, while allowing a safety margin for Bézier interpolation.
const outerPocketCorridor=[
 [0,505,525,273,282],[20,510,526,250,265],
 [40,513,530,231,241],[60,515,533,208,216],
 [80,505,523,185,198],[100,495,511,169,182],
 [120,482,497,159,173],[130,476,494,154,169],
 [150,469,485,147,161],[170,460,477,140,157]
];
for(const [d,xmin,xmax,ymin,ymax] of outerPocketCorridor){
 const pts=[0,4,8].map(lane=>overlay.point(t,d,lane));
 for(const [i,p] of pts.entries()){
  assert.ok(p.x>=xmin&&p.x<=xmax&&p.y>=ymin&&p.y<=ymax,
   'TOKYO_2000_CHUTE_WHITE_SEPARATOR '+d+'m lane '+[0,4,8][i]+
   ' at '+p.x.toFixed(2)+','+p.y.toFixed(2));
 }
 assert.ok(pts[0].x<pts[1].x&&pts[1].x<pts[2].x,
  'Tokyo pocket must retain stable inside-to-outside lane order '+d);
}
// No on-screen teleportation when crossing any new registration anchor or
// rejoining the legacy main-course lane guide.
for(const lane of [0,4,8]){
 for(let d=1;d<=300;d++){
  const a=overlay.point(t,d-1,lane),b=overlay.point(t,d,lane);
  assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<3,
   'TOKYO_2000_CHUTE_DISCONTINUITY '+d+'m lane '+lane);
 }
}
// The common-course geometry and all Kyoto reference positions must remain
// unchanged. Kyoto expected coordinates were pinned before this fix.
const kyotoReference=[
 [0,225.04556,159.84737],[365,454.42499,115.93116],
 [570,560.55047,165.02295],[700,568.49338,249.60808],
 [996.3,453.96177,322.91013],[1400,290.00286,318.92]
];
for(const [d,x,y] of kyotoReference){
 const p=overlay.point(k,d,4);
 assert.ok(Math.abs(p.x-x)<.001&&Math.abs(p.y-y)<.001,
  'KYOTO_REGRESSION '+d+'m');
}
assert.equal(overlay.outwardShiftPx(t,675),0);
const html=fs.readFileSync(root+'race-simulator.html','utf8');
// Existing stage page already uses the Kyoto inner/outer shared image overlay.
assert.ok(html.includes('race-umapot-overlay-v1.js?v=20261016-43'));
assert.ok(html.includes('東京芝2000mの引き込み線'));
assert.ok(html.includes('Stage v0.31'));
console.log('PASS_V032_TOKYO_2000_OUTER_TURF_CHUTE_30_MARKERS_WHITE_GAP_CLEAR');
console.log('PASS_V032_TOKYO_CHUTE_CONTINUITY_AND_KYOTO_UNCHANGED');
