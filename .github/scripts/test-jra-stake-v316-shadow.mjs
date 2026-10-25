// Synthetic v3.16 staking-only acceptance tests. No official prediction write access.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {ticketKey,evaluateStrategy} from './jra-strategy-engine-v39.mjs';
import {compareV316Shadow,V316_SHADOW_POLICY} from './jra-stake-optimizer-v316-shadow.mjs';

const observed='2030-10-25T08:59:00+09:00';
const line=(type,selection,odds)=>({
 type,selection,market_odds:odds,stake_yen:100,quote_verified:true,
 market_selection_id:ticketKey(type,selection),
 observed_at:observed,source_url:'https://example.org/verified-odds'
});
const outcomes=[];
for(let a=1;a<=4;a++)for(let b=1;b<=4;b++)for(let c=1;c<=4;c++)
 if(a!==b&&b!==c&&a!==c)outcomes.push({finish:[a,b,c],probability:1/24});
const scenario={low:outcomes,central:outcomes,high:outcomes};
const race={start_at:'2030-10-25T15:40:00+09:00',
 sale_field_size:4,place_paid_positions:2,offered_types:['単勝','馬単']};
const command=(x,category,row)=>({
 category,row,type:x.type,method:'single',jra_input:x.selection.join('→'),
 definition:{selection:x.selection},points:1,unit_stake_yen:100,stake_yen:100,
 ticket_keys:[ticketKey(x.type,x.selection)]
});
function fixture(winOdds=9.0){
 const base=[line('単勝',[1],winOdds),line('単勝',[2],winOdds),line('馬単',[3,4],100)];
 const source={
  prompt_version:'v3.13',stage:'formal_prestart',race_id:'synthetic-prestart-test',
  proof_commit:'a'.repeat(40),race_context:race,frame_map:{1:1,2:2,3:3,4:4},
  outcome_distributions:scenario,final_bets_fixed_at:'2030-10-25T09:01:00+09:00',
  purchase_strategy_evaluations:base.map((l,i)=>({
   strategy_id:'synthetic-'+i,lines:[structuredClone(l)]
  }))
 };
 const sourceBytes=JSON.stringify(source)+'\n';
 const metric=evaluateStrategy(base,scenario,source.frame_map,race);
 const formal={
  purchase_strategy_version:'v3.15',source_race_id:source.race_id,
  source_prediction_sha256:crypto.createHash('sha256').update(sourceBytes).digest('hex'),
  source_prediction_proof:source.proof_commit,proof_commit:'b'.repeat(40),
  final_bets_fixed_at:'2030-10-25T09:02:00+09:00',
  formal_bets:structuredClone(base),regular_commands:[
   command(base[0],'通常',1),command(base[1],'通常',2)
  ],medium_command:{category:'中穴',method:'pass',points:0,stake_yen:0},
  large_command:command(base[2],'大穴',5),
  total_stake_yen:300,
  purchase_metrics:{
   modeled_expected_net_profit_yen:metric.expected_payout_yen_scenarios.central-300,
   modeled_low_expected_net_profit_yen:metric.expected_payout_yen_scenarios.low-300,
   modeled_net_loss_probability:metric.loss_probability_scenarios.central
  }
 };
 return {source,sourceBytes,formal};
}
const f=fixture();
const beforeS=JSON.stringify(f.source),beforeF=JSON.stringify(f.formal);
const result=compareV316Shadow(f);
assert.equal(result.activated,false);
assert.equal(result.publication_allowed,false);
assert.equal(result.shadow_proposal_available,true);
assert(result.candidate.stake_yen>result.baseline.stake_yen);
assert(result.delta.central_expected_profit_yen>=V316_SHADOW_POLICY.minimum_expected_profit_gain_yen);
assert(result.candidate.scenarios.central.loss_probability<=result.baseline.scenarios.central.loss_probability+1e-8);
assert(result.candidate.scenarios.low.expected_net_profit_yen>=result.baseline.scenarios.low.expected_net_profit_yen);
assert.equal(result.audit.unchanged_ticket_set,true);
assert.equal(result.audit.unchanged_purchase_command_count,true);
assert.equal(result.audit.unchanged_hit_probability,true);
assert.equal(result.audit.speculation_stays_at_100_yen,true);
assert(result.commands.filter(x=>x.category==='通常').some(x=>x.unit_stake_yen>100));
assert.equal(result.commands.find(x=>x.category==='大穴').unit_stake_yen,100);
assert(result.commands.every(x=>x.unit_stake_yen%100===0));
assert.deepEqual(result.proposed_lines.map(x=>x.market_selection_id),
 f.formal.formal_bets.map(x=>x.market_selection_id));
assert.equal(JSON.stringify(f.source),beforeS,'original source must be unmodified');
assert.equal(JSON.stringify(f.formal),beforeF,'formal tickets must be unmodified');
assert.deepEqual(compareV316Shadow(f).commands,result.commands,'deterministic replay');
const badEdge=fixture(2.0),rejected=compareV316Shadow(badEdge);
assert.equal(rejected.shadow_proposal_available,false,'never increase stakes on negative-edge options');
const tampered=fixture();
tampered.formal.source_prediction_sha256='0'.repeat(64);
assert.throws(()=>compareV316Shadow(tampered),/SHA256 mismatch/);
const tamperedOdds=fixture();
tamperedOdds.formal.formal_bets[0].market_odds=101;
assert.throws(()=>compareV316Shadow(tamperedOdds),/traced exactly/);
const duplicated=fixture();
duplicated.formal.formal_bets[1]=duplicated.formal.formal_bets[0];
assert.throws(()=>compareV316Shadow(duplicated),/repeated bet/);
const stale=fixture();
stale.formal.final_bets_fixed_at='2030-10-25T15:45:00+09:00';
assert.throws(()=>compareV316Shadow(stale),/not frozen before/);
console.log('PASS_V316_SYNTHETIC shadow only; group-unit 100-yen grid; original proofs, source quotes, 6000 ceiling; unchanged selections and speculative unit stakes; bounded EV/low-case/loss probability');
