#!/usr/bin/env python3
"""Offline, reproducible tests for date-independent JRA intake; no fabricated formal forecasts."""
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('jra_generic_v314',ROOT/'.github/scripts/jra-gather-live-v314.py')
a=importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class FrozenDatetime(datetime):
 @classmethod
 def now(cls,tz=None):
  return cls(2026,10,11,12,0,0,tzinfo=tz)
class TestGenericJRAIntake(unittest.TestCase):
 def test_all_supported_jra_field_sizes_and_regression(self):
  for count in range(9,19):
   frames=a.frame_allocation(count)
   self.assertEqual(count,len(frames))
   self.assertEqual(sorted(frames),frames)
   self.assertEqual(set(frames),set(range(1,9)))
   self.assertTrue(all(1<=x<=8 for x in frames))
  self.assertEqual([1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8],a.frame_allocation(16))
  self.assertEqual([1,2,3,3,4,4,5,5,6,6,7,7,8,8],a.frame_allocation(14))
  self.assertEqual([1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,8],a.frame_allocation(17))
  self.assertRaises(RuntimeError,a.frame_allocation,8)
  self.assertRaises(RuntimeError,a.frame_allocation,19)

 def sample_request(self,preview):
  return {'date':'2026-10-12','preview_path':str(preview),
   'race':{'slug':'2026-10-12-october-stakes','venue':'東京',
           'name':'オクトーバーステークス','race_no':11,
           'start_at':'2026-10-12T15:30:00+09:00','race_code':'2605040511',
           'official':'https://www.jra.go.jp/JRADB/accessD.html?CNAME=placeholder',
           'surface':'芝','distance_m':2000}}
 def test_prestart_preview_and_published_safety_gates(self):
  testpath=ROOT/'docs/research/_v314-offline-test-preview.json'
  data={'date':'2026-10-12','races':[{'id':'2026-10-12-october-stakes','horses':[
    {'number':i,'name':'SYNTHETIC_'+str(i),'overall_grade':'B','judgement':'fixture, not a prediction',
     'mark':('◎' if i==1 else '○' if i==2 else '▲' if i==3 else '△')}
    for i in range(1,10)]}]}
  testpath.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
  try:
   req=self.sample_request(testpath.relative_to(ROOT))
   with patch.object(a,'datetime',FrozenDatetime):
    race,preview=a.validate_request(req)
    self.assertEqual(race['race_no'],11)
    self.assertEqual(len(preview['races'][0]['horses']),9)
    bad=json.loads(json.dumps(req));bad['race']['start_at']='2026-10-12T15:45:00+09:00'
    with self.assertRaisesRegex(RuntimeError,'schedule'):a.validate_request(bad)
    bad=json.loads(json.dumps(req));bad['race']['slug']='2026-10-11-october-stakes'
    with self.assertRaisesRegex(RuntimeError,'date mismatch'):a.validate_request(bad)
    bad=json.loads(json.dumps(req));bad['official_snapshot_path']='e2e_validation/source-evidence/missing.html'
    with self.assertRaises(RuntimeError):a.validate_request(bad)
    bad=json.loads(json.dumps(req));bad['race']['venue']='地方競馬場'
    with self.assertRaisesRegex(RuntimeError,'unrecognized'):a.validate_request(bad)
    bad=json.loads(json.dumps(req));bad['preview_path']='docs/research/../../etc/passwd'
    with self.assertRaises(RuntimeError):a.validate_request(bad)
   with patch.object(a,'datetime',datetime):
    with self.assertRaisesRegex(RuntimeError,'begun'):a.validate_request(req) if datetime.now(a.JST)>=datetime.fromisoformat(req['race']['start_at']) else None
  finally:
   testpath.unlink(missing_ok=True)

 def test_no_date_pinning_and_exact_evidence_reconciliation_in_workflow(self):
  py=(ROOT/'.github/scripts/jra-gather-live-v314.py').read_text()
  flow=(ROOT/'.github/workflows/jra-generic-one-shot-v314.yml').read_text()
  self.assertIn("DATE=req['date']",py)
  self.assertIn("preview_path",py)
  self.assertIn('sha256(raw)',py)
  self.assertNotIn("DATE='2026-10-11'",py)
  self.assertIn("paths:",flow)
  self.assertIn("e2e_validation/requests/v314/*.json",flow)
  self.assertIn("jra-odds-full-refresh-v313-exec.py --refresh-all",flow)
  self.assertIn("validate-jra-pdf-content-v313.py",flow)
  self.assertIn('cmp -s "$FILE"',flow)
  self.assertIn('git add -- "$INPUT_PATH" "$SNAPSHOT"',flow)
  self.assertNotIn("cancel-in-progress: true",flow)

if __name__=='__main__':
 unittest.main()
