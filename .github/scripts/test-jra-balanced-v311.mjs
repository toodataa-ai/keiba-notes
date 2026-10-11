// Synthetic fixtures only: these prices are NOT live market odds.
import assert from 'node:assert/strict';
import {ticketKey} from './jra-strategy-engine-v39.mjs';
import {optimizePurchasePortfolio} from './jra-portfolio-optimizer-v310.mjs';
import {optimizeBalancedPortfolio} from './jra-balanced-optimizer-v311.mjs';
const combos=[];
for(let a=1;a<=4;a++)for(let b=1;b<=4;b++)for(let c=1;c<=4;c++)
 if(a!==b&&a!==c&&b!==c)combos.push({finish:[a,b,c],probability:1/24});
const distributions={low:combos,central:combos,high:combos};
const time='2030-10-11T09:00:00+09:00';
const settings={budget_yen:6000,outcome_distributions:distributions,
  frame_map:{1:1,2:2,3:3,4:4},
  race_context:{start_at:'2030-10-11T15:00:00+09:00',offered_types:['単勝'],place_paid_positions:3},
  freeze_at:'2030-10-11T09:01:00+09:00'};
function priced(id,odds){
 const key=ticketKey('単勝',[id]);
 return {type:'単勝',selection:[id],stake_yen:100,market_odds:odds,quote_verified:true,
  market_selection_id:key,source_url:'https://example.org/synthetic',observed_at:time};
}
const strategies=[1,2,3,4].map((id,i)=>({strategy_id:'S'+id,lines:[priced(id,[5,4.6,3.88,1.2][i])]}));
const args={...settings,strategies};
const exact=optimizePurchasePortfolio(args);
const balanced=optimizeBalancedPortfolio(args);
assert.equal(exact.selected_lines.length,2,'exact-EV policy should reject small negative hedge');
assert.equal(balanced.selected_lines.length,3,'balanced policy should adopt higher-hit-rate set');
assert(balanced.selected_lines.some(x=>x.expected_profit_yen<0),'a bounded negative-EV hedge must be considered as part of a positive-EV set');
assert(balanced.expected_net_profit_yen_scenarios.central>0,'whole portfolio must retain positive expected net profit');
assert(balanced.expected_net_profit_yen_scenarios.central>=exact.optimizer_audit.expected_net_profit_yen*0.9-1e-7);
assert(balanced.hit_probability_scenarios.central>exact.hit_probability_scenarios.central+0.2);
assert(balanced.loss_probability_scenarios.central<exact.loss_probability_scenarios.central);
assert.equal(balanced.total_stake_yen,300);
assert(balanced.optimizer_audit.considered_excluded.some(x=>x.selection[0]===4),'negative unhelpful ticket exclusion recorded');
assert.equal(balanced.optimizer_audit.balanced_selection.optimality,'heuristic_risk_neighbourhood_not_global');
const expensive=optimizeBalancedPortfolio({...args,strategies:[{strategy_id:'single-high',lines:[priced(1,5)]}]});
assert.equal(expensive.total_stake_yen,100,'no artificial purchase quota');
const noValue=optimizeBalancedPortfolio({...args,strategies:[{strategy_id:'loss-only',lines:[priced(1,2)]}]});
assert.equal(noValue.purchase_decision,'pass');
assert.equal(noValue.total_stake_yen,0);
const unverified=optimizeBalancedPortfolio({...args,strategies:[
 {strategy_id:'one',lines:[priced(1,5)]},
 {strategy_id:'unverified',lines:[{...priced(2,100),quote_verified:false}]}
]});
assert.equal(unverified.selected_lines.length,1,'unverified quote must never be bought');
assert.throws(()=>optimizeBalancedPortfolio({...args,budget_yen:6100}),/6000/);
console.log('PASS v3.11: correlated union hit, bounded profit sacrifice, net loss, provenance, no spend-to-cap');
