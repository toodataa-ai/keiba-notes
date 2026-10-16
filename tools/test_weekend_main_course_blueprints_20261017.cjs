/* JRA weekend 2026-10-17–18 six-course design-stage acceptance gate.
 * This test does NOT approve exact XY coordinates or enable live simulation.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const base='docs/staging/';
const file=JSON.parse(fs.readFileSync(base+'weekend-main-course-blueprints-20261017.json','utf8'));
const catalog=JSON.parse(fs.readFileSync(base+'race-course-catalog-v1.json','utf8'));
const html=fs.readFileSync(base+'weekend-main-course-review.html','utf8');
const script=fs.readFileSync(base+'weekend-main-course-review-v1.js','utf8');
assert.equal(file.status,'PROVISIONAL_BLUEPRINT_NO_ANIMATION');
assert.equal(file.safe_for_live_simulator,false);
assert.equal(file.restrictions.no_unverified_live_animation,true);
assert.equal(file.restrictions.require_human_visual_acceptance,true);
assert.equal(file.restrictions.require_frozen_pre_race_horse_report_for_live,true);
assert.equal(file.courses.length,6);
const expected=[
 ['kyoto_turf_inner_2000','2026-10-18','kyoto','turf','inner',2000],
 ['tokyo_turf_1600','2026-10-17','tokyo','turf','single',1600],
 ['kyoto_dirt_1800','2026-10-17','kyoto','dirt','single',1800],
 ['niigata_turf_inner_1200','2026-10-17','niigata','turf','inner',1200],
 ['tokyo_dirt_2100','2026-10-18','tokyo','dirt','single',2100],
 ['niigata_turf_inner_2200','2026-10-18','niigata','turf','inner',2200]
];
for(let index=0;index<expected.length;index++){
 const b=file.courses[index], [id,date,venue,surface,layout,distance]=expected[index];
 assert.equal(b.course_id,id);assert.equal(b.priority,index+1);assert.equal(b.date,date);
 assert.equal(b.venue_id,venue);assert.equal(b.surface,surface);
 assert.equal(b.layout,layout);assert.equal(b.distance_m,distance);
 const v=catalog.venues.find(x=>x.code===venue);
 assert.ok(v,'venue must exist');
 const route=v.routes.find(x=>x.surface===surface&&x.layout===layout&&x.distances_m.includes(distance));
 assert.ok(route,'exact surface, layout and distance from the JRA catalogue '+id);
 const spec=route.variants[surface==='dirt'?'dirt':'A'];
 assert.ok(Math.abs(spec.lap_m-b.lap_m)<.001,'lap must match official metadata '+id);
 assert.ok(Math.abs(spec.straight_m-b.straight_m)<.001,'straight must match official metadata '+id);
 assert.deepEqual(spec.width_m,b.track_width_m);
 assert.equal(route.elevation_m,b.elevation_range_m);
 assert.ok(b.official_course.includes('/'+venue+'/course/'));
 assert.ok(b.official_entries.includes('jra.go.jp/'));
 assert.equal(b.segments.length,b.segment_names.length);
 assert.equal(b.segments.length,b.segment_bounds.length-1);
 assert.equal(b.segment_bounds[0],0);
 assert.ok(Math.abs(b.segment_bounds.at(-1)-distance)<.001);
 assert.ok(Math.abs(b.segment_bounds.at(-2)-(distance-b.straight_m))<.001);
 for(let i=0;i<b.segments.length;i++){
  const seg=b.segments[i];
  assert.equal(seg.length,4);
  assert.ok(b.segment_bounds[i+1]>b.segment_bounds[i]);
  assert.ok(seg.every(pt=>pt.length===2&&pt.every(coord=>Number.isFinite(coord)&&coord>=50&&coord<=550)));
  assert.ok(Math.hypot(seg[0][0]-seg[3][0],seg[0][1]-seg[3][1])>2,'degenerate route segment');
  if(i){
   const previous=b.segments[i-1][3];
   assert.ok(Math.hypot(seg[0][0]-previous[0],seg[0][1]-previous[1])<.00001,
    'course must be continuous at '+id+' segment '+i);
  }
 }
 const final=b.segments.at(-1),dx=final[3][0]-final[0][0];
 assert.ok(b.turn==='right'?dx<0:dx>0,'correct home-straight direction '+id);
}
assert.equal(new Set(file.courses.map(x=>x.course_id)).size,6,'all six independently defined');
assert.equal(new Set(file.courses.map(x=>JSON.stringify(x.segments))).size,6,'no reused surrogate course shape');
assert.match(html,/STAGING/);
assert.match(html,/まだ馬を走らせることはできません/);
assert.match(html,/weekend-main-course-review-v1\.js/);
assert.match(script,/PROVISIONAL_BLUEPRINT_NO_ANIMATION/);
assert.match(script,/safe_for_live_simulator!==false/);
assert.doesNotMatch(script,/RaceSimEngine\.create|drawRace\(|requestAnimationFrame/);
console.log('PASS_WEEKEND_20261017_SIX_COURSE_PLANS_VALID_GATED_NOT_YET_APPROVED');
