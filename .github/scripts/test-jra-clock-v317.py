#!/usr/bin/env python3
"""Deterministic offline regression against actual immutable JRA evidence; no prices."""
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.github/scripts'))
from jra_clock_v1 import recover,official_clock,shadow_signal

class TestJRAClock(unittest.TestCase):
    def test_short_and_long_formats(self):
        examples=[
            ('2026年8月2日 新潟 アイビスSD 4 着 57.0 kg 1000芝 54.2 良 520 kg 3F 32.0',1000,'芝',4,'54.2'),
            ('2026年8月2日 札幌 1 着 56.0 kg 1000ダ 59.7 良 510 kg 3F 35.0',1000,'ダート',1,'59.7'),
            ('2026年8月2日 小倉 2 着 56.0 kg 1000ダ 1:00.1 良',1000,'ダート',2,'1:00.1'),
            ('2026年8月2日 京都 1 着 57.0 kg 1200芝 1:08.1 良',1200,'芝',1,'1:08.1'),
            ('2026年8月2日 京都 1 着 57.0 kg 2600芝 2:40.0 稍重',2600,'芝',1,'2:40.0'),
            ('2026年8月2日 京都 1 着 57.0 kg 1000芝 良 520 kg 3F 32.0',1000,'芝',1,None),
            ('2026年8月2日 京都 中止 57.0 kg 1000芝 良',1000,'芝',None,None),
            ('2026年8月2日 京都 1 着 57.0 kg 1000芝 1:68.1 良',1000,'芝',1,None),
        ]
        for text,dist,surface,finish,expected in examples:
            got=official_clock(text,dist,surface,finish)
            self.assertEqual((got or (None,))[0],expected)

    def test_fourteen_actual_races(self):
        names=['2026-10-12-october-stakes','2026-10-12-swan-stakes',
               '2026-10-17-fuji-stakes','2026-10-17-hokuriku-stakes',
               '2026-10-17-tourmaline-stakes','2026-10-18-brazil-cup',
               '2026-10-18-niigata-himba-stakes','2026-10-18-shuka-sho',
               '2026-10-24-artemis-stakes','2026-10-24-cassiopeia-stakes',
               '2026-10-24-uonuma-stakes','2026-10-25-kannazuki-stakes',
               '2026-10-25-kikka-sho','2026-10-25-lumiere-autumn-dash']
        stats=dict(rows=0,unchanged=0,recovered=0,legitimate_absence=0)
        for race in names:
            data=json.loads((ROOT/'e2e_validation/inputs/v313'/(race+'.json')).read_text(encoding='utf8'))
            for horse in data['step1']['runners']:
                for p in horse.get('past_performances',[]):
                    new=recover(p)
                    stats['rows']+=1
                    self.assertEqual(p.get('source_excerpt'),new.get('source_excerpt'))
                    self.assertEqual(p.get('finish'),new.get('finish'))
                    if p.get('time'):
                        stats['unchanged']+=1
                        self.assertEqual(p['time'],new['time'])
                    elif new.get('time'):
                        stats['recovered']+=1
                        self.assertEqual(1000,p['distance_m'])
                        self.assertEqual('芝',p['surface'])
                    else:
                        stats['legitimate_absence']+=1
                        self.assertIsNone(p.get('finish'))
        self.assertEqual(dict(rows=860,unchanged=789,recovered=31,legitimate_absence=40),stats)

    def test_independent_clock_shadow_does_not_change_marks(self):
        path=ROOT/'e2e_validation/inputs/v313/2026-10-25-lumiere-autumn-dash.json'
        data=json.loads(path.read_text(encoding='utf8'))
        runners=data['step1']['runners']
        fixed=[(h['mark'],h['overall_grade'],h['win_probability']) for h in runners]
        copies=[{**h,'past_performances':[recover(x) for x in h.get('past_performances',[])]} for h in runners]
        result=shadow_signal(copies,'2026-10-25')
        self.assertFalse(result['production_effect'])
        self.assertEqual('SHADOW_ONLY',result['mode'])
        self.assertGreaterEqual(len(result['events']),3)
        self.assertEqual(fixed,[(h['mark'],h['overall_grade'],h['win_probability']) for h in copies])
        lookup={h['horse_name']:h for h in result['horses']}
        self.assertGreater(lookup['カウスリップ']['historical_comparisons'],0)
        self.assertIsNone(lookup['ヴェントゥーラ']['relative_seconds_per_1000m'])

if __name__=='__main__': unittest.main()
