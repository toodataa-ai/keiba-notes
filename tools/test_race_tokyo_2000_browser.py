"""Blocked-page QA only. This does not certify racing playback or source geometry."""
from pathlib import Path
import functools
import http.server
import json
import os
import threading
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
    http.server.SimpleHTTPRequestHandler, directory=str(root / 'docs')))
threading.Thread(target=server.serve_forever, daemon=True).start()
out = root / 'artifacts/tokyo-2000'
out.mkdir(parents=True, exist_ok=True)
reports = []
with sync_playwright() as p:
    executable = os.environ.get('TOKYO_QA_CHROMIUM')
    browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
    for width in (390, 1024):
        page = browser.new_page(viewport={'width': width, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{server.server_port}/lab/race-clean-tokyo-2000-v1.html?run=1&approved=true')
        assert page.locator('.horse').count() == 18
        assert page.locator('dd').count() == 108
        assert page.locator('#startBtn').is_disabled()
        assert page.locator('.controls select').is_disabled()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.evaluate('RaceTokyo2000.status.canAnimate === false')
        assert page.evaluate('''() => {try {RaceTokyo2000.create();return false;} catch(e) {
            return e.message === 'TOKYO_ORIGINAL_ROUTE_UNVERIFIED';}}''')
        assert not errors, errors
        page.screenshot(path=str(out / f'blocked-{width}.png'), full_page=True)
        reports.append({'width': width, 'abilityValues': 108, 'cards': 18,
                        'overflow': False, 'playback': 'blocked', 'errors': errors})
        page.close()
    browser.close()
server.shutdown()
(out / 'browser.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2))
print(json.dumps(reports, ensure_ascii=False))
