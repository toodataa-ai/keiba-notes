#!/usr/bin/env python3
"""Local fixture tests for v3.12 source-form extraction; no external HTTP or fabricated market quotes."""
import importlib.util,json,tempfile
from pathlib import Path
from bs4 import BeautifulSoup
path=Path('.github/scripts/jra-odds-recovery-v312.py')
spec=importlib.util.spec_from_file_location('v312_recovery',path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
base='https://sports.yahoo.co.jp/keiba/race/odds/st/0000000000?ninki=0'
html='''<html><form method="get" action="/keiba/race/odds/st/0000000000">
<input type="hidden" name="ninki" value="0"/>
<select name="horse_axis"><option value="">すべて</option>''' + ''.join(
 '<option value="%s">%s番</option>'%(n,n) for n in range(1,13)
)+'''</select><select name="position">
<option value="1" selected>1着</option><option value="2">2着</option>
</select></form></html>'''
queries=list(mod.form_queries(base,BeautifulSoup(html,'html.parser'),10))
assert len(queries)==1,queries
url,params=queries[0]
assert url.endswith('/st/0000000000') and params['horse_axis']=='10'
assert params['position']=='1' and params['ninki']=='0'
foreign=html.replace('action="/keiba/race/odds/st/0000000000"','action="https://example.org/"')
assert not list(mod.form_queries(base,BeautifulSoup(foreign,'html.parser'),10))
assert mod.canonical('三連複',[16,1,10])==('三連複',(1,10,16))
assert mod.canonical('三連単',[16,1,10])==('三連単',(16,1,10))
print('PASS v3.12 odds recovery: inspected form fields, requested exact first-place axis, foreign source refused, trifecta order preserved')
