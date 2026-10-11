import fs from 'node:fs';
import assert from 'node:assert/strict';
import {compareThreeCommandPortfolio,THREE_COMMAND_POLICY} from './jra-three-command-shadow-v1.mjs';
import {ticketKey,expandStrategy} from './jra-strategy-engine-v39.mjs';
const outcome=[];
for(let i=1;i<=6;i++)for(let j=1;j<=6;j++)if(i!==j)
  for(let k=1;k<=6;k++)if(k!==i&&k!==j)
    outcome.push({finish:[i,j,k],probability:1/120});
const freeze='2026-10-12T12:10:00+09:00',observed='2026-10-12T12:00:00+09:00';
const quote=(type,selection,odds=25)=>({type,selection,stake_yen:100,market_odds:odds,
  quote_verified:true,source_url:'https://sports.yahoo.co.jp/keiba/race/odds/ur/VERIFIED_FIXTURE',
  observed_at:observed,market_selection_id:ticketKey(type,selection)});
function fixture(n=5,odds=25,partial=false){
  const wheel=expandStrategy('馬連','key_wheel',{key:1,partners:[2,3,4,5,6]})
    .map(x=>quote(x.type,x.selection,odds));
  const selected=wheel.slice(0,n);
  return {budget_yen:6000,strategies:[
    {strategy_id:'WHEEL',type:'馬連',strategy_kind:'key_wheel',
      definition:{key:1,partners:[2,3,4,5,6]},lines:partial?wheel.slice(0,4):wheel},
    ...selected.map((line,i)=>({strategy_id:'S'+i,type:'馬連',strategy_kind:'single',
      definition:{selection:line.selection},lines:[line]}))],
    formal_final_bets:selected,
    outcome_distributions:{low:outcome,central:outcome,high:outcome},
    frame_map:Object.fromEntries([1,2,3,4,5,6].map(i=>[String(i),i])),
    race_context:{start_at:'2026-10-12T15:30:00+09:00',sale_field_size:6,
      place_paid_positions:2,offered_types:['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単']},
    freeze_at:freeze};
}
function assertExact(r){
  assert.ok(r.commands.length<=3);
  const reconstructed=[];
  for(const c of r.commands){
    const x=expandStrategy(c.type,c.method,c.definition);
    assert.equal(x.length,c.points);
    assert.deepEqual(new Set(x.map(t=>ticketKey(t.type,t.selection))),new Set(c.ticket_keys));
    reconstructed.push(...x.map(t=>ticketKey(t.type,t.selection)));
  }
  assert.deepEqual(new Set(reconstructed),
    new Set(r.proposed_lines.map(x=>ticketKey(x.type,x.selection))));
  assert.equal(reconstructed.length,r.proposed_lines.length);
  assert.ok(!r.formal_adoption_authorized);
  assert.ok(r.formal_bets_unchanged);
  assert.ok(r.proposed?.stake_yen<=6000);
}
{
  const f=fixture(),before=JSON.stringify(f),r=compareThreeCommandPortfolio(f);
  assert.equal(JSON.stringify(f),before,'source must stay byte-equivalent');
  assert.equal(r.status,'three_command_shadow_candidate');
  assertExact(r);
  assert.equal(r.commands.length,1);
  assert.equal(r.commands[0].method,'key_wheel');
  assert.equal(r.commands[0].points,5);
  console.log('PASS_THREE_COMMAND_full_wheel_single_action');
}
{
  const f=fixture(4,25,true),r=compareThreeCommandPortfolio(f);
  assertExact(r);
  assert.equal(r.commands.length,3,'incomplete wheel cannot be presented as one action');
  assert.ok(r.commands.every(x=>x.method==='single'));
  console.log('PASS_THREE_COMMAND_partial_wheel_not_misrepresented');
}
{
  const f=fixture(5,1.01),r=compareThreeCommandPortfolio(f);
  assert.equal(r.status,'no_qualifying_three_command_set');
  assert.equal(r.commands.length,0);
  console.log('PASS_THREE_COMMAND_no_ev_forced_bets');
}
{
  const f=fixture();f.formal_final_bets[0]={...f.formal_final_bets[0],market_odds:9999};
  assert.throws(()=>compareThreeCommandPortfolio(f),/final_bets not fully matched/);
  console.log('PASS_THREE_COMMAND_no_fabricated_pricing');
}
{
  const f=fixture();f.freeze_at='2026-10-13T12:10:00+09:00';
  assert.throws(()=>compareThreeCommandPortfolio(f),/prestart/);
  console.log('PASS_THREE_COMMAND_no_postrace_recompute');
}
for(const [race,p] of [
  ['october-stakes','e2e_validation/predictions/2026-10-12-october-stakes/v3.13-run38177939515-attempt2.json'],
  ['swan-stakes','e2e_validation/predictions/2026-10-12-swan-stakes/v3.13-run38177942081-attempt2.json']
]){
  const before=fs.readFileSync(p),o=JSON.parse(before);
  const r=compareThreeCommandPortfolio({
    budget_yen:6000,strategies:o.purchase_strategy_evaluations,
    formal_final_bets:o.final_bets,outcome_distributions:o.outcome_distributions,
    frame_map:o.frame_map,race_context:o.race_context,freeze_at:o.final_bets_fixed_at
  });
  if(r.proposed)assertExact(r);
  assert.ok(r.audit.combinations_enumerated>=0);
  assert.equal(Buffer.compare(fs.readFileSync(p),before),0,'historical prediction must remain immutable');
  console.log('REAL_20261012_SHADOW_REPLAY',race,JSON.stringify({
    commands:r.commands.length,baseline_profit:r.baseline.expected_net_profit_yen,
    proposed_profit:r.proposed?.expected_net_profit_yen??null,
    hit_change_pp:r.comparison?.hit_probability_delta_pp??null,
    loss_change_pp:r.comparison?.net_loss_probability_delta_pp??null,
    verified:r.audit.verified_source_ticket_count
  }));
}
assert.equal(THREE_COMMAND_POLICY.max_purchase_commands,3);
console.log('PASS_THREE_COMMAND_ALL_TESTS');
