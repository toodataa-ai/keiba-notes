// Synthetic fixtures only, never imply market odds or outcomes were observed live.
import assert from 'node:assert/strict';
import {inspectExactQuoteCoverageV312,auditPurchaseSetComparisonsV312} from './jra-purchase-audit-v312.mjs';
import {optimizeBalancedPortfolio} from './jra-balanced-optimizer-v311.mjs';
import {ticketKey} from './jra-strategy-engine-v39.mjs';

const triplets=[];
for(let a=1;a<=4;a++)for(let b=1;b<=4;b++)for(let c=1;c<=4;c++)
 if(a!==b&&a!==c&&b!==c)triplets.push({finish:[a,b,c],probability:1/24});
const args={budget_yen:6000,
 race_context:{start_at:'2030-10-11T15:00:00+09:00',offered_types:['単勝'],place_paid_positions:3},
 frame_map:{1:1,2:2,3:3,4:4},freeze_at:'2030-10-11T09:01:00+09:00',
 outcome_distributions:{low:triplets,central:triplets,high:triplets}};
const odds=[5,4.6,3.88,1.2];
const mk=(n)=>({type:'単勝',selection:[n],stake_yen:100,market_odds:odds[n-1],
 quote_verified:true,source_url:'https://example.org/synthetic-test-only',
 observed_at:'2030-10-11T09:00:00+09:00',market_selection_id:ticketKey('単勝',[n])});
args.strategies=[1,2,3,4].map(n=>({strategy_id:'S'+n,type:'単勝',strategy_kind:'single',lines:[mk(n)]}));
const coverage=inspectExactQuoteCoverageV312(args.strategies);
assert.equal(coverage.missing_count,0);
assert.equal(coverage.total_candidates,4);
assert.equal(coverage.priced,4);
const bad=structuredClone(args.strategies);
bad[2].lines[0].quote_verified=false;
assert.equal(inspectExactQuoteCoverageV312(bad,{strict:false}).missing_count,1);
assert.throws(()=>inspectExactQuoteCoverageV312(bad),/BLOCKER: exact prereace odds incomplete/);
const crossed=structuredClone(args.strategies);
crossed.push({strategy_id:'duplicated-missing',type:'単勝',strategy_kind:'single',lines:[{...mk(2),quote_verified:false}]});
assert.throws(()=>inspectExactQuoteCoverageV312(crossed),/inconsistent exact quote/);
const balance=optimizeBalancedPortfolio(args);
const audit=auditPurchaseSetComparisonsV312(args,balance);
assert.equal(audit.original_purchase_unchanged,true);
assert.equal(audit.mode_comparisons.length,args.strategies.length);
assert(audit.comparison_sets.some(t=>t.kind==='final_balanced'));
assert(audit.comparison_sets.some(t=>t.kind==='exact_profit_baseline'));
assert(audit.comparison_sets.some(t=>t.kind==='illustrative_max_marginal_hit'&&t.tickets===1));
assert.equal(audit.comparison_sets.find(t=>t.kind==='final_balanced').tickets,balance.selected_lines.length);
assert(Number.isFinite(audit.search_diagnostic.no_marginal_hit_gain));
assert(audit.comparison_sets.every(t=>t.hit_pct!==null&&t.profit_yen!==null));
assert(balance.selected_lines.every(t=>audit.comparison_sets.find(x=>x.kind==='final_balanced').keys.includes(ticketKey(t.type,t.selection))));
console.log('PASS JRA v3.12: exact quote fail-closed, deduplication, correlated 1-to-N comparison, nonmutating v3.11 purchase.');
