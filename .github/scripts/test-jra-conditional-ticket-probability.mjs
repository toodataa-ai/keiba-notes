import assert from 'node:assert/strict';
import {finishingTriples, ticketProbability, evaluateScenario} from './jra-conditional-ticket-probability.mjs';
const runners=[
 {horse_number:1,frame_number:1,strength:5},
 {horse_number:2,frame_number:1,strength:3},
 {horse_number:3,frame_number:2,strength:2},
 {horse_number:4,frame_number:3,strength:1}
];
const triple=finishingTriples(runners);
const almost=(x,y)=>assert(Math.abs(x-y)<1e-8,`${x} != ${y}`);
almost(triple.reduce((s,r)=>s+r.probability,0),1);
almost(ticketProbability(triple,'単勝',[1],4),5/11);
almost(ticketProbability(triple,'三連単',[1,2,3],4),(5/11)*(3/6)*(2/3));
almost(ticketProbability(triple,'三連複',[1,2,3],4),
 [1,2,3].reduce((s,a,i)=>s+[1,2,3].filter(x=>x!==a).reduce((s,b)=>{const c=[1,2,3].find(x=>x!==a&&x!==b);return s+ticketProbability(triple,'三連単',[a,b,c],4)},0),0));
almost(ticketProbability(triple,'馬連',[1,2],4),ticketProbability(triple,'馬単',[1,2],4)+ticketProbability(triple,'馬単',[2,1],4));
almost(ticketProbability(triple,'ワイド',[1,2],4),
 triple.filter(r=>r.finish.includes(1)&&r.finish.includes(2)).reduce((s,r)=>s+r.probability,0));
almost(ticketProbability(triple,'枠連',[1,1],4),ticketProbability(triple,'馬連',[1,2],4));
almost(ticketProbability(triple,'複勝',[1],4),ticketProbability(triple,'単勝',[1],4)); // <=4 horses pays first only
const scenario=evaluateScenario(runners,[1,2,3],'三連単',40);
almost(scenario.break_even_probability,0.025);
assert.equal(scenario.scenario_only,true);
assert.throws(()=>ticketProbability(triple,'WIN5',[1],4),/Only eight/);
assert.throws(()=>finishingTriples([...runners,{horse_number:1,frame_number:4,strength:5}]),/duplicate/);
console.log('PASS: conditional ranking normalization, exact order, unordered tickets, frame bets, sensitivity inputs, WIN5 exclusion');
