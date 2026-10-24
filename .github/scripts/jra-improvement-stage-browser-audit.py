#!/usr/bin/env python3
"""Real Chrome smoke test for isolated JRA improvement-cycle staging dashboard."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright

url = "http://127.0.0.1:8765/staging/improvement-cycle.html"
data = json.loads(Path("docs/data/jra_improvement_cycle_v1.json").read_text(encoding="utf-8"))
assert data["gates"]["automated_prompt_change"] is False
html = Path("docs/staging/improvement-cycle.html").read_text(encoding="utf-8")
assert 'data-stage="preview"' in html and "staging-shell-marker" in html
assert "noindex,nofollow" in html and 'href="../"' in html
assert "jra_improvement_cycle_v1.json" in html
with sync_playwright() as playwright:
    chrome = next((shutil.which(name) for name in ("google-chrome","chromium","chromium-browser") if shutil.which(name)), None)
    assert chrome, "Real Chrome is required"
    browser = playwright.chromium.launch(headless=True, executable_path=chrome, args=["--no-sandbox"])
    for width in (320,375,390,430,768,1024,1440):
        page = browser.new_page(viewport={"width":width,"height":850}, is_mobile=width<=430,has_touch=width<=430)
        errors=[]
        page.on("pageerror",lambda err:errors.append(str(err)))
        page.goto(url,wait_until="load",timeout=25000)
        page.wait_for_function("document.querySelector('#main')?.hidden === false",timeout=15000)
        info=page.evaluate("""() => ({
            vw: innerWidth, scroll: document.documentElement.scrollWidth,
            body: document.body.scrollWidth,
            strict: document.querySelector('#strict').textContent,
            paired: document.querySelector('#paired').textContent,
            weeks: document.querySelectorAll('#weekly article').length,
            topics: document.querySelectorAll('#hypotheses article').length,
            regimes: document.querySelectorAll('#regimes article').length,
            approved: document.querySelector('#approval').textContent,
            links: [...document.querySelectorAll('nav a')].map(x=>x.href),
        })""")
        assert not errors,(width,errors)
        assert info["scroll"]<=width+2 and info["body"]<=width+2,(width,info)
        assert info["strict"]==str(data["formal"]["strict_verified_reviews"]),(width,info)
        assert info["weeks"]==len(data["formal"]["meetings"]),(width,info)
        assert info["topics"]==len(data["formal"]["hypotheses"]),(width,info)
        assert info["regimes"]==3,(width,info)
        assert info["approved"]=="自動採用なし",(width,info)
        if width in (320,390,768,1440):
            page.screenshot(path=f"/tmp/jra-improvement-stage-{width}.png",full_page=True)
        print("PASS_IMPROVEMENT_DASHBOARD_REAL_CHROME",width,info["scroll"])
        page.close()
    browser.close()
