/* v0.30: Prevent Kyoto outer A-course 1400 horses from appearing on
 * inner-course side of the WHITE source-image separator mid-corner.
 * Coordinates measured from 620x430 Umapot JPG. Display-only test.
 */
'use strict';
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const W={},d='docs/staging/';
for(const name of ['race-course-geometry-v1.js','race-umapot-overlay-v1.js'])
 vm.runInNewContext(fs.readFileSync(d+name,'utf8').replace('setup();',''),
  {window:W,globalThis:W,document:{getElementById:()=>null,querySelector:()=>null}});
const k=W.RaceCourseGeometry.get('kyoto_turf_outer_1400');
const t=W.RaceCourseGeometry.get('tokyo_turf_2000');
assert.ok(W.RaceUmapotOverlay.validate(k));
assert.ok(W.RaceUmapotOverlay.validate(t));
// Measured per-row edge of WHITE separator and outside grass. Lane0 must
// CLEAR the divider; lane4 must remain within outer green stripe.
// [progress metres, approximate WHITE outer border x, outer grass edge x].
const bands=[
 [570,540,567],[600,548,573],[650,552,575],[675,551,575],
 [700,550,574],[725,548,573],[750,546,569],[775,541,564],
 [805,534,559],[830,530,555]
];
for(const [progress,separatorEnd,outerEdge] of bands){
 const inside=W.RaceUmapotOverlay.point(k,progress,0);
 const out4=W.RaceUmapotOverlay.point(k,progress,4);
 assert.ok(inside.x-separatorEnd>=8,
  'INNER_COURSE_WHITESPLIT_OVERLAP d='+progress+' x='+inside.x);
 assert.ok(out4.x<=outerEdge+2,
  'OUTSIDE_TURF_IMAGE_EDGE d='+progress+' x='+out4.x);
 assert.ok(out4.x>inside.x+4,'outerward lane orientation at d='+progress);
}
// The white separator fades after ~750m; at 890m+ the tangent swings
// towards the bottom straight so x itself decreases on the correct outer
// green stripe. Bounds use the image's lower straight, not the bend x-values.
for(const [progress,minimumX] of [
 [700,558],[725,556],[750,555],[775,550],[805,540],
 [830,533],[860,514],[890,500],[920,483]
]){
 assert.ok(W.RaceUmapotOverlay.point(k,progress,0).x>=minimumX,
  'LATE_TURN_CUTS_INSIDE d='+progress);
}
for(const lane of [0,2,4]){
 for(let v=500;v<=1100;v+=.5){
  const before=W.RaceUmapotOverlay.point(k,v-.2,lane);
  const after=W.RaceUmapotOverlay.point(k,v+.2,lane);
  assert.ok(Math.hypot(after.x-before.x,after.y-before.y)<.36,
   'VISUAL_TRAJECTORY_JERK d='+v);
 }
}
assert.equal(W.RaceUmapotOverlay.outwardShiftPx(t,675),0,'Tokyo unchanged');
const html=fs.readFileSync(d+'race-simulator.html','utf8');
assert.ok(/Stage v0\.\d+/.test(html)&&html.includes('白い内外分離線より外側'));
console.log('PASS_V030_KYOTO_OUTER_RAIL_CLEARANCE_AND_NO_INNER_SHORTCUT');
