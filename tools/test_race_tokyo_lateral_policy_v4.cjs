'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),g={};
for(const n of ['race-lab-18-fixture-v1','race-tokyo-2000-v1','race-tokyo-lateral-policy-v4'])
 vm.runInNewContext(fs.readFileSync('docs/lab/'+n+'.js','utf8'),{window:g});
const data=g.RaceTokyo2000.race({motion:'bounded-lateral-v4'}),cfg={maxLane:16,laneWidthM:1.65,minimumLongitudinalM:2.55};
const policy=g.RaceTokyoLateralV4.create(data,cfg);
const h={number:2,d:1996.6250312693903,lane:2.9028104023228956},front={number:8,finished:true,
 d:2000,displayD:2000.2944354181677,lane:2.904441014305537,finishTime:122.61923927238765};
const before=JSON.stringify([h,front]),time=122.64,dt=.08,cross=(front.finishTime-(time-dt))/dt;
const safe=policy.limitTravel(h,[h,front],{distance:2,held:false},dt,time);
assert.ok(safe.held);assert.ok(h.d+safe.distance*cross<=2000-2.55+1e-8);
assert.ok(h.d+safe.distance<=front.displayD-2.55+1e-8);
assert.equal(JSON.stringify([h,front]),before,'clearance calculation must not rewrite runners or crossing time');
const gap=t=>policy.postFinishTravel(t)-policy.postFinishTravel(t-.2);
assert.ok(Math.abs(gap(1)-gap(5))<1e-10,'same-lane runoff separation must not shrink');
assert.ok(policy.postFinishTravel(3)>32);
assert.throws(()=>g.RaceTokyo2000.create(),/UNVERIFIED/);
console.log('PASS Tokyo candidate checks exact wire-crossing clearance and constant runoff separation without state mutation');
