'use strict';
const assert=require('node:assert/strict'),{overlapInterval,sweptRectangle}=require('./lib/race-swept-audit-v1.cjs');
const p=(d,lane)=>({d,lane});
assert.equal(overlapInterval(3,3,2.55),null);
assert.deepEqual(overlapInterval(0,0,2.55),[0,1]);
assert.equal(sweptRectangle(p(0,0),p(0,0),p(2.55,0),p(2.55,0)),null,'touching is not interpenetration');
assert.equal(sweptRectangle(p(0,0),p(1,0),p(4,2),p(5,2)),null);
// Collision exists only BETWEEN endpoints; endpoint-only checks miss this.
const hit=sweptRectangle(p(-4,0),p(4,0),p(0,-1),p(0,1));
assert.ok(hit&&hit.from>0&&hit.to<1);
// Fore-aft and side overlap occur at different times: do not invent a collision.
assert.equal(sweptRectangle(p(0,2),p(10,0),p(0,0),p(0,0)),null);
assert.equal(sweptRectangle(p(-4,0),p(4,0),p(0,-1),p(0,1),{endFraction:.1}),null,'exclude time after earlier wire crossing');
assert.throws(()=>overlapInterval(NaN,0,1),/INVALID/);
console.log('PASS swept-rectangle audit: tunneling, disjoint overlap intervals, clearance and finish cutoff');
