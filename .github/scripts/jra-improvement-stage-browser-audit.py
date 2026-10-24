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
            flowSteps: document.querySelectorAll('#roadFlow .flow-step').length,
            flowCurrent: document.querySelectorAll('#roadFlow .is-current').length,
            flowCurrentLabel: document.querySelector('#flowPosition').textContent,
            pairActual: document.querySelector('#pairLarge').textContent,
            pairValue: document.querySelector('#pairProgress').value,
            pairGoal: document.querySelector('#pairProgress').max,
            pairEta: document.querySelector('#pairEta').textContent,
            nextAfterPairs: document.querySelectorAll('.after-steps li').length,
            researchChartBars: document.querySelectorAll('#researchChart progress').length,
            researchChartSummaries: [...document.querySelectorAll('#researchChart .research-chart-foot b')].map(x=>x.textContent),
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
        assert info["flowSteps"]==5,(width,info)
        assert info["flowCurrent"]==1,(width,info)
        assert "ステップ2" in info["flowCurrentLabel"],(width,info)
        strict_proof_guard=page.evaluate("""() => {
          const base={
            latest_formal_prompt_version:'v3.13',
            experiments:[{id:'test',baseline:'v3.13',challenger:'trial',status:'collecting'}],
            formal:{comparison:{baseline:'v3.13',candidate:'trial',
              pair_matches_current_formal:true,paired_strict_cases:6,
              weekly_paired_actuals:[]}}
          };
          const no_ledger=qualifiedPairCount(base);
          base.formal.comparison.weekly_paired_actuals=[
             {week_start:'2026-11-02',valid_pairs:3},
             {week_start:'2026-11-09',valid_pairs:3}];
          const verified=qualifiedPairCount(base);
          base.formal.comparison.weekly_paired_actuals[1].valid_pairs=2;
          return {no_ledger,verified,mismatch:qualifiedPairCount(base)};
        }""")
        assert strict_proof_guard=={"no_ledger":0,"verified":6,"mismatch":0},(width,strict_proof_guard)
        assert info["pairValue"]==0 and info["pairGoal"]==20,(width,info)
        assert "0" in info["pairActual"] and "20" in info["pairActual"],(width,info)
        assert "未算出" in info["pairEta"],(width,info)
        assert info["nextAfterPairs"]==3,(width,info)
        assert info["researchChartBars"]==3,(width,info)
        expected_chart=['あと約'+str(x['next_decision']['additional_races_estimate'])+'レース'
                        for x in data["research"]["regimes"]]
        assert all(any(t in real for real in info['researchChartSummaries']) for t in expected_chart),(width,info)
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
        page.select_option('#scenarioPace','6')
        assert '4開催週' in page.locator('#scenarioWeeks').inner_text(),(width,info)
        page.select_option('#scenarioPace','3')
        assert '7開催週' in page.locator('#scenarioWeeks').inner_text(),(width,info)
        future_test=page.evaluate("""() => {
          const sample={
            latest_formal_prompt_version:'v3.13',
            experiments:[{baseline:'v3.13',challenger:'candidate'}],
            formal:{comparison:{candidate:'candidate',weekly_paired_actuals:[
               {week_start:'2026-11-02',valid_pairs:3},
               {week_start:'2026-11-09',valid_pairs:3}]}}
          };
          return pairedArrivalForecast(sample,6,20);
        }""")
        assert future_test['weeks']==5 and '12月14日' in future_test['when'],(width,future_test)
        if width in (320,390,768,1440):
            page.screenshot(path=f"/tmp/jra-improvement-stage-{width}.png",full_page=True)
        print("PASS_IMPROVEMENT_DASHBOARD_REAL_CHROME",width,info["scroll"])
        page.close()
    browser.close()
