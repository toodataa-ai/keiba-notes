/* Stage A-equivalent representative course registry tests.
 * Keep surface, layout, start distance and special routes exact, but collapse
 * A/B/C/D turf rail letters to one disclosed A-equivalent shape.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync('docs/lab/race-course-catalog-v1.json','utf8'));
const sdk=require('../docs/lab/race-course-catalog-v1.js');
const c=sdk.create(input);
assert.deepEqual(c.stats,{venues:10,families:27,rail_variants:27,templates:133,
 geometry_approved:0,stage_experiments:2});
assert.equal(new Set(c.templates.map(t=>t.id)).size,133);
assert.equal(input.safety_contract.require_explicit_turf_rail,false);
assert.equal(input.safety_contract.turf_rail_variants_collapsed_to_A,true);
const counts=Object.fromEntries(input.venues.map(v=>[v.code,c.list({venue:v.code}).length]));
for(const [v,count] of Object.entries(counts))assert.ok(count>0,'missing '+v);
for(const t of c.templates){
 assert.ok(t.source_url.startsWith('https://www.jra.go.jp/facilities/race/'));
 assert.equal(t.can_simulate,false,'catalog is metadata only');
 assert.equal(t.start_position,null);
 assert.equal(t.rail_boundary,null);
 assert.equal(t.continuous_path,null);
 assert.ok(t.distance_m>0);
 assert.ok(t.width_m===null||Array.isArray(t.width_m));
 assert.ok(c.get(t.id)===t);
 assert.equal(t.rail,t.surface==='turf'?'A':'dirt');
 const given={venue:t.venue,surface:t.surface,distance_m:t.distance_m,layout:t.layout};
 const r=c.resolve(given);
 assert.equal(r.status,'metadata_registered',t.id);
 assert.equal(r.template.id,t.id);
 assert.equal(c.bindRace(given).status,'geometry_not_approved',t.id);
 if(t.surface==='turf'){
  assert.equal(r.actual_rail,null);
  assert.equal(r.rail_approximation,true);
  for(const actual of ['A','B','C','D']){
   const x=c.resolve({...given,rail:actual});
   assert.equal(x.template.id,t.id,'same A-equivalent course for '+actual);
   assert.equal(x.actual_rail,actual);
   assert.equal(x.rail_policy,'A_equivalent');
   assert.equal(x.rail_approximation,actual!=='A');
   assert.equal(c.bindRace({...given,rail:actual}).status,'geometry_not_approved');
   assert.equal(c.list({...given,rail:actual}).length,1,'all rails filter to representative A');
  }
 }else{
  assert.equal(r.rail_approximation,false);
 }
}
const resolve=(x)=>c.resolve(x);
assert.equal(resolve({venue:'京都',surface:'芝',distance_m:1400}).status,'needs_layout');
assert.equal(resolve({venue:'京都',surface:'芝',distance_m:2000}).status,'needs_layout');
assert.equal(resolve({venue:'新潟',surface:'芝',distance_m:1400}).status,'needs_layout');
assert.equal(resolve({venue:'新潟',surface:'芝',distance_m:2000}).status,'needs_layout');
assert.equal(resolve({venue:'阪神',surface:'芝',distance_m:1400}).status,'needs_layout');
assert.equal(resolve({venue:'中山',surface:'芝',distance_m:3200}).template.layout,'outer_to_inner');
assert.equal(resolve({venue:'阪神',surface:'芝',distance_m:3200,rail:'D'}).template.layout,'outer_to_inner');
assert.equal(resolve({venue:'新潟',surface:'芝',distance_m:1000,rail:'C'}).template.layout,'straight');
const kyotoB=resolve({venue:'京都',surface:'芝',distance_m:1400,rail:'B',layout:'外回り'});
assert.equal(kyotoB.template.lap_m,1894.3);
assert.equal(kyotoB.template.straight_m,403.7);
assert.equal(kyotoB.template.stage_experiment_id,'kyoto_turf_outer_1400');
assert.equal(kyotoB.rail_approximation,true);
assert.equal(resolve({venue:'京都',surface:'芝',distance_m:1400,layout:'内回り'}).template.lap_m,1782.8);
assert.equal(resolve({venue:'京都',surface:'芝',distance_m:1400,layout:'外回り'}).template.lap_m,1894.3);
assert.equal(resolve({venue:'新潟',surface:'芝',distance_m:1000,layout:'直線'}).template.lap_m,null);
assert.equal(resolve({venue:'東京',surface:'ダート',distance_m:1600}).template.special_start,'turf_to_dirt');
assert.equal(resolve({venue:'新潟',surface:'ダート',distance_m:1200}).template.special_start,'turf_to_dirt');
assert.equal(resolve({venue:'東京',surface:'芝',distance_m:2000,layout:'外回り'}).status,'unsupported_layout');
assert.equal(resolve({venue:'京都',surface:'芝',distance_m:1400,rail:'Z',layout:'outer'}).status,'invalid_rail');
assert.equal(resolve({venue:'札幌',surface:'芝',distance_m:1300}).status,'unsupported_course_distance');
assert.equal(resolve({venue:'東京',surface:'芝',distance_m:2000}).status,'metadata_registered');
assert.equal(resolve({venue:'存在しない場',surface:'芝',distance_m:1400}).status,'unknown_venue');
const stage=c.templates.filter(t=>t.stage_experiment_id).map(t=>t.id).sort();
assert.deepEqual(stage,['kyoto_turf_outer_A_1400','tokyo_turf_single_A_2000']);
assert.equal(c.list({venue:'阪神',layout:'outer_to_inner',rail:'D'}).length,1);
assert.equal(c.list({venue:'新潟',surface:'dirt'}).length,5);
const doc=fs.readFileSync('docs/lab/race-course-catalog.html','utf8');
const ui=fs.readFileSync('docs/lab/race-course-catalog-ui-v1.js','utf8');
assert.match(doc,/コース型台帳/);assert.match(doc,/id="courseRows"/);
assert.match(doc,/代表モデル/);
assert.match(doc,/A相当/);
assert.match(doc,/座標.*未検品/);
assert.ok(!doc.includes('race-sim-engine.js'));
assert.ok(!ui.includes('RaceSimEngine.create'));
console.log('PASS_JRA_CATALOG_TEN_VENUES_27_FAMILIES_27_REPRESENTATIVE_ROUTES_133_DISTANCE_TEMPLATES');
console.log('PASS_CATALOG_ABCD_UNIFICATION_STRICT_SURFACE_LAYOUT_START_AND_FAIL_CLOSED_GEOMETRY');
console.log('PASS_JRA_CATALOG_LAB_READ_ONLY_BROWSER');
console.log('TEMPLATE_COUNTS_BY_VENUE '+JSON.stringify(counts));
