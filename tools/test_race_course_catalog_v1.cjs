/* JRA ten-venue official course type registry: deterministic, fail closed.
 * No JRA prompt, settlement, picks or actual race prediction modifications.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync('docs/staging/race-course-catalog-v1.json','utf8'));
const sdk=require('../docs/staging/race-course-catalog-v1.js');
const c=sdk.create(input);
assert.deepEqual(c.stats,{venues:10,families:27,rail_variants:57,templates:297,
 geometry_approved:0,stage_experiments:2});
assert.equal(new Set(c.templates.map(t=>t.id)).size,297);
const counts=Object.fromEntries(input.venues.map(v=>[v.code,c.list({venue:v.code}).length]));
for(const [v,count] of Object.entries(counts))assert.ok(count>0,'missing '+v);
for(const t of c.templates){
 assert.ok(t.source_url.startsWith('https://www.jra.go.jp/facilities/race/'));
 assert.equal(t.can_simulate,false);
 assert.equal(t.start_position,null);
 assert.equal(t.rail_boundary,null);
 assert.equal(t.continuous_path,null);
 assert.ok(t.distance_m>0);
 assert.ok(t.width_m===null||Array.isArray(t.width_m));
 assert.ok(c.get(t.id)===t);
 const r=c.resolve({venue:t.venue,surface:t.surface,distance_m:t.distance_m,
   layout:t.layout,rail:t.rail==='dirt'?undefined:t.rail});
 assert.equal(r.status,'metadata_registered',t.id);
 assert.equal(r.template.id,t.id);
 const bind=c.bindRace({venue:t.venue,surface:t.surface,distance_m:t.distance_m,
   layout:t.layout,rail:t.rail==='dirt'?undefined:t.rail});
 assert.equal(bind.ok,false,'unapproved geometry unexpectedly executable '+t.id);
 assert.equal(bind.status,'geometry_not_approved');
}
const req=(o)=>c.resolve(o);
assert.equal(req({venue:'京都',surface:'芝',distance_m:1400,rail:'A'}).status,'needs_layout');
assert.equal(req({venue:'京都',surface:'芝',distance_m:2000,rail:'A'}).status,'needs_layout');
assert.equal(req({venue:'新潟',surface:'芝',distance_m:1400,rail:'A'}).status,'needs_layout');
assert.equal(req({venue:'新潟',surface:'芝',distance_m:2000,rail:'A'}).status,'needs_layout');
assert.equal(req({venue:'阪神',surface:'芝',distance_m:1400,rail:'B'}).status,'needs_layout');
assert.equal(req({venue:'中山',surface:'芝',distance_m:3200,rail:'A'}).template.layout,'outer_to_inner');
assert.equal(req({venue:'阪神',surface:'芝',distance_m:3200,rail:'B'}).template.layout,'outer_to_inner');
assert.equal(req({venue:'新潟',surface:'芝',distance_m:1000,rail:'A'}).template.layout,'straight');
const kyotoOuter=req({venue:'京都',surface:'芝',distance_m:1400,rail:'B',layout:'外回り'});
assert.equal(kyotoOuter.template.lap_m,1913.6);
assert.equal(kyotoOuter.template.straight_m,398.7);
assert.equal(kyotoOuter.template.stage_experiment_id,null,'A stage shape must never silently cover B');
assert.equal(req({venue:'京都',surface:'芝',distance_m:1400,rail:'A',layout:'内回り'}).template.lap_m,1782.8);
assert.equal(req({venue:'京都',surface:'芝',distance_m:1400,rail:'A',layout:'外回り'}).template.lap_m,1894.3);
assert.equal(req({venue:'京都',surface:'芝',distance_m:1400,rail:'D',layout:'外回り'}).template.straight_m,398.7);
assert.equal(req({venue:'新潟',surface:'芝',distance_m:1000,rail:'A',layout:'直線'}).template.lap_m,null);
assert.equal(req({venue:'東京',surface:'ダート',distance_m:1600}).template.special_start,'turf_to_dirt');
assert.equal(req({venue:'新潟',surface:'ダート',distance_m:1200}).template.special_start,'turf_to_dirt');
assert.equal(req({venue:'東京',surface:'芝',distance_m:2000,rail:'A',layout:'外回り'}).status,'unsupported_layout');
assert.equal(req({venue:'京都',surface:'芝',distance_m:1400,rail:'Z',layout:'outer'}).status,'needs_rail');
assert.equal(req({venue:'札幌',surface:'芝',distance_m:1300,rail:'A'}).status,'unsupported_course_distance');
assert.equal(req({venue:'東京',surface:'芝',distance_m:2000}).status,'needs_rail');
assert.equal(req({venue:'存在しない場',surface:'芝',distance_m:1400}).status,'unknown_venue');
const stage=c.templates.filter(t=>t.stage_experiment_id).map(t=>t.id).sort();
assert.deepEqual(stage,['kyoto_turf_outer_A_1400','tokyo_turf_single_A_2000']);
assert.equal(c.list({venue:'阪神',layout:'outer_to_inner',rail:'A'}).length,1);
assert.equal(c.list({venue:'新潟',surface:'dirt'}).length,5);
const doc=fs.readFileSync('docs/staging/race-course-catalog.html','utf8');
const ui=fs.readFileSync('docs/staging/race-course-catalog-ui-v1.js','utf8');
assert.match(doc,/コース型台帳/);assert.match(doc,/id="courseRows"/);
assert.match(doc,/race-course-catalog-ui-v1\.js/);
assert.match(doc,/座標.*未検品/);
assert.ok(!doc.includes('race-sim-engine.js'),'catalog must not trigger actual races');
assert.ok(!ui.includes('RaceSimEngine.create'),'catalog UI is read-only');
console.log('PASS_JRA_CATALOG_TEN_VENUES_27_FAMILIES_57_RAIL_VARIANTS_297_DISTANCE_TEMPLATES');
console.log('PASS_JRA_CATALOG_STRICT_LAYOUT_RAIL_START_SURFACE_NO_UNKNOWN_GEOMETRY_EXECUTION');
console.log('PASS_JRA_CATALOG_STAGE_READ_ONLY_BROWSER');
console.log('TEMPLATE_COUNTS_BY_VENUE '+JSON.stringify(counts));
