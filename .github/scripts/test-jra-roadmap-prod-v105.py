#!/usr/bin/env python3
"""JRA roadmap v1.05 release acceptance (local Chrome, immutable predictions)."""
import json
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

DOCS=Path("docs")
url="http://127.0.0.1:8765"
formal=json.loads((DOCS/"data/jra_improvement_cycle_v1.json").read_text(encoding="utf8"))
regime=json.loads((DOCS/"data/experience_regime_status.json").read_text(encoding="utf8"))
verified=[r for r in regime.get("collection_runs",{}).values()
          if r.get("proof_commit") and r.get("complete_evidence_races",0)>0
          and r["complete_evidence_races"]==r.get("prerace_proof_valid_races")
          and len(r.get("complete_evidence_race_ids",[]))==r["complete_evidence_races"]]
race_ids={rid for r in verified for rid in r["complete_evidence_race_ids"]}
horse_total=sum(sum((r.get("regimes",{}).get(c) or {}).get("horse_observations",0)
                   for c in ("E0","E1","E2")) for r in verified)
html=(DOCS/"improvement-cycle.html").read_text(encoding="utf8")
assert 'data-stage="preview"' not in html
assert 'staging-shell-marker' not in html
assert 'noindex,nofollow' not in html
assert 'href="staging/' not in html
assert '<base ' not in html
assert 'assets/improvement-cycle.css?v=20261025-1' in html
assert 'data/jra_improvement_cycle_v1.json' in html
assert 'data/experience_regime_status.json' in html

with sync_playwright() as pw:
    chrome=next((shutil.which(x) for x in ("google-chrome","chromium","chromium-browser") if shutil.which(x)),None)
    assert chrome,"Local Chrome/Chromium required"
    browser=pw.chromium.launch(headless=True,executable_path=chrome,args=["--no-sandbox"])
    for w in (320,375,390,430,768,1024,1440):
        page=browser.new_page(viewport={"width":w,"height":860},is_mobile=w<=430,has_touch=w<=430)
        errors=[]
        page.on("pageerror", lambda err:errors.append(str(err)))
        page.goto(url+"/improvement-cycle.html",wait_until="load",timeout=30000)
        page.wait_for_function("document.querySelector('#main')?.hidden===false",timeout=15000)
        results=page.evaluate("""() => {
            const $=s=>document.querySelector(s);
            const sty=s=>getComputedStyle($(s));
            const selectors=['body','.hero h1','.section h2','.metric strong','.topic-road h3',
                '.topic-road .track-step b','.study-road h3','.study-road .track-step b',
                '.decision-hint','.scenario-bar select','.scenario-bar option',
                '.week strong','.timing-eta','.sources summary'];
            return {
                font:Object.fromEntries(selectors.map(s=>[s,sty(s).fontFamily])),
                width:document.documentElement.scrollWidth,
                bg:sty('body').backgroundColor,section:sty('.section').backgroundColor,
                card:sty('.road-card').backgroundColor,
                cardBorder:parseFloat(sty('.road-card').borderLeftWidth),
                themeAccent:sty('.topic-road').borderTopColor,
                studyAccent:sty('.study-road').borderTopColor,
                themes:document.querySelectorAll('#topicRoadmaps .road-card').length,
                studies:document.querySelectorAll('#studyRoadmaps .road-card').length,
                stages:[...document.querySelectorAll('.road-card')].map(c=>[
                    c.querySelectorAll('.track-step').length,
                    c.querySelectorAll('.track-step.is-current').length]),
                formal:$('#formalReviews').textContent,
                research:$('#researchRaces').textContent,
                horses:$('#researchHorses').textContent,
                trials:$('#registeredTrials').textContent
            };
        }""")
        assert not errors,(w,errors)
        assert results["width"]<=w+2,(w,"overflow",results)
        assert all(v.replace('"','').startswith('Meiryo UI') for v in results["font"].values()),(w,results["font"])
        assert results["font"]["body"]==results["font"][".scenario-bar select"],(w,results["font"])
        assert len({results["bg"],results["section"],results["card"]})==3,(w,results)
        assert results["cardBorder"]>=1.5 and results["themeAccent"]!=results["studyAccent"],(w,results)
        assert results["themes"]==len(formal["formal"]["hypotheses"]),(w,results)
        assert results["studies"]==3,(w,results)
        assert all(stages==5 and current==1 for stages,current in results["stages"]),(w,results)
        assert results["formal"]==str(formal["formal"]["strict_verified_reviews"])+"レース",(w,results)
        assert results["research"]==str(len(race_ids))+"レース",(w,results)
        assert results["horses"]==str(horse_total)+"頭分",(w,results)
        assert results["trials"]==str(len(formal["experiments"]))+"件",(w,results)
        if w==390:
            page.select_option('#scenarioPace','6')
            assert '4開催週' in page.locator('#topicRoadmaps .timing-row').first.inner_text()
        if w in (390,1440):page.screenshot(path=f"/tmp/jra-roadmap-prod-preview-{w}.png",full_page=True)
        print("PASS_PRODUCTION_ROADMAP_BROWSER",w,results["themes"],results["studies"],results["research"])
        page.close()
    for w in (390,1440):
        p=browser.new_page(viewport={"width":w,"height":850},is_mobile=w==390,has_touch=w==390)
        p.goto(url+"/index.html")
        card=p.locator("a.milestone-card")
        assert card.count()==1
        assert card.get_attribute("href")=="improvement-cycle.html"
        card.click()
        p.wait_for_url("**/improvement-cycle.html")
        p.wait_for_function("document.querySelector('#main')?.hidden===false")
        assert p.locator('#topicRoadmaps .road-card').count()==len(formal['formal']['hypotheses'])
        p.goto(url+"/roadmap.html")
        anchor=p.locator("#live-milestones a[href='improvement-cycle.html']")
        assert anchor.count()==1
        anchor.click()
        p.wait_for_url("**/improvement-cycle.html")
        assert p.locator('#roadmapsTitle').is_visible()
        print("PASS_PRODUCTION_HOMEPAGE_AND_OLD_BOOKMARK",w)
        p.close()
    browser.close()
