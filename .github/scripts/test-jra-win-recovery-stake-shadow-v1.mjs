// Synthetic only. This test MUST NOT touch prestart formal predictions or E2E proof.
import assert from 'node:assert/strict';
import {ticketKey,evaluateStrategy} from './jra-strategy-engine-v39.mjs';
import {optimizeWinStakeForRecovery,RECOVERY_STAKE_POLICY} from './jra-win-recovery-stake-shadow-v1.mjs';
const outcomes=[];
for(let a=1;a<=4;a++)for(let b=1;b<=4;b++)for(let c=1;c<=4;c++)
 if(a!==b&&a!==c&&b!==c)outcomes.push({finish:[a,b,c],probability:1/24});
const dist={low:outcomes,central:outcomes,high:outcomes};
const frame_map={1:1,2:2,3:3,4:4};
const race_context={place_paid_positions:3,sale_field_size:4,offered_types:['単勝','三連単']};
const marketLine=(type,selection,market_odds,id)=>{
 const key=ticketKey(type,selection);
 return {type,selection,stake_yen:100,market_odds,market_selection_id:key,
   quote_verified:true,source_url:'https://example.org/test/synthetic',observed_at:'2030-10-11T09:00:00+09:00',
   id,probabilities:{low:type==='単勝'?0.25:1/24,central:type==='単勝'?0.25:1/24,
     high:type==='単勝'?0.25:1/24}};
};
const selected=[
 marketLine('単勝',[1],3.5,'B01'),
 marketLine('三連単',[2,3,4],50,'B02'),
 marketLine('三連単',[3,4,2],50,'B03'),
 marketLine('三連単',[4,2,3],50,'B04')
];
const args={selected_lines:selected,outcome_distributions:dist,frame_map,race_context,budget_yen:6000};
const before=evaluateStrategy(selected,dist,frame_map,race_context);
const proposed=optimizeWinStakeForRecovery(args);
assert.equal(proposed.algorithm,'win_recovery_staking_shadow_v1');
assert.equal(proposed.activated,false,'pilot MUST NOT autoactivate the formal forecast');
assert.equal(proposed.selected_lines[0].stake_yen,200,'3.5x win needs 200 yen to recover the other 300 yen');
assert.equal(proposed.total_stake_yen,500);
assert.equal(proposed.optimizer_audit.win_break_even_thresholds[0].win_only_break_even_stake_yen,200);
assert(proposed.loss_probability_scenarios.central<before.loss_probability_scenarios.central-0.1);
assert.equal(proposed.hit_probability_scenarios.central,before.hit_probability_scenarios.central,
 'changing stake does not increase probability of any ticket hitting');
assert(proposed.expected_net_profit_yen_scenarios.central>=
 before.expected_payout_yen_scenarios.central-before.total_stake_yen-200);
assert(proposed.optimizer_audit.only_win_ticket_amount_changed);
assert(proposed.selected_lines.slice(1).every((x,i)=>x.stake_yen===selected[i+1].stake_yen));
assert.deepEqual(selected.map(x=>x.stake_yen),[100,100,100,100],
 'original frozen tickets must remain untouched');
assert(proposed.optimizer_audit.trials_evaluated>0);
const repeat=optimizeWinStakeForRecovery(args);
assert.deepEqual(proposed.selected_lines,repeat.selected_lines,'stake proposals must be deterministic');

const alreadyCovered=optimizeWinStakeForRecovery({
 ...args,selected_lines:[marketLine('単勝',[1],5.0,'B01')]
});
assert.equal(alreadyCovered.selected_lines[0].stake_yen,100,'never artificially consume unused budget');
assert.equal(alreadyCovered.reason,'no_safe_material_recovery_improvement');
const noWin=optimizeWinStakeForRecovery({...args,selected_lines:selected.slice(1)});
assert.equal(noWin.total_stake_yen,300,'non-win tickets remain at original prices');
assert(noWin.optimizer_audit.selected_line_count_unchanged);
assert.throws(()=>optimizeWinStakeForRecovery({...args,budget_yen:6100}),/budget/);
assert.throws(()=>optimizeWinStakeForRecovery({
 ...args,selected_lines:[{...selected[0],quote_verified:false}]
}),/verified odds/);
assert.throws(()=>optimizeWinStakeForRecovery({
 ...args,selected_lines:[selected[0],{...selected[0],id:'duplicate'}]
}),/duplicated final ticket/);
console.log('PASS: 100→200 recovery break-even win-stake shadow pilot, unchanged hit rate, bounded EV, 6000 max, no mutation, no compulsory spend');
