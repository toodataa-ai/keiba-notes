/* Stage v0.28: lane zero corresponds to inner edge, no trail or map switch. */
'use strict';
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const W={},dir='docs/staging/';
vm.runInNewContext(fs.readFileSync(dir+'race-course-geometry-v1.js','utf8'),{window:W,globalThis:W});
vm.runInNewContext(fs.readFileSync(dir+'race-umapot-overlay-v1.js','utf8').replace('setup();',''),{
 window:W,globalThis:W,document:{getElementById:()=>null,querySelector:()=>null}});
for(const id of ['tokyo_turf_2000','kyoto_turf_outer_1400']){
 const course=W.RaceCourseGeometry.get(id);
 assert.ok(W.RaceUmapotOverlay.validate(course));
 for(const d of [0,130,300,500,810,927,course.distance_m-course.straight_m,course.distance_m-1]
   .filter(x=>x>=0&&x<course.distance_m)){
  const live0=W.RaceCourseGeometry.point(course,d,0);
  const live4=W.RaceCourseGeometry.point(course,d,4);
  const map0=W.RaceUmapotOverlay.point(course,d,0);
  const map4=W.RaceUmapotOverlay.point(course,d,4);
  assert.ok(Math.hypot(live0.x-live4.x,live0.y-live4.y)>2,'live inner track lane separation');
  const mapped=Math.hypot(map0.x-map4.x,map0.y-map4.y);
  assert.ok(mapped>8&&mapped<10,'reference track lane spacing in image pixels');
 }
 for(const segment of course.segments.slice(1)){
  const a=W.RaceUmapotOverlay.point(course,segment.from-.02,0);
  const b=W.RaceUmapotOverlay.point(course,segment.from+.02,0);
  assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<.14,'reference rail moves continuously across landmarks');
 }
 console.log('PASS_V028_INNER_RAIL_BOTH_MAPS',id);
}
const html=fs.readFileSync(dir+'race-simulator.html','utf8');
const js=fs.readFileSync(dir+'race-simulator.js','utf8');
const um=fs.readFileSync(dir+'race-umapot-overlay-v1.js','utf8');
assert.match(html,/Stage v0\.\d+/);
assert.ok(html.includes('id="referenceMapFigure"'));
for(const id of ['courseMapMode','courseCanvas','pathToggle'])assert.ok(!html.includes('id="'+id+'"'));
assert.ok(!html.includes('進路の軌跡を表示'));
assert.ok(!js.includes("strokePath(ctx,35,'#d9d7b7')"));
assert.ok(!js.includes("horse.trail"));
assert.ok(!um.includes('if(pathOn)for'));
assert.ok(/race-umapot-overlay-v1\.js\?v=20261015-\d+/.test(html));
console.log('PASS_V028_UMAPOT_FIXED_MAP_NO_YELLOW_TRAILS');