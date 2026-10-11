// A PDF layout fixture derived from an immutable old prediction.
// Any v3.12 version marker is test-local; historical STEP1, PDFs and prediction are never saved.
import fs from 'node:fs';
import {optimizeAndCompareV312} from './jra-v312-purchase-compare.mjs';
const source='e2e_validation/predictions/2026-10-11-ireland-trophy/v3.11-run38101635486-attempt1.json';
const old=JSON.parse(fs.readFileSync(source,'utf8'));
const args={budget_yen:6000,strategies:old.purchase_strategy_evaluations,
 outcome_distributions:old.outcome_distributions,frame_map:old.frame_map,
 race_context:old.race_context,freeze_at:old.final_bets_fixed_at};
const portfolio=optimizeAndCompareV312(args);
const finalBets=portfolio.selected_lines.map((x,i)=>({id:'B'+String(i+1).padStart(2,'0'),
 type:x.type,selection:x.selection,stake_yen:x.stake_yen,market_odds:x.market_odds,
 market_selection_id:x.market_selection_id,source_url:x.source_url,observed_at:x.observed_at}));
const fixture={...old,prompt_version:'v3.12',purchase_portfolio_selection:portfolio,
 final_bets:finalBets,total_stake_yen:portfolio.total_stake_yen,
 test_only:true,notes:['INTERNAL TEST ONLY: old source odds incomplete; NEVER publish this fixture']};
fs.writeFileSync(process.argv[2],JSON.stringify(fixture,null,2)+'\n');
console.log('v3.12 synthetic PDF fixture rows',finalBets.length,'unpriced',old.market_quote_audit.missing_individual_lines);
