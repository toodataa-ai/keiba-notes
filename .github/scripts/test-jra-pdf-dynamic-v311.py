#!/usr/bin/env python3
"""No page ceilings: rendered >30-page synthetic stress plus omitted-row negative case."""
from pathlib import Path
import json,os,subprocess,sys,tempfile
import importlib.util
root=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='jra-v311-unlimited-') as td:
 p=Path(td);fixture=json.loads(Path('/tmp/jra-v311-pdf-fixture.json').read_text(encoding='utf-8'))
 base=fixture['purchase_portfolio_selection']['optimizer_audit']
 # These are synthetic, NON-MARKET unpriced options for PDF pagination only.
 for i in range(170):
  fixture['ticket_candidate_comparisons'].append({
   'type':'三連複','selection':[1,2,3+i],'eligibility':'unpriced',
   'source_url':None,'market_odds':None})
 if not isinstance(base.get('considered_excluded'),list):raise AssertionError('missing excluded array')
 data=p/'fixture.json';data.write_text(json.dumps(fixture,ensure_ascii=False),encoding='utf-8')
 html=p/'output.html';pdf=p/'output.pdf'
 env={**os.environ,'JRA_SELECTED_ROWS_PER_PAGE':'4','JRA_REJECTED_ROWS_PER_PAGE':'3'}
 subprocess.run([sys.executable,'.github/scripts/jra-render-live-v311.py',str(data),str(html)],check=True,cwd=root,env=env)
 subprocess.run([sys.executable,'-m','weasyprint',str(html),str(pdf)],check=True,cwd=root)
 subprocess.run([sys.executable,'.github/scripts/validate-jra-pdf-content-v311.py',
  '--html',str(html),'--pdf',str(pdf),'--prediction',str(data)],check=True,cwd=root)
 import fitz
 with fitz.open(pdf) as doc:
  assert len(doc)>60, 'stress PDF should exceed sixty pages; no total page ceiling'
 source=html.read_text(encoding='utf-8')
 assert 'U0170' in source,'last candidate not printed'
 tampered=p/'tampered.html'
 tampered.write_text(source.replace('<td>U0170</td>','<td>欠落</td>'),encoding='utf-8')
 out=subprocess.run([sys.executable,'.github/scripts/validate-jra-pdf-content-v311.py',
  '--html',str(tampered),'--pdf',str(pdf),'--prediction',str(data)],cwd=root,
  text=True,capture_output=True)
 assert out.returncode!=0 and ('U0170' in out.stdout or 'U0170' in out.stderr),'lost final unpriced candidate must fail PDF publication'
 print('PASS v3.11 unlimited-page >60 rendered PDF and omissions fail closed')
