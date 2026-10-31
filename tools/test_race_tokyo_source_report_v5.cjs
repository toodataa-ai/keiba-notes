'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const r=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
assert.equal(r.sourceSession.model,'source-linked-v5');assert.equal(r.sourceSession.canAnimate,false);assert.equal(r.approval,'not_approved');
assert.equal(r.sourceSession.geometrySha256,'281afd0bffdc43c7b314c2d5bd3ed544344eee2f75c4b6240571aa8381a7723d');
assert.equal(r.summary.seedCount,32);assert.equal(r.runs.length,32);assert.ok(r.reproducible);
for(const k of ['endpointHits','sweptHits','launchEndpointHits','launchSweptHits','runoffEndpointHits','allStateSweptHits','boundsViolations','backwardSteps','emergencyStops'])assert.equal(r.summary[k],0,k);
assert.ok(r.summary.all18Finished&&r.summary.all18RunoffComplete);assert.ok(r.summary.maxLateralMps<=1.2+1e-8);assert.ok(r.summary.maxLateralVelocityJumpMps<=.064+1e-8);
for(const row of r.runs){assert.ok(row.all18Finished&&row.all18RunoffComplete);assert.equal(row.motionStats.emergencyStops,0);}
for(const row of r.stepSensitivity){assert.ok(row.all18Finished&&row.all18RunoffComplete);assert.equal(row.allStateSweptHits,0);assert.ok(row.maxLateralVelocityJumpMps<=.032+1e-8);}
assert.equal(r.boundaryComparison.find(x=>x.distance===110).physicalKind,'turn');
for(const [name,expected] of Object.entries(r.sourceHashes))assert.equal(crypto.createHash('sha256').update(fs.readFileSync('docs/lab/'+name+'.js')).digest('hex'),expected,name+' hash');
console.log('PASS source-linked 32 seeds, 18 finish/runoff, swept safety, bounds, acceleration, reproduction, exact engine/source hashes; approval remains false');
