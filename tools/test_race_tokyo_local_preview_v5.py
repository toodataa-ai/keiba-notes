"""Source-local browser QA. Source-containing screenshots stay LOCAL, never artifacts/."""
import argparse,json,math,hashlib,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--source-dir',required=True);p.add_argument('--base',default='http://127.0.0.1:8775/');p.add_argument('--out',default='/tmp/tokyo-v5-browser');args=p.parse_args()
source=Path(args.source_dir);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
checkpoints=[0,100,130,300,900,1145,1474.1,1600,1920,1950,1980,2000,2032]
reports=[];reference=None
with sync_playwright() as pw:
 browser=pw.chromium.launch(**({'executable_path':shutil.which('chromium')} if shutil.which('chromium') else {}),headless=True)
 for width in [390,1024]:
  for speed in [1,2,4]:
   page=browser.new_page(viewport={'width':width,'height':900});errors=[];posts=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
   page.add_init_script('''window.__raf=null;window.__now=0;window.requestAnimationFrame=cb=>{window.__raf=cb;return 1};window.__tick=ms=>{window.__now+=ms;const cb=window.__raf;window.__raf=null;if(cb)cb(window.__now)};''')
   page.goto(args.base+'lab/race-clean-tokyo-2000-v1.html?approved=true&run=1&motion=bounded-lateral-v4')
   assert page.locator('#startBtn').is_disabled()
   assert page.evaluate('RaceTokyo2000.status.canAnimate===false')
   page.locator('#sourceInspector').evaluate('(e)=>e.open=true')
   page.locator('#sourceAuditFiles').set_input_files([source/'audit-local.json',source/'source-local.svg'])
   page.wait_for_function('RaceTokyoSourceInspector.getLocalInputs()!==null',polling=100)
   assert page.locator('#startBtn').is_disabled(),'Import alone cannot bypass safety audits'
   page.locator('#prepareLocalBtn').click()
   page.wait_for_function('!document.getElementById("prepareLocalBtn").disabled',timeout=180000,polling=100)
   assert not page.locator('#startBtn').is_disabled(),page.locator('#localPreviewStatus').inner_text()
   audit=page.evaluate('RaceTokyoLocalPreviewV5.audit')
   assert audit['mask']['bad']==audit['mask']['folds']==0
   assert audit['mask']['sourceScaleX']==audit['mask']['sourceScaleY']
   signature=hashlib.sha256(json.dumps(audit['result'],sort_keys=True).encode()).hexdigest()
   if reference is None:reference=signature
   assert signature==reference
   for d in checkpoints:
    f=page.evaluate('(d)=>RaceTokyoLocalPreviewV5.seek(d)',d)
    assert math.isclose(f['leaderD'],d,abs_tol=.002),(d,f['leaderD'])
    assert len(f['points'])==len(f['overview']['positions'])==18
    assert f['overview']['sourceScaleX']==f['overview']['sourceScaleY']
    for q,h in zip(f['points'],f['overview']['positions']):
     assert q['number']==h['number'] and q['d']==h['d'] and q['lane']==h['lane']
    if d<1920:
     assert f['broadcast']['sourceScaleX']==f['broadcast']['sourceScaleY']
     for a,b in zip(f['broadcast']['positions'],f['overview']['positions']):
      assert a['worldX']==b['worldX'] and a['worldY']==b['worldY']
    else:
     assert f['broadcast']['screenSpan']==100
     for marker in f['broadcast']['positions']:
      assert marker['y']-12*.81>=f['broadcast']['top']+13
      assert marker['y']+12*.81<=f['broadcast']['bottom']-13
     w=page.locator('#liveBroadcast').bounding_box()['width']
     lead=max(f['broadcast']['positions'],key=lambda h:h['d'])
     assert math.isclose(lead['x']/w,.3+(2000-d)/100,abs_tol=.00002)
    if d in [0,100,300,900,1474.1,1920,1950,2000,2032]:
     page.locator('#localPreview').screenshot(path=str(out/f'local-{width}-{speed}x-{d}.png'))
    # Repainting a paused scene cannot change camera or source positions.
    assert page.evaluate('''()=>{const a=JSON.stringify(RaceTokyoLocalPreviewV5.lastFrame);RaceTokyoLocalPreviewV5.draw();return a===JSON.stringify(RaceTokyoLocalPreviewV5.lastFrame)}''')
   # Fixed physics replay from the start. Only wall-time rate changes.
   page.evaluate('RaceTokyoLocalPreviewV5.seek(0)');page.locator('#playSpeed').select_option(str(speed));page.locator('#startBtn').click()
   samples=page.evaluate('''()=>{let old=null,rows=[],lastGoal=null,goalCut=null;for(let i=0;i<10000&&RaceTokyoLocalPreviewV5.isPlaying;i++){window.__tick(1000/60);const f=RaceTokyoLocalPreviewV5.lastFrame;if(old&&f.time>old.time){const dt=f.time-old.time;for(let j=0;j<18;j++){if(f.points[j].d<old.points[j].d-1e-8)throw Error('backwards');if((f.points[j].d-old.points[j].d)/dt>30)throw Error('presentation acceleration');}if(f.leaderD<1920){const lead=f.points.reduce((a,b)=>b.d>a.d?b:a);const a=f.overview.positions.find(p=>p.number===lead.number);const b=f.broadcast.positions.find(p=>p.number===lead.number);if(!Number.isFinite(a.worldX+b.worldX))throw Error('projection');const prior=old.overview.positions.find(p=>p.number===lead.number);const dx=a.worldX-prior.worldX,dy=a.worldY-prior.worldY;const forwardX=dx*Math.cos(f.camera.angle)-dy*Math.sin(f.camera.angle);if(forwardX>1e-5)throw Error('tracking direction reversed');}else{if(goalCut===null)goalCut=f.leaderD;const lead=f.broadcast.positions.reduce((a,b)=>b.d>a.d?b:a);if(lastGoal!==null&&lead.x>lastGoal+1e-7)throw Error('goal direction reversed');lastGoal=lead.x;}}old=f;if(i%120===0)rows.push({time:f.time,leaderD:f.leaderD});}if(RaceTokyoLocalPreviewV5.isPlaying)throw Error('not complete');return{rows,goalCut,final:RaceTokyoLocalPreviewV5.lastFrame}}''')
   assert samples['goalCut']>=1920
   assert page.locator('#raceRows tr').count()==18
   assert page.locator('#raceBanner').is_visible()
   assert page.locator('#raceClock').inner_text()==page.evaluate('RaceBroadcastHud.clock(RaceTokyoLocalPreviewV5.audit.result[0].finishTime)')
   assert all(h['d']>=2032 for h in samples['final']['points'])
   assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
   assert not errors,errors
   # Replacing either source invalidates the audited session and playback.
   page.locator('#sourceAuditFiles').set_input_files([source/'audit-local.json'])
   page.wait_for_function('document.getElementById("startBtn").disabled',polling=100)
   assert page.evaluate('RaceTokyoLocalPreviewV5.audit===null')
   reports.append({'width':width,'speed':speed,'checkpoints':len(checkpoints),'resultSha256':signature,'audit':audit['summary'],'mask':audit['mask'],'goalCutDistance':samples['goalCut'],'all18Results':True,'noPageErrors':True,'noSourcePost':not posts})
   assert not posts,posts
   page.close();print('PASS',width,speed,'x',flush=True)
 browser.close()
(out/'numeric-browser-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
print('PASS source-local 390/1024 x 1/2/4, actual distances, 13 checkpoints, original vector/body mask, fixed 100m goal camera, all18 clocks/results, repeatability, reset lock')
