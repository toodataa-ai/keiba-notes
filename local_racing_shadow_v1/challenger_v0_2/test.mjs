import test from "node:test";
import assert from "node:assert/strict";
import { scoreRace, MODEL_VERSION } from "./scoring.mjs";
const fixture=()=>{
 const runners=Array.from({length:6},(_,i)=>({horse_no:i+1,horse_name:"Horse"+(i+1),
    evidence_score:6-i,non_runner:false,recent_races:[{date:"2026-10-01",finish_position:i+1}],
    running_style_hypothesis:i<2?"先行":"中団",weight_carried:55,gate:i+1}));
 return {race_id:"20261014-sonoda-01",date:"2026-10-14",venue:"園田",surface:"ダート",
 model_version:"local-daily-shadow-v0.1",production_effect:false,scheduled_start_at:"2026-10-14T12:30:00+09:00",
 information_cutoff_at:"2026-10-14T08:30:00+09:00",runners};
};
test("deterministic ranked output, original untouched",()=>{
 const src=fixture(),orig=JSON.stringify(src);
 const a=scoreRace(src),b=scoreRace(src);
 assert.deepEqual(a,b); assert.equal(JSON.stringify(src),orig);
 assert.equal(a.model_version,MODEL_VERSION);
 assert.equal(a.ability_order.length,6);
 assert.deepEqual(a.ability_order.map(x=>x.rank),[1,2,3,4,5,6]);
});
test("reject outcome leakage",()=>{const src=fixture();src.finish_order=[];assert.throws(()=>scoreRace(src),/leakage/);});
test("reject after-cutoff snapshots",()=>{const src=fixture();src.information_cutoff_at=src.scheduled_start_at;assert.throws(()=>scoreRace(src),/cutoff/);});
test("ban-ei must use a separate model",()=>{const src=fixture();src.surface="ばんえい";assert.throws(()=>scoreRace(src),/BANEI/);});
test("non-runners excluded, no invented data",()=>{const src=fixture();src.runners[0].non_runner=true;
 const r=scoreRace(src);assert.equal(r.ability_order.length,5);assert(!r.ability_order.some(x=>x.horse_no===1));});
test("reject future race form data",()=>{const src=fixture();src.runners[0].recent_races=[{date:"2026-10-14"}];assert.throws(()=>scoreRace(src),/not before/);});
