"""Real mobile/desktop staging audit; never deploys Pages."""
import json
import shutil
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
expected=json.loads((root/'docs/data/jra_shadow_experiment_status_v1.json').read_text())['runtime']['experiments']
server=subprocess.Popen(['python','-m','http.server','8765','--directory',str(root/'docs')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    time.sleep(1)
    with sync_playwright() as p:
        chrome=next((shutil.which(x) for x in ('chromium','google-chrome','chromium-browser') if shutil.which(x)),None)
        browser=p.chromium.launch(headless=True,executable_path=chrome,args=['--no-sandbox'])
        for width in (390,1440):
            page=browser.new_page(viewport={'width':width,'height':900})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8765/staging/improvement-cycle.html')
            page.wait_for_function("document.querySelector('#main').hidden===false")
            assert page.locator('.road-card').count()==7
            assert page.locator('.shadow-runtime').count()==7
            for x in expected:
                card=page.locator('[data-theme="'+x['theme']+'"]')
                assert card.count()==1
                assert x['candidate_version'] in card.inner_text()
                assert x['approval'] in card.inner_text()
                card.locator('.shadow-runtime details').first.evaluate('(e)=>e.open=true')
                for blocker in x['blockers']:assert blocker in card.inner_text()
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),width
            assert not errors,errors
            page.screenshot(path=f'/tmp/shadow-stage-{width}.png',full_page=True)
            page.goto('http://127.0.0.1:8765/staging/all-experiments.html')
            page.wait_for_url('**/staging/improvement-cycle.html')
            page.close()
        # Failure must be visible; no stale or invented counts when data is absent.
        page=browser.new_page()
        page.route('**/jra_shadow_experiment_status_v1.json',lambda route:route.fulfill(status=503,body='unavailable'))
        page.goto('http://127.0.0.1:8765/staging/improvement-cycle.html')
        page.wait_for_selector('.error-block')
        assert page.locator('#main').get_attribute('hidden') is not None
        browser.close()
    print('PASS_SHADOW_STAGE_390_1440_SEVEN_THEMES_DATA_PARITY_REDIRECT_FAILURE_VISIBILITY')
finally:
    server.terminate();server.wait(timeout=5)
