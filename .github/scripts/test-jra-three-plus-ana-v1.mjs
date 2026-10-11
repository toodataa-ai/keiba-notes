import fs from 'node:fs';import assert from 'node:assert/strict';
import {compareThreePlusAna,PURCHASE_ACTION_POLICY,instructions} from './jra-three-plus-ana-shadow-v1.mjs';
import {expandStrategy,ticketKey} from './jra-strategy-engine-v39.mjs';
const samples=[
'e2e_validation/predictions/2026-10-12-october-stakes/v3.13-run38177939515-attempt2.json',
'e2e_validation/predictions/2026-10-12-swan-stakes/v3.13-run38177942081-attempt2.json'];
for(const input of samples){
 const source=fs.readFileSync(input),d=JSON.parse(source);
 const p=compareThreePlusAna({budget_yen:6000,strategies:d.purchase_strategy_evaluations,
  formal_final_bets:d.final_bets,outcome_distributions:d.outcome_distributions,
  frame_map:d.frame_map,race_context:d.race_context,freeze_at:d.final_bets_fixed_at});
 assert.equal(Buffer.compare(source,fs.readFileSync(input)),0,'original file must remain immutable');
 assert.equal(p.formal_final_bets_unchanged,true);
 assert.equal(p.regular_commands.length<=3,true);
 assert.equal(p.ana_command.row,4);
 assert.equal(p.summary.stake_yen<=6000,true);
 const commands=[...p.regular_commands,...(p.ana_command.method==='pass'?[]:[p.ana_command])];
 let bought=[];
 for(const c of commands){
  const exp=expandStrategy(c.type,c.method,c.definition);
  assert.equal(exp.length,c.points);
  assert.equal(c.stake_yen,c.points*c.unit_stake_yen);
  assert.deepEqual(new Set(exp.map(x=>ticketKey(x.type,x.selection))),new Set(c.ticket_keys));
  assert.ok(instructions(c)===c.jra_input||c.category==='穴狙い');
  bought.push(...exp);
 }
 const keys=bought.map(x=>ticketKey(x.type,x.selection));
 assert.equal(new Set(keys).size,keys.length);
 assert.deepEqual(new Set(keys),new Set(p.proposed_lines.map(x=>ticketKey(x.type,x.selection))));
 assert.equal(commands.reduce((a,c)=>a+c.stake_yen,0),p.summary.stake_yen);
 if(p.ana_command.method!=='pass') {
  assert.ok(p.ana_command.observed_odds_floor>=20);
  assert.ok(p.ana_command.modeled_central_event_probability<=0.1);
 }
 console.log('PASS_THREE_PLUS_ANA_REAL',d.race_id,JSON.stringify({
  regular:p.regular_commands.length,ana:p.ana_command.method,stake:p.summary.stake_yen,
  expected_profit:p.summary.modeled_expected_net_profit_yen,
  delta_profit:p.change_vs_formal.expected_profit_yen,
  delta_hit_pp:p.change_vs_formal.union_hit_pp,
  delta_loss_pp:p.change_vs_formal.net_loss_pp
 }));
}
assert.equal(PURCHASE_ACTION_POLICY.max_regular_commands,3);
assert.equal(PURCHASE_ACTION_POLICY.max_ana_lines,1);
assert.equal(PURCHASE_ACTION_POLICY.formal_release,false);
console.log('PASS_THREE_PLUS_ANA_ALL_TESTS');
