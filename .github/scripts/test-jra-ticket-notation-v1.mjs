import assert from 'node:assert/strict';
import {formatPurchaseCommand as f} from './jra-ticket-notation-v1.mjs';
import {expandStrategy,ticketKey} from './jra-strategy-engine-v39.mjs';
import {compareThreePlusAna} from './jra-three-plus-ana-shadow-v1.mjs';
import fs from 'node:fs';
const cases=[
 [{type:'単勝',method:'single',definition:{selection:[2]}},'2'],
 [{type:'複勝',method:'single',definition:{selection:[9]}},'9'],
 [{type:'枠連',method:'single',definition:{selection:[4,2]}},'2－4'],
 [{type:'馬連',method:'single',definition:{selection:[9,2]}},'2－9'],
 [{type:'ワイド',method:'single',definition:{selection:[9,2]}},'2－9'],
 [{type:'馬単',method:'single',definition:{selection:[2,9]}},'2→9'],
 [{type:'三連複',method:'single',definition:{selection:[9,2,10]}},'2－9－10'],
 [{type:'三連単',method:'single',definition:{selection:[2,9,10]}},'2→9→10'],
 [{type:'三連単',method:'box',definition:{horses:[10,2,9]}},'2・9・10 BOX'],
 [{type:'三連複',method:'box',definition:{horses:[10,2,9]}},'2・9・10 BOX'],
 [{type:'馬連',method:'key_wheel',definition:{key:2,partners:[10,4,9]}},'2－（4・9・10）'],
 [{type:'ワイド',method:'key_wheel',definition:{key:2,partners:[10,4,9]}},'2－（4・9・10）'],
 [{type:'馬単',method:'key_wheel_first',definition:{key:2,partners:[4,9]}},'2→（4・9）'],
 [{type:'馬単',method:'key_wheel_second',definition:{key:2,partners:[4,9]}},'（4・9）→2'],
 [{type:'馬単',method:'key_wheel_multi',definition:{key:2,partners:[4,9]}},'2⇄（4・9）（馬単マルチ）'],
 [{type:'三連複',method:'one_key_wheel',definition:{key:2,partners:[1,4,9]}},'軸：2 ／ 相手：1・4・9'],
 [{type:'三連複',method:'two_key_wheel',definition:{axes:[9,2],partners:[1,4,13]}},'軸：2・9 ／ 相手：1・4・13'],
 [{type:'三連単',method:'two_key_fixed',definition:{axes:[2,9],positions:[1,2],partners:[1,4]}},'2→9→（1・4）'],
 [{type:'三連単',method:'two_key_fixed',definition:{axes:[2,9],positions:[1,3],partners:[1,4]}},'2→（1・4）→9'],
 [{type:'三連単',method:'one_key_fixed',definition:{key:2,position:1,partners:[1,9,10]}},'2→（1・9・10）→（1・9・10）（相手は異なる2頭）'],
 [{type:'三連単',method:'one_key_multi',definition:{key:2,partners:[1,9,10]}},'2＋（1・9・10）から2頭（3連単全着順マルチ）'],
 [{type:'三連単',method:'two_key_multi',definition:{axes:[9,2],partners:[1,4]}},'2・9＋（1・4）から1頭（3連単全着順マルチ）'],
 [{type:'三連単',method:'formation',definition:{slots:[[2,4],[9],[1,10]]}},'（2・4）→（9）→（1・10）'],
 [{type:'三連複',method:'formation',definition:{slots:[[2],[9,4],[1,10]]}},'（2）－（4・9）－（1・10）'],
 [{type:'馬単',method:'formation',definition:{slots:[[2],[9,4]]}},'（2）→（4・9）'],
 [{type:'馬連',method:'formation',definition:{slots:[[2,4],[9,10]]}},'（2・4）－（9・10）']
];
for(const [v,expected] of cases){
 const actual=f(v);
 assert.equal(actual,expected,JSON.stringify(v));
 const bets=expandStrategy(v.type,v.method,v.definition);
 assert.ok(bets.length>=1);
 assert.equal(new Set(bets.map(x=>ticketKey(x.type,x.selection))).size,bets.length);
}
assert.notEqual(f({type:'三連単',method:'single',definition:{selection:[2,9,10]}}),
  f({type:'三連単',method:'single',definition:{selection:[10,9,2]}}),'order must matter for trifecta');
assert.equal(f({type:'三連複',method:'single',definition:{selection:[2,9,10]}}),
  f({type:'三連複',method:'single',definition:{selection:[10,9,2]}}),'order must not matter for trio');
assert.throws(()=>f({type:'三連単',method:'unknown',definition:{selection:[2,9,10]}}),/NOTATION_BLOCKER/);
const fpaths=[
 'e2e_validation/predictions/2026-10-12-october-stakes/v3.13-run38177939515-attempt2.json',
 'e2e_validation/predictions/2026-10-12-swan-stakes/v3.13-run38177942081-attempt2.json'
];
for(const filename of fpaths){
 const original=fs.readFileSync(filename),d=JSON.parse(original);
 const res=compareThreePlusAna({budget_yen:6000,strategies:d.purchase_strategy_evaluations,
  formal_final_bets:d.final_bets,outcome_distributions:d.outcome_distributions,
  frame_map:d.frame_map,race_context:d.race_context,freeze_at:d.final_bets_fixed_at});
 assert.deepEqual(res.regular_commands.map(x=>x.jra_input),
  res.regular_commands.map(x=>f(x)),'display drift from canonical notation');
 if(res.ana_command.method!=='pass')assert.equal(res.ana_command.jra_input,f(res.ana_command));
 assert.equal(Buffer.compare(original,fs.readFileSync(filename)),0,'sealed formal original changed');
 assert.ok(res.regular_commands.length<=3,'3 row UI cap');
 console.log('PASS_NOTATION_REAL_SEALED',d.race_id,JSON.stringify(res.regular_commands.map(x=>[x.type,x.jra_input])));
}
console.log('PASS_JRA_CANONICAL_NOTATION',cases.length,'methods and both sealed races');

