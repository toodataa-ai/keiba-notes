#!/usr/bin/env python3
"""Do not allow omission, duplicate insertion, invented odds, or unnamed bets."""
import importlib.util, pathlib, unittest, copy
p=pathlib.Path(__file__).with_name('jra-v315-value-column-v1.py')
spec=importlib.util.spec_from_file_location('value_col',p)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class ValueColumnContract(unittest.TestCase):
 def setUp(self):
  self.src={'prompt_version':'v3.13','stage':'formal_prestart','proof_commit':'a'*40,'step1_fixed_at':'2026-11-01T08:00:00+09:00',
   'race_context':{'date':'2026-11-01','venue':'東京'},'step1_ranking':[
    {'horse_number':1,'horse_name':'一番馬','mark':'◎'},{'horse_number':2,'horse_name':'二番馬','mark':'○'}]}
  self.p={'purchase_strategy_version':'v3.15','status':'formal_prestart','purchase_decision':'buy',
   'source_prediction_proof':'a'*40,'step1_fixed_at':self.src['step1_fixed_at'],'race_context':self.src['race_context'],
   'formal_bets':[{'type':'馬連','selection':[1,2],'stake_yen':100,'market_selection_id':'馬連:[1,2]',
      'quote_verified':True,'market_odds':21.2}],
   'total_stake_yen':100,'regular_commands':[{'type':'馬連','definition':{'selection':[1,2]},'points':1,'ticket_keys':['馬連:[1,2]']}],
   'purchase_metrics':{'modeled_expected_net_profit_yen':36.5,'modeled_net_loss_probability':0.52}}
 def test_column_is_real_names_and_executed_value(self):
  note,names=mod.column(self.p,self.src)
  for term in ('妙味','期待値','一番馬','二番馬','21.2倍','37円','52.0%'):
   self.assertIn(term,note)
  self.assertEqual(names,['一番馬','二番馬'])
 def test_inserts_immediately_after_bet_table_not_new_box(self):
  original='<section class="page">'+mod.ANCHOR+'<table><tr><td>馬連</td></tr></table><p>固定印</p></section>'
  note,_=mod.column(self.p,self.src)
  new=mod.apply(original,note)
  self.assertEqual(new.replace(note,'',1),original)
  self.assertTrue(new.index('</table>')<new.index(mod.TITLE)<new.index('固定印'))
  self.assertNotIn('class="hero"',note)
  with self.assertRaisesRegex(ValueError,'already present'):
   mod.apply(new,note)
 def test_fail_closed_on_missing_quote_and_proof_mismatch(self):
  c=copy.deepcopy(self.p);c['formal_bets'][0]['quote_verified']=False
  with self.assertRaisesRegex(ValueError,'verified purchased'):mod.column(c,self.src)
  c=copy.deepcopy(self.p);c['source_prediction_proof']='b'*40
  with self.assertRaisesRegex(ValueError,'proof mismatch'):mod.column(c,self.src)
 def test_pass_decision_has_reason_and_named_horse(self):
  c=copy.deepcopy(self.p);c.update(purchase_decision='pass',formal_bets=[],total_stake_yen=0,regular_commands=[])
  note,names=mod.column(c,self.src)
  self.assertIn('見送り',note);self.assertIn('一番馬',note)
  self.assertEqual(names,['一番馬'])
if __name__=='__main__':unittest.main()
