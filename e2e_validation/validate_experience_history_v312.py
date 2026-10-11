#!/usr/bin/env python3
"""v3.12 CI interpretation for a single SHA-frozen preexisting experience gap.
Never repairs or conceals any historical case, and rejects all new regressions."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCHIVED='e2e_validation/cases/2026-10-10-mimuro-stakes/case.json'
HISTORICAL_SHA='f833d33b480e1f845d80a0160e60fb8ad194788a'
EXPECTED={'case':ARCHIVED,'race_id':'2026-10-10-mimuro-stakes','version':'v3.2',
          'grade':'prospective_strict',
          'error':'experience_required_after_start_date: grade=prospective_strict date=2026-10-10 required_from=2026-10-10'}
def main():
 p=subprocess.run([sys.executable,'experience_regime_v1/analyze.py','--cases',
       'e2e_validation/cases','--output','docs/data/experience_regime_status.json','--allow-errors'],
       cwd=ROOT,stdout=subprocess.DEVNULL,text=True)
 if p.returncode:raise RuntimeError('experience-regime computation failed')
 report=json.loads((ROOT/'docs/data/experience_regime_status.json').read_text(encoding='utf-8'))
 errors=report.get('errors',[])
 if not errors:
  print('PASS E0/E1/E2 experience regime: no errors');return
 sha=subprocess.check_output(['git','hash-object',ARCHIVED],cwd=ROOT,text=True).strip()
 if sha!=HISTORICAL_SHA or errors!=[EXPECTED]:
  raise RuntimeError('BLOCKER: unknown experience failure or changed archived case: '+json.dumps(errors,ensure_ascii=False))
 print('ARCHIVED EXPERIENCE GAP (non-cleared): historical 2026-10-10 v3.2 case '
   'still lacks required experience data. Original case Git SHA verified; no other error. '
   'This is a disclosed legacy-baseline warning, not a validation of the missing evidence.')
if __name__=='__main__':
 main()
