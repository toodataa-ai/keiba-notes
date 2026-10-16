/* Kyoto A inner 2000m / Shuka Sho stage-design geometry regression.
 * Checks more than endpoints: exact shared physical home straight, JRA first
 * turn approach length, C1 corner joins, and no unapproved animation.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const file=JSON.parse(fs.readFileSync('docs/staging/weekend-main-course-blueprints-20261017.json','utf8'));
const route=file.courses.find(x=>x.course_id==='kyoto_turf_inner_2000');
const catalog=JSON.parse(fs.readFileSync('docs/staging/race-course-catalog-v1.json','utf8'));
const review=fs.readFileSync('docs/staging/weekend-main-course-review.html','utf8');
const script=fs.readFileSync('docs/staging/weekend-main-course-review-v1.js','utf8');
assert.ok(route,'official course must be separately defined');
assert.equal(file.safe_for_live_simulator,false);
assert.equal(file.status,'PROVISIONAL_BLUEPRINT_NO_ANIMATION');
assert.equal(route.distance_m,2000);
assert.equal(route.lap_m,1782.8);
assert.equal(route.straight_m,328.4);
assert.equal(route.turn,'right');
assert.equal(route.layout,'inner');
assert.equal(route.elevation_range_m,3.1);
assert.equal(route.start_to_first_turn_m,308.7);
assert.equal(route.segment_bounds[1],308.7);
assert.equal(route.segment_bounds.at(-2),1671.6);
assert.equal(route.segments.length,7);
assert.equal(route.segments.length,route.segment_names.length);
assert.equal(route.segment_bounds.length,8);
const inner=catalog.venues.find(x=>x.code==='kyoto').routes
 .find(x=>x.surface==='turf'&&x.layout==='inner');
assert.equal(route.lap_m,inner.variants.A.lap_m);
assert.equal(route.straight_m,inner.variants.A.straight_m);
assert.equal(route.elevation_range_m,inner.elevation_m);
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const start=route.segments[0][0];
const goal=route.segments.at(-1)[3];
const corner=route.segments[1][0];
assert.ok(dist(start,goal)>75,'start and goal must be DISTINCT physical points');
assert.ok(dist(goal,corner)>70,'goal must be away from first turn entrance');
assert.ok(goal[0]<start[0]&&goal[0]>corner[0],
 'goal on home stretch between gate and first turn (right-hand course)');
const C=(b,t)=>{
 const q=1-t;
 return [0,1].map(i=>q*q*q*b[0][i]+3*q*q*t*b[1][i]+
       3*q*t*t*b[2][i]+t*t*t*b[3][i]);
};
const shared=route.overlap_geometry;
assert.equal(shared.gate_on_home_straight,true);
assert.equal(shared.first_corner_not_at_goal,true);
assert.ok(shared.start_fraction>0&&shared.start_fraction<shared.goal_fraction&&shared.goal_fraction<1);
for(let i=0;i<=100;i++){
 const fraction=shared.start_fraction+
  (shared.goal_fraction-shared.start_fraction)*i/100;
 const onShared=C(shared.home_straight_shared_cubic,fraction);
 const fromGate=C(route.segments[0],
  (fraction-shared.start_fraction)/(1-shared.start_fraction));
 const approachingGoal=C(route.segments.at(-1),fraction/shared.goal_fraction);
 assert.ok(dist(onShared,fromGate)<.0002,'source same physical rail: gate to first corner '+i);
 assert.ok(dist(onShared,approachingGoal)<.0002,'source same physical rail: last straight '+i);
}
assert.ok(dist(C(shared.home_straight_shared_cubic,shared.start_fraction),start)<.0002);
assert.ok(dist(C(shared.home_straight_shared_cubic,shared.goal_fraction),goal)<.0002);
for(let i=1;i<route.segments.length;i++){
 const left=route.segments[i-1],right=route.segments[i];
 assert.ok(dist(left[3],right[0])<.00001,'zero gap at 1-4C and straight boundary '+i);
 const a=[left[3][0]-left[2][0],left[3][1]-left[2][1]];
 const b=[right[1][0]-right[0][0],right[1][1]-right[0][1]];
 const cosine=(a[0]*b[0]+a[1]*b[1])/(Math.hypot(...a)*Math.hypot(...b));
 assert.ok(cosine>.995,'tangent direction discontinuity at boundary '+i+': '+cosine);
}
assert.ok(!route.notes.includes('1コーナーまで217.2m'));
assert.ok(route.official_course.includes('/kyoto/course/'));
assert.ok(route.reference.official_race.includes('/keiba/g1/shuka.html'));
assert.match(review,/id="officialRaceReference"/);
assert.match(review,/weekend-main-course-review-v1.js\?v=20261016-2/);
assert.match(script,/segment_names\[i\]\.match\(/);
assert.match(script,/officialRaceReference/);
assert.doesNotMatch(script,/RaceSimEngine\.create|requestAnimationFrame/);
console.log('PASS_KYOTO_INNER_2000_OFFICIAL_RUNUP_SHARED_STRAIGHT_C1_SEVEN_SECTORS');
