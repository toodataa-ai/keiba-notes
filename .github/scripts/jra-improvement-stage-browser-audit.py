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
            strict: document.querySelector('#formalVersion').textContent,
            priority: document.querySelector('#priorityCount').textContent,
            registered: document.querySelector('#trialCount').textContent,
            paired: document.querySelector('#paired').textContent,
            currentStage: document.querySelector('#currentStage').textContent,
            nextAction: document.querySelector('#nextAction').textContent,
            weeks: document.querySelectorAll('#weekly article').length,
            topics: document.querySelectorAll('#hypotheses article').length,
            regimes: document.querySelectorAll('#regimes article').length,
            researchBars: document.querySelectorAll('#regimes progress').length,
            researchDeficits: [...document.querySelectorAll('#regimes .remaining-figure')].map(x=>x.textContent),
            topicDeficits: [...document.querySelectorAll('#hypotheses .remaining-figure')].map(x=>x.textContent),
            milestones: document.querySelectorAll('#milestones article').length,
            adoptionGate: document.querySelector('#milestones').textContent,
            themeQuestions: document.querySelectorAll('#hypotheses .detail-row').length,
            approved: document.querySelector('#approval').textContent,
            links: [...document.querySelectorAll('nav a')].map(x=>x.href),
        })""")
        assert not errors,(width,errors)
        assert info["scroll"]<=width+2 and info["body"]<=width+2,(width,info)
        assert info["strict"]==str(data["latest_formal_prompt_version"]),(width,info)
        assert info["priority"]==str(data["public_roadmap"]["prioritized_topics"])+" / "+str(len(data["formal"]["hypotheses"]))+"テーマ",(width,info)
        assert info["registered"]==str(data["public_roadmap"]["registered_challenger_count"])+"件",(width,info)
        assert info["paired"]=="0 / 20",(width,info)
        assert info["weeks"]==len(data["formal"]["meetings"]),(width,info)
        assert info["topics"]==len(data["formal"]["hypotheses"]),(width,info)
        assert info["themeQuestions"]>=2*info["topics"],(width,info)
        assert info["regimes"]==3,(width,info)
        assert info["researchBars"]==6,(width,info)
        expected_estimates=['あと約'+str(x['next_decision']['additional_races_estimate'])+'レース'
                            for x in data['research']['regimes']]
        assert info["researchDeficits"]==expected_estimates,(width,info)
        assert len(info["topicDeficits"])==len(data['formal']['hypotheses']),(width,info)
        assert any('あと' in text for text in info['topicDeficits']),(width,info)
        assert info["milestones"]==5,(width,info)
        assert "必要" in info["adoptionGate"] or "20レース" in info["adoptionGate"],(width,info)
        assert "A/B/C" in info["approved"],(width,info)
        assert "実験" in info["currentStage"],(width,info)
        assert info["nextAction"],(width,info)
        if width in (320,390,768,1440):
            page.screenshot(path=f"/tmp/jra-improvement-stage-{width}.png",full_page=True)
        print("PASS_IMPROVEMENT_DASHBOARD_REAL_CHROME",width,info["scroll"])
        page.close()
    browser.close()
