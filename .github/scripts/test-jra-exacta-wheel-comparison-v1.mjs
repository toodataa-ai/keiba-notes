import assert from 'node:assert/strict';
import {assessExactaMultiCoverage,sortRegularPurchaseCommands} from './jra-exacta-wheel-comparison-v1.mjs';
import {expandStrategy,ticketKey} from './jra-strategy-engine-v39.mjs';
const key=t=>ticketKey(t.type,t.selection);
const finish=[];
for(let a=1;a<=5;a++)for(let b=1;b<=5;b++)for(let c=1;c<=5;c++)
  if(a!==b&&b!==c&&a!==c)finish.push({finish:[a,b,c],probability:1/60});
const args={outcome_distributions:{central:finish,low:finish,high:finish},
  frame_map:{1:1,2:2,3:3,4:4,5:5},race_context:{sale_field_size:5,place_paid_positions:2}};
const wheel={key:1,partners:[2,3]};
const selected=expandStrategy('馬単','key_wheel_second',wheel);
function quote(t){return {...t,stake_yen:100,market_odds:t.selection[1]===1?20:50,
 source_url:'https://test.invalid/actual-price',observed_at:'2026-10-12T10:00:00+09:00'};}
const all=expandStrategy('馬単','key_wheel_multi',wheel).map(quote);
const regular_lines=selected.map(x=>all.find(t=>key(x)===key(t)));
const regular_commands=[{type:'馬単',method:'key_wheel_second',definition:wheel,
  points:2,stake_yen:200,unit_stake_yen:100,ticket_keys:selected.map(key),source_strategy_id:'CASE'}];
const invoke=(overrides={})=>assessExactaMultiCoverage({regular_commands,regular_lines,side_lines:[],
 all,args,budget_yen:6000,...overrides});
{
 const r=invoke();
 assert.equal(r.regular_commands[0].method,'key_wheel_multi');
 assert.equal(r.regular_commands[0].points,4);
 assert.equal(r.regular_commands[0].stake_yen,400);
 assert.ok(r.audit[0].variants.key_wheel_multi.metrics.hit_probability>
   r.audit[0].variants.key_wheel_second.metrics.hit_probability);
 assert.ok(r.audit[0].variants.key_wheel_multi.metrics.expected_net_profit_yen>=
   r.audit[0].variants.key_wheel_second.metrics.expected_net_profit_yen);
 assert.deepEqual(new Set(r.regular_lines.map(key)),
   new Set(expandStrategy('馬単','key_wheel_multi',wheel).map(key)));
 console.log('PASS_EXACTA_PARETO_PROMOTES_AFFORDABLE_MULTI');
}
{
 const bad=all.map(x=>({...x,market_odds:x.selection[0]===1?1.01:x.market_odds}));
 const r=invoke({all:bad});
 assert.equal(r.regular_commands[0].method,'key_wheel_second');
 assert.ok(r.audit[0].variants.key_wheel_multi.metrics.expected_net_profit_yen<
   r.audit[0].variants.key_wheel_second.metrics.expected_net_profit_yen);
 console.log('PASS_EXACTA_NOT_FORCED_WHEN_MULTI_WASTES_EV');
}
{
 const withoutFirst=all.filter(x=>x.selection[1]===1);
 const r=invoke({all:withoutFirst});
 assert.equal(r.regular_commands[0].method,'key_wheel_second');
 assert.equal(r.audit[0].variants.key_wheel_multi.status,'unpriced');
 console.log('PASS_EXACTA_UNQUOTED_MULTI_REJECTED');
}
{
 const side=[all.find(x=>x.selection[0]===1)];
 const r=invoke({side_lines:side});
 assert.equal(r.regular_commands[0].method,'key_wheel_second');
 assert.equal(r.audit[0].variants.key_wheel_multi.status,'overlap');
 console.log('PASS_EXACTA_MULTI_CANNOT_DUPLICATE_SIDE_TICKET');
}
{
 const r=invoke({budget_yen:200});
 assert.equal(r.regular_commands[0].method,'key_wheel_second');
 assert.equal(r.audit[0].variants.key_wheel_multi.status,'over_budget');
 console.log('PASS_EXACTA_MULTI_CANNOT_EXCEED_BUDGET');
}
{
 const ordered=sortRegularPurchaseCommands([
  {type:'三連複',id:'trio'},{type:'馬連',id:'quinella'},{type:'馬単',id:'exacta'},
  {type:'ワイド',id:'wide'}
 ]);
 assert.deepEqual(ordered.map(x=>x.id),['quinella','exacta','wide','trio']);
 assert.deepEqual(ordered.map(x=>x.row),[1,2,3,4]);
 console.log('PASS_JRA_BET_TYPE_PRESENTATION_ORDER');
}
console.log('PASS_EXACTA_MULTI_COMPARISON_ALL');

