/* Kyoto A-course 1400 OUTER: image-registered outer circuit only.
 * Fail if overlay shortcuts through inner green ribbon between 3rd/4th bends.
 * Original Umapot asset sampled as 620x430; registration is display-only.
 */
'use strict';
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const W={},dir='docs/staging/';
vm.runInNewContext(fs.readFileSync(dir+'race-course-geometry-v1.js','utf8'),{window:W,globalThis:W});
vm.runInNewContext(fs.readFileSync(dir+'race-umapot-overlay-v1.js','utf8').replace('setup();',''),
 {window:W,globalThis:W,document:{getElementById:()=>null,querySelector:()=>null}});
const k=W.RaceCourseGeometry.get('kyoto_turf_outer_1400'),t=W.RaceCourseGeometry.get('tokyo_turf_2000');
assert.equal(W.RaceUmapotOverlay.validate(k),true);
assert.equal(W.RaceUmapotOverlay.validate(t),true);
// Individual outer-track pixels verified on the original Umapot 620x430 JPG.
const stripe=[
// distance d, minimum X to keep lane 0 on the OUTER green turn,
 [570,540],[600,545],[650,550],[675,550],[700,550],
 [725,546],[750,541],[775,535],[805,525],[830,515]
];
for(const [d,minX] of stripe){
 const inRail=W.RaceUmapotOverlay.point(k,d,0);
 const lane4=W.RaceUmapotOverlay.point(k,d,4);
 assert.ok(inRail.x>=minX,'INNER-COURSE-SHORTCUT at '+d+'m: '+inRail.x);
 assert.ok(lane4.x>inRail.x+4,'outside lane must sit further outside on right turn');
}
for(const d of [365,445,500,540,570,600,650,675,700,725,750,775,805,830,860,890,920,950,970,996.3]){
 for(const lane of [0,1,4]){
  const p=W.RaceUmapotOverlay.point(k,d,lane);
  assert.ok(p.x>=160&&p.x<=590&&p.y>=90&&p.y<=345,'mapped outside original source');
  const a=W.RaceUmapotOverlay.point(k,d-.08,lane);
  const b=W.RaceUmapotOverlay.point(k,d+.08,lane);
  assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<.30,'no corner splice jerk at '+d);
 }
}
assert.equal(W.RaceUmapotOverlay.outwardShiftPx(t,675),0,'Tokyo registration untouched');
const html=fs.readFileSync(dir+'race-simulator.html','utf8');
assert.ok(html.includes('Stage v0.29')&&html.includes('外回りの芝帯上'));
assert.ok(!html.includes('id="courseMapMode"')&&!html.includes('id="pathToggle"'));
console.log('PASS_V029_KYOTO_OUTER_ONLY_IMAGE_STRIPE_AND_SEAM_CONTINUITY');
