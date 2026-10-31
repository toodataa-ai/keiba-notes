"""Original-source inspection QA. Source files/screenshots stay outside the repository."""
import argparse
import functools
import http.server
import json
from pathlib import Path
import os
import threading
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument('--source-dir',type=Path,required=True)
args = ap.parse_args()
root=Path(__file__).resolve().parents[1]
source=args.source_dir.resolve()
assert root not in source.parents and root!=source
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(root/'docs')))
threading.Thread(target=server.serve_forever,daemon=True).start()
expected=json.loads((source/'audit-local.json').read_text())
out=source/'screens';out.mkdir(exist_ok=True)
reports=[]
with sync_playwright() as p:
    executable=os.environ.get('TOKYO_QA_CHROMIUM')
    browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
    for width in (390,1024):
        page=browser.new_page(viewport={'width':width,'height':1000})
        errors=[];uploads=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:uploads.append(req.url) if req.method!='GET' else None)
        page.goto(f'http://127.0.0.1:{server.server_port}/lab/race-clean-tokyo-2000-v1.html')
        page.locator('#sourceInspector').evaluate('(el)=>el.open=true')
        page.locator('#sourceAuditFiles').set_input_files([source/'audit-local.json',source/'source-local.svg'])
        page.wait_for_function('RaceTokyoSourceInspector.lastView!==null')
        assert page.locator('#sourceAuditViews').is_visible()
        states=[]
        for i,shot in enumerate(expected['numericalCheckpoints']):
            page.locator('#sourceCheckpoint').select_option(str(i))
            view=page.evaluate('RaceTokyoSourceInspector.lastView')
            assert view['checkpoint']==shot['distance']
            assert view['overview']['sourceScaleX']==view['overview']['sourceScaleY']
            assert view['detail']['sourceScaleX']==view['detail']['sourceScaleY']
            for point,horse in zip(view['overview']['positions'],shot['horses']):
                assert all(point[k]==horse[k] for k in ('number','d','displayD','lane'))
                other=next(x for x in view['detail']['positions'] if x['number']==point['number'])
                assert point['x']==other['x'] and point['y']==other['y']
            assert page.locator('#startBtn').is_disabled()
            assert page.evaluate('RaceTokyo2000.status.canAnimate===false')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            states.append({'distance':shot['distance'],'positions':18,'matching':True})
            if shot['distance'] in (0,100,130,300,900,1474.1,1920,2000,2032):
                page.locator('#sourceInspector').screenshot(path=str(out/f'source-{width}-{shot["distance"]}.png'))
        raster=page.evaluate('RaceTokyoSourceInspector.rasterAudit()')
        print(json.dumps({'width':width,'raster':raster},ensure_ascii=False),flush=True)
        assert raster['bad']==0,raster
        assert raster['samples']>1000000
        assert not errors,errors
        assert not uploads,uploads
        # Wrong-source pair must erase the previous valid inspection and remain locked.
        page.locator('#sourceAuditFiles').set_input_files([
            {'name':'audit-local.json','mimeType':'application/json','buffer':(source/'audit-local.json').read_bytes()},
            {'name':'source-local.svg','mimeType':'image/svg+xml','buffer':b'<svg xmlns="http://www.w3.org/2000/svg"/>'}])
        page.wait_for_function('document.getElementById("sourceAuditStatus").textContent.startsWith("読込停止")')
        assert page.locator('#sourceAuditViews').is_hidden()
        assert page.evaluate('RaceTokyoSourceInspector.lastView===null')
        assert 'ハッシュ' in page.locator('#sourceAuditStatus').inner_text()
        assert page.locator('#startBtn').is_disabled()
        reports.append({'width':width,'checkpoints':states,'raster':raster,'errors':errors,'uploads':uploads,'canAnimate':False})
        page.close()
    browser.close()
server.shutdown()
(source/'browser-audit.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
print('PASS LOCAL ORIGINAL SOURCE INSPECTION; race playback remains locked')
