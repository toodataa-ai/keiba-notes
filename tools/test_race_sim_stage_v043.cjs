/* Stage Kyoto inner 2000m: reuse ORIGINAL Umapot image, calibrate
 * number overlay only. Physics and original outer 1400m stays unchanged.
 */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root='docs/staging/',W={},document={
 getElementById:()=>null,querySelector:()=>null
};
for(const p of ['race-course-geometry-v1.js'])
 vm.runInNewContext(fs.readFileSync(root+p,'utf8'),{window:W,globalThis:W});
vm.runInNewContext(fs.readFileSync(root+'race-umapot-overlay-v1.js','utf8'),
 {window:W,globalThis:W,document});
const html=fs.readFileSync(root+'race-simulator.html','utf8');
const js=fs.readFileSync(root+'race-simulator.js','utf8');
const overlay=fs.readFileSync(root+'race-umapot-overlay-v1.js','utf8');
const kyoto=W.RaceCourseGeometry.get('kyoto_turf_inner_2000');
const oldKyoto=W.RaceCourseGeometry.get('kyoto_turf_outer_1400');
const tokyo=W.RaceCourseGeometry.get('tokyo_turf_2000');
assert.ok(W.RaceUmapotOverlay.validate(kyoto));
assert.ok(W.RaceUmapotOverlay.validate(oldKyoto));
assert.ok(W.RaceUmapotOverlay.validate(tokyo));
assert.equal(kyoto.segments.length,7);
const expected=[
 [0,349.5,312],[100,291.2,310],[310,170.6,301.7],
 [530,157.7,203.3],[720,187.1,156.3],[1000,318.4,141.7],
 [1270,462.2,137],[1435,510.1,196],
 [1670,500.7,314.7],[2000,294.4,310.9]
];
for(const [d,x,y] of expected){
 const p=W.RaceUmapotOverlay.point(kyoto,d,3);
 assert.ok(Math.hypot(p.x-x,p.y-y)<3,'registered Kyoto inner image anchor: '+d);
}
let last=null,maxPxPer5m=0;
for(let d=0;d<=2000;d+=5){
 const p=W.RaceUmapotOverlay.point(kyoto,d,3);
 assert.ok(p.x>28&&p.x<590&&p.y>86&&p.y<351,
  'inner 2000m marker must stay on the Kyoto original image '+d);
 if(last)maxPxPer5m=Math.max(maxPxPer5m,Math.hypot(last.x-p.x,last.y-p.y));
 last=p;
}
assert.ok(maxPxPer5m<5,'smooth 4th-corner→straight and start/finish joins');
// Check original image registrations were not rewritten as stand-ins.
const oldOuter=W.RaceUmapotOverlay.point(oldKyoto,805,3);
assert.ok(Math.abs(oldOuter.x-559)<15 && oldOuter.y>270);
const oldTokyo=W.RaceUmapotOverlay.point(tokyo,0,0);
assert.ok(oldTokyo.x>500&&oldTokyo.y>265);
assert.ok(html.includes('id="kyotoCourseImage"'));
assert.ok(html.includes('src="https://umapot.com/data/powerpoint/kyoto_couse/kyoto_couse_1.jpg"'));
assert.ok(html.includes('race-umapot-overlay-v1.js?v=20261016-43'));
assert.ok(html.includes('race-simulator.js?v=20261016-43'));
assert.ok(html.includes('同じうまぽっとの京都競馬場原画像'));
assert.ok(js.includes("['kyoto_turf_outer_1400','kyoto_turf_inner_2000'].includes"));
assert.ok(js.includes("'kyoto_turf_inner_2000'].includes(race.course_id)"));
const official=JSON.parse(fs.readFileSync(root+'race-sim-manifest-v1.json','utf8'));
assert.equal(official.races.length,2,'official field must remain two sealed races');
assert.ok(!official.races.some(x=>x.course_id==='kyoto_turf_inner_2000'));
console.log('PASS_V043_ACTUAL_UMAPOT_KYOTO_IMAGE_INNER_2000_AND_LEGACY_TRACKS',maxPxPer5m.toFixed(2));
