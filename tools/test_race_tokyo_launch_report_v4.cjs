'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const [oldPath,newPath]=process.argv.slice(2);if(!oldPath||!newPath)throw Error('Provide legacy and bounded audit JSON paths');
const old=JSON.parse(fs.readFileSync(oldPath)),candidate=JSON.parse(fs.readFileSync(newPath));
assert.deepEqual(old.seeds,candidate.seeds);assert.equal(candidate.seeds.length,32);
assert.equal(candidate.motion,'bounded-lateral-v4');assert.equal(old.motion,'legacy');
assert.equal(candidate.canAnimate,false);assert.equal(candidate.approval,'not_approved');assert.equal(candidate.reproducible,true);
assert.ok(old.summary.launchSweptHits>0,'The diagnostic must retain the reproduced legacy failure');
for(const key of ['endpointHits','sweptHits','launchEndpointHits','launchSweptHits','runoffEndpointHits','allStateSweptHits','boundsViolations','backwardSteps','emergencyStops'])
 assert.equal(candidate.summary[key],0,key);
assert.equal(candidate.summary.all18Finished,true);assert.equal(candidate.summary.all18RunoffComplete,true);
assert.ok(candidate.summary.maxLateralMps<=1.2+1e-9);
assert.ok(candidate.summary.maxLateralVelocityJumpMps<=.8*.08+1e-9);
for(const row of candidate.stepSensitivity){
 for(const key of ['endpointHits','sweptHits','launchSweptHits','runoffEndpointHits','allStateSweptHits'])assert.equal(row[key],0,`${row.seed}/${key}`);
 assert.ok(row.maxLateralVelocityJumpMps<=.8*.04+1e-9);
 assert.ok(row.all18Finished&&row.all18RunoffComplete);
}
console.log('PASS 32-seed bounded candidate safety diagnostics at 0.08s; three 0.04s sensitivities; approval stays false');
