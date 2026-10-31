"""LAB only: visible abilities and real-time 1/2/4x fixed goal camera."""
import json
import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

base = os.environ.get('LAB_QA_BASE', 'http://127.0.0.1:8765/lab/')
out = Path(os.environ.get('LAB_QA_OUT', '/tmp/clean-lab'))
out.mkdir(parents=True, exist_ok=True)
reports = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('chromium'), args=['--no-sandbox'])
    for width in (390, 1024):
        for trial in ('synthetic', 'shuka2026'):
            for speed in (1, 2, 4):
                page = browser.new_page(viewport={'width': width, 'height': 900})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(f'{base}race-clean-course-v1.html?trial={trial}&v=ability90', wait_until='load')
                page.wait_for_function('window.CleanLab?.inspect().turfReady')
                ability = page.evaluate('''() => {
                  const cards=[...document.querySelectorAll('.runner-ability-card')];
                  const horses=CleanLab.getState().horses;
                  return {count:cards.length,values:cards.map(card=>{
                    const h=horses.find(h=>h.number===Number(card.dataset.number));
                    return [...card.querySelectorAll('[data-trait]')].map(v=>({
                     value:Number(v.textContent),expected:h.abilityProfile.displaySix[v.dataset.trait]}));
                  }),overflow:document.documentElement.scrollWidth>innerWidth};
                }''')
                assert ability['count'] == (18 if trial == 'synthetic' else 17)
                assert not ability['overflow']
                assert all(len(row) == 6 for row in ability['values'])
                assert all(v['value'] == v['expected'] and 82 <= v['value'] <= 98 for row in ability['values'] for v in row)
                if speed == 1:
                    page.locator('.runner-ability-card').first.screenshot(path=str(out / f'ability90-{width}-{trial}-ability.png'))
                page.evaluate('''speed => {
                  CleanLab.advanceTo(1919);document.getElementById('speed').value=String(speed);
                  window.__goalSamples=[];
                  function sample(ts){
                    const f=CleanLab.frameSample(),g=CleanLab.inspect().goalFrame;
                    if(g){
                      const r=document.getElementById('goalCamera').getBoundingClientRect();
                      const h=f.horses.reduce((a,b)=>a.d>b.d?a:b);
                      const q=RaceCleanGoalView.goalScreenPosition(h.d,h.lane,2000,r.width,r.height,14,'右',1,g.screenSpan);
                      __goalSamples.push({ts,d:h.d,x:q.x,width:r.width,visible:g.visible});
                    }
                    if(!g||g.leaderD<2002)requestAnimationFrame(sample);
                  }
                  requestAnimationFrame(sample);document.getElementById('startBtn').click();
                }''', speed)
                page.wait_for_function('CleanLab.inspect().goalFrame?.leaderD>=2002', timeout=20000)
                samples = page.evaluate('__goalSamples')
                assert samples[0]['x'] > samples[0]['width'] + 10.935, (width,trial,speed,samples[:3])
                assert samples[0]['visible'] == 0
                moving = [s for s in samples if s['d'] <= 2000]
                deltas = [(b['ts']-a['ts'], b['d']-a['d'], a['x']-b['x']) for a, b in zip(moving, moving[1:])]
                assert all(dd >= -1e-8 for _, dd, _ in deltas), 'backwards goal movement'
                assert all(abs(dx - dd * samples[0]['width'] / 100) < 1e-6 for _, dd, dx in deltas)
                still = sum(dd < 1e-8 for _, dd, _ in deltas)
                assert still <= max(3, len(deltas)*.05), ('excess stationary frames', still)
                report = {'width': width, 'trial': trial, 'speed': speed, 'frames': len(samples),
                          'entryX': samples[0]['x'], 'canvasWidth': samples[0]['width'],
                          'stillFrames': still, 'maxFrameGapMs': max(dt for dt, _, _ in deltas)}
                assert report['maxFrameGapMs'] < 250, report
                reports.append(report)
                page.locator('#pauseBtn').click()
                if speed == 1:
                    page.locator('#broadcastStage').screenshot(path=str(out / f'ability90-{width}-{trial}-wire.png'))
                # Changing the CAMERA keeps the same physical seek snapshot.
                physical = page.evaluate('''() => {CleanLab.advanceTo(1980);return CleanLab.getState().horses.map(h=>[h.number,h.d,h.lane,h.finishTime]);}''')
                page.goto(f'{base}race-clean-course-v1.html?trial={trial}&goalCamera=legacy&checkpoint=1980', wait_until='load')
                page.wait_for_function('window.CleanLab?.inspect().turfReady')
                assert page.evaluate('CleanLab.inspect().goalScreenSpan') == 290
                assert page.evaluate('CleanLab.getState().horses.map(h=>[h.number,h.d,h.lane,h.finishTime])') == physical
                assert not errors, errors
                print('PASS_LAB90_REALTIME_BROWSER', json.dumps(report))
                page.close()
    browser.close()
(out / 'ability90-realtime.json').write_text(json.dumps(reports, indent=2))
