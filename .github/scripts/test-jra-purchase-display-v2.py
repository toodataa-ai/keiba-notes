#!/usr/bin/env python3
"""Fast exact-purchase regression: user-facing BOX/wheel commands must match final_bets."""
import importlib.util
import json
from itertools import combinations,permutations
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
path=ROOT/'.github/scripts/jra-pdf-presentation-overlay-v2.py'
spec=importlib.util.spec_from_file_location('jra_display_v2',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
old=m.old
def prediction(typ,selections,amount=100,strategies=None):
 return {'final_bets':[{'id':'B'+str(i),'type':typ,'selection':list(sel),'stake_yen':amount}
  for i,sel in enumerate(selections)],
  'purchase_strategy_evaluations':strategies or []}
def check_coverage(d):
 cmds=old.purchase_commands(d)
 tickets={old.bet_key(x) for x in d['final_bets']}
 seen=[]
 for row in cmds:
  seen+=list(row['_keys'])
 assert len(seen)==len(tickets)==len(set(seen))
 assert set(seen)==tickets
 assert sum(x['amount_yen'] for x in cmds)==sum(x['stake_yen'] for x in d['final_bets'])
 return cmds

class TestTrueExactGroups(unittest.TestCase):
 def test_wide_and_same_stake(self):
  d=prediction('ワイド',[(1,2),(1,3),(1,4)])
  cmds=check_coverage(d)
  self.assertEqual(len(cmds),1)
  self.assertEqual(cmds[0]['method'],'1頭軸流し')
  self.assertEqual(cmds[0]['tickets'],3)
  d['final_bets'][0]['stake_yen']=200
  self.assertNotEqual(len(check_coverage(d)),1)
 def test_exacta_multi(self):
  d=prediction('馬単',[(1,2),(2,1),(1,3),(3,1)])
  cmds=check_coverage(d)
  self.assertEqual(len(cmds),1)
  self.assertEqual(cmds[0]['method'],'1頭軸マルチ')
 def test_trio_two_keys(self):
  d=prediction('三連複',[(1,2,3),(1,2,4),(1,2,5)])
  cmds=check_coverage(d)
  self.assertEqual(len(cmds),1)
  self.assertEqual(cmds[0]['method'],'2頭軸流し')
 def test_trifecta_two_key_multi(self):
  selections=[x for p in (3,4) for x in permutations([1,2,p])]
  d=prediction('三連単',selections)
  cmds=check_coverage(d)
  self.assertEqual(len(cmds),1)
  self.assertEqual(cmds[0]['method'],'2頭軸マルチ')
  self.assertEqual(cmds[0]['tickets'],12)
 def test_missing_one_ticket_never_claim_multi(self):
  selections=[x for p in (3,4) for x in permutations([1,2,p])]
  selections.remove((4,1,2))
  cmds=check_coverage(prediction('三連単',selections))
  self.assertFalse(any(x['method']=='2頭軸マルチ' for x in cmds))
 def test_trifecta_one_key_fixed(self):
  d=prediction('三連単',[(1,*x) for x in permutations((2,3,4),2)])
  cmds=check_coverage(d)
  self.assertEqual(len(cmds),1)
  self.assertEqual(cmds[0]['method'],'1頭軸固定')
 def test_previous_two_real_races_nonregression(self):
  files=[
   ROOT/'e2e_validation/predictions/2026-10-11-ireland-trophy/v3.12-rerun38113832729-attempt1.json',
   ROOT/'e2e_validation/predictions/2026-10-11-uzumasa-stakes/v3.12-rerun38113827050-attempt2.json'
  ]
  for p in files:
   with self.subTest(p=p.name):
    d=json.loads(p.read_text())
    old._display_only_group_candidates=m.v1_derived
    try: original=check_coverage(d)
    finally:old._display_only_group_candidates=m.better_derived
    enhanced=check_coverage(d)
    self.assertLessEqual(len(enhanced),len(original))
    self.assertEqual(sum(x['amount_yen'] for x in enhanced),
                     sum(x['stake_yen'] for x in d['final_bets']))
if __name__=='__main__':
 unittest.main(verbosity=2)
