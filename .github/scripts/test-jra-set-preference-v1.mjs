import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {compareSetPreferredPortfolio} from './jra-set-preference-v1.mjs';
import {expandStrategy,ticketKey} from './jra-strategy-engine-v39.mjs';

const TYPES=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'];
const freeze='2026-10-12T12:00:00+09:00';
function probabilities(){
 const permutations=[];
 for(let a=1;a<=6;a++)for(let b=1;b<=6;b++)if(b!==a)
  for(let c=1;c<=6;c++)if(c!==a&&c!==b)
   permutations.push({finish:[a,b,c],probability:1/120});
 return {low:permutations,central:permutations,high:permutations};
}
const outcomes=probabilities();
const odds=new Map();
const quote=(type,sel,amount)=>({
 type,selection:sel,stake_yen:100,market_odds:amount,
 source_url:'https://sports.yahoo.co.jp/keiba/race/odds/ur/FAKE_FIXTURE',
 observed_at:'2026-10-12T11:59:00+09:00',market_selection_id:ticketKey(type,sel),
 quote_verified:true
});
function fixture(badPrice=25){
 const picks=[[1,2],[1,3],[1,4],[1,5],[2,3]].map(s=>quote('馬連',s,25));
 const market=[...picks,quote('馬連',[1,6],badPrice)];
 const st=[
  {strategy_id:'FULL_WHEEL',type:'馬連',strategy_kind:'key_wheel',
   definition:{key:1,partners:[2,3,4,5,6]},lines:market.filter(x=>x.selection.includes(1))},
  ...picks.map((x,i)=>({strategy_id:'S'+i,type:'馬連',strategy_kind:'single',
   definition:{selection:x.selection},lines:[x]}))
 ];
 return {budget_yen:6000,strategies:st,baseline_selected_lines:picks,
  outcome_distributions:outcomes,frame_map:Object.fromEntries([1,2,3,4,5,6].map(x=>[String(x),Math.min(x,8)])),
  freeze_at:freeze,race_context:{start_at:'2026-10-12T15:30:00+09:00',
   sale_field_size:6,place_paid_positions:2,offered_types:TYPES}};
}
{
 const data=fixture(),original=JSON.stringify(data),res=compareSetPreferredPortfolio(data);
 assert.equal(JSON.stringify(data),original,'SET2 shadow cannot mutate source');
 assert.equal(res.activated,true,'positive-edge expanded wheel should displace more fragmented baseline');
 assert.equal(res.status,'eligible_shadow_candidate');
 assert.equal(res.baseline.command_count,5);
 assert.equal(res.proposed.command_count,2);
 assert.equal(res.proposed.ticket_count,6);
 assert.equal(res.commands.filter(x=>x.method==='key_wheel').length,1);
 assert.equal(res.proposed.total_stake_yen,600);
 assert.ok(res.proposed.hit_probability>res.baseline.hit_probability);
 assert.ok(res.proposed.expected_net_profit_yen>res.baseline.expected_net_profit_yen);
 assert.equal(res.formal_prediction_unchanged,true);
 assert.deepEqual(new Set(res.commands.flatMap(x=>x.ticket_keys)),
  new Set(res.proposed_lines.map(x=>ticketKey(x.type,x.selection))));
 console.log('PASS_SET_PREFERENCE_complete_wheel_and_correct_portfolio_metrics');
}
{
 const data=fixture(1.01),res=compareSetPreferredPortfolio(data);
 assert.equal(res.activated,false,'must not buy complete group if marginal EV is negative');
 assert.equal(res.proposed.command_count,5);
 assert.equal(res.proposed.total_stake_yen,500);
 console.log('PASS_SET_PREFERENCE_decline_economically_bad_wheel');
}
{
 const data=fixture();
 data.baseline_selected_lines[0].market_odds=44;
 assert.throws(()=>compareSetPreferredPortfolio(data),/baseline selection differs from verified quotes/);
 console.log('PASS_SET_PREFERENCE_refuse_baseline_quote_mismatch');
}
{
 const data=fixture();
 data.strategies[0].lines.pop();
 const res=compareSetPreferredPortfolio(data);
 assert.equal(res.activated,false,'incomplete BOX/formation/wheel must never become a full purchase');
 assert.equal(res.rejected.incomplete,1);
 console.log('PASS_SET_PREFERENCE_refuse_partial_betting_command');
}
{
 const data=fixture();
 data.strategies[0].lines[0].quote_verified=false;
 const res=compareSetPreferredPortfolio(data);
 assert.equal(res.activated,false,'group must require full priced source evidence');
 console.log('PASS_SET_PREFERENCE_refuse_unpriced_group');
}
{
 const data=fixture();
 data.baseline_selected_lines=[];
 const res=compareSetPreferredPortfolio(data);
 assert.equal(res.activated,false);
 assert.equal(res.status,'no_buy_baseline');
 console.log('PASS_SET_PREFERENCE_no_market_value_no_bets');
}
// Actual archived, prestart-formal v3.12 data. This is an offline historical REPLAY,
// never a refit against race results and never a rewrite of old final_bets.
const archive=[
 'e2e_validation/predictions/2026-10-11-ireland-trophy/v3.12-rerun38113832729-attempt1.json',
 'e2e_validation/predictions/2026-10-11-uzumasa-stakes/v3.12-rerun38113827050-attempt2.json'
];
for(const file of archive){
 const bytes=fs.readFileSync(file),before=createHash('sha256').update(bytes).digest('hex'),record=JSON.parse(bytes);
 const result=compareSetPreferredPortfolio({
  budget_yen:6000,strategies:record.purchase_strategy_evaluations,
  baseline_selected_lines:record.purchase_portfolio_selection.selected_lines,
  outcome_distributions:record.outcome_distributions,frame_map:record.frame_map,
  race_context:record.race_context,freeze_at:record.final_bets_fixed_at
 });
 assert.equal(result.formal_prediction_unchanged,true);
 assert.equal(result.proposed.command_count<=result.baseline.command_count,true);
 assert.equal(result.proposed.total_stake_yen<=6000,true);
 assert.ok(result.baseline.ticket_count>=0);
 assert.equal(createHash('sha256').update(fs.readFileSync(file)).digest('hex'),before,
  'historical record SHA changed in replay');
 assert.equal(record.prompt_version,'v3.12');
 console.log('PASS_SET_PREFERENCE_ARCHIVED_REPLAY',record.race_id,JSON.stringify({
  active:result.activated,candidates:result.candidate_group_count,considered:result.considered,
  baseline:result.baseline,proposed:result.proposed
 }));
}
