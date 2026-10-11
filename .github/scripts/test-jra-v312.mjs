// v3.12 synthetic quote and real frozen-prediction regression. Never alters historic files.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {reconcileQuotes} from './jra-v312-quote-gate.mjs';
import {optimizeAndCompareV312} from './jra-v312-purchase-compare.mjs';
import {ticketKey} from './jra-strategy-engine-v39.mjs';
const ts='2030-10-11T09:00:00+09:00';
const q=(type,selection,odds)=>({type,selection,market_odds:odds,quote_verified:true,
 source_url:'https://example.org/odds',observed_at:ts,source_capture_sha256:'b'.repeat(64),
 source_capture_path:'e2e_validation/quote-evidence/fixture.json',
 market_selection_id:ticketKey(type,selection)});
const example={race_id:'2030-10-11-demo',race_context:{start_at:'2030-10-11T15:00:00+09:00'},
 strategies:[{strategy_id:'T1',type:'三連単',strategy_kind:'formation',
  definition:{slots:[[1],[2,3],[3,4]]}}],
 market_quotes:[q('三連単',[1,2,3],60),q('三連単',[1,2,4],70)]};
const coverage=reconcileQuotes(example);
assert.equal(coverage.generated_unique,3);
assert.equal(coverage.verified,2);
assert.equal(coverage.missing_count,1);
assert.equal(coverage.missing[0].key,ticketKey('三連単',[1,3,4]));
assert.equal(coverage.missing[0].reason,'not_collected');
const restored=reconcileQuotes({...example,market_quotes:[...example.market_quotes,q('三連単',[1,3,4],77)]});
assert.equal(restored.complete,true);
assert.equal(restored.missing_count,0);
const corrupted=reconcileQuotes({...example,market_quotes:[...example.market_quotes,
  {...q('三連単',[1,3,4],77),market_odds:null}]});
assert.equal(corrupted.missing[0].reason.includes('invalid_or_unverified_odds'),true);
const path='e2e_validation/predictions/2026-10-11-ireland-trophy/v3.11-run38101635486-attempt1.json';
const old=JSON.parse(fs.readFileSync(path,'utf8'));
const args={budget_yen:6000,strategies:old.purchase_strategy_evaluations,
 outcome_distributions:old.outcome_distributions,frame_map:old.frame_map,
 race_context:old.race_context,freeze_at:old.final_bets_fixed_at};
const updated=optimizeAndCompareV312(args);
const audit=updated.optimizer_audit.v312_purchase_comparison;
assert.equal(updated.total_stake_yen<=6000,true);
assert.equal(updated.algorithm,'v312_single_swap_audited_neighbourhood');
assert.equal(audit.screened.attempted_add_or_swap>0,true,'screened count must be nonzero');
assert.equal(audit.screened.economic_feasible>=audit.screened.correlated_evaluated,true);
assert.equal(audit.incremental_hit_subsets.at(-1).ticket_count,updated.selected_lines.length);
assert.equal(audit.incremental_hit_subsets.at(-1).hit_probability_scenarios.central,
  updated.hit_probability_scenarios.central);
assert.equal(audit.strategy_mode_comparisons.length>0,true);
assert.equal(audit.baseline.expected_net_profit_yen_scenarios.central>0,true);
assert.equal(audit.screened.correlated_evaluated===0,Boolean(audit.zero_trial_explanation));
assert.equal(old.purchase_portfolio_selection.optimizer_audit.balanced_selection.hit_probability_gain,0,
 'old original must remain unchanged, including the previously missing comparison');
console.log('PASS v3.12: missing trifecta odds fail, exact price repairs pass, all choice-set audit fields and legacy intact');
