#!/usr/bin/env python3
"""Chrome audit: per-topic visual roadmap, true prior evidence and non-regression."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright

url="http://127.0.0.1:8765/staging/improvement-cycle.html"
d=json.loads(Path("docs/data/jra_improvement_cycle_v1.json").read_text(encoding="utf-8"))
col=json.loads(Path("docs/data/experience_regime_status.json").read_text(encoding="utf-8"))
verified_runs=[x for x in col.get("collection_runs",{}).values()
    if x.get("proof_commit") and x.get("complete_evidence_races",0)>0
    and x["complete_evidence_races"]==x.get("prerace_proof_valid_races")
    and len(x.get("complete_evidence_race_ids",[]))==x["complete_evidence_races"]]
expected_race_count=len({rid for run in verified_runs for rid in run["complete_evidence_race_ids"]})
observed_by_group={code:{
  "races":sum(int((x.get("regimes",{}).get(code) or {}).get("races") or 0) for x in verified_runs),
  "horses":sum(int((x.get("regimes",{}).get(code) or {}).get("horse_observations") or 0) for x in verified_runs)}
 for code in ("E0","E1","E2")}
assert not d["gates"]["automated_prompt_change"]
html=Path("docs/staging/improvement-cycle.html").read_text(encoding="utf-8")
assert 'data-stage="preview"' in html and "noindex,nofollow" in html and "staging-shell-marker" in html
with sync_playwright() as pw:
    chrome=next((shutil.which(x) for x in ("google-chrome","chromium","chromium-browser") if shutil.which(x)),None)
    assert chrome,"Chrome required"
    browser=pw.chromium.launch(headless=True,executable_path=chrome,args=["--no-sandbox"])
    for width in (320,375,390,430,768,1024,1440):
        page=browser.new_page(viewport={"width":width,"height":850},is_mobile=width<=430,has_touch=width<=430)
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto(url,wait_until="load",timeout=25000)
        page.wait_for_function("document.querySelector('#main')?.hidden===false",timeout=15000)
        info=page.evaluate("""() => ({
          viewport:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,
          reviews:document.querySelector('#formalReviews').textContent,
          researchRaces:document.querySelector('#researchRaces').textContent,
          researchHorses:document.querySelector('#researchHorses').textContent,
          registration:document.querySelector('#registeredTrials').textContent,
          topics:[...document.querySelectorAll('#topicRoadmaps .road-card')].map(c=>({
            title:c.querySelector('h3').textContent,
            first:c.querySelector('.evidence-actual .value').textContent,
            second:c.querySelector('.evidence-confirmed .value').textContent,
            current:[...c.querySelectorAll('.track-step.is-current')].map(x=>x.textContent),
            states:c.querySelectorAll('.track-step').length,
            bars:[...c.querySelectorAll('progress')].map(p=>[p.value,p.max]),
            comparison:c.querySelector('.comparison-mini').textContent,
            hint:c.querySelector('.decision-hint').textContent,
            eta:c.querySelector('.timing-row').textContent
          })),
          studies:[...document.querySelectorAll('#studyRoadmaps .road-card')].map(c=>({
            title:c.querySelector('h3').textContent,
            first:c.querySelector('.evidence-actual .value').textContent,
            second:c.querySelector('.evidence-confirmed .value').textContent,
            states:c.querySelectorAll('.track-step').length,
            current:c.querySelectorAll('.track-step.is-current').length,
            bars:[...c.querySelectorAll('progress')].map(p=>[p.value,p.max]),
            eta:c.querySelector('.timing-row').textContent
          })),
          weeks:document.querySelectorAll('#weekly .week').length
        })""")
        assert not errors,(width,errors)
        assert info["scroll"]<=width+2 and info["body"]<=width+2,(width,info)
        assert info["reviews"]==str(d["formal"]["strict_verified_reviews"])+"レース",(width,info)
        assert info["researchRaces"]==str(expected_race_count)+"レース",(width,info)
        assert info["registration"]==str(len(d["experiments"]))+"件",(width,info)
        assert info["researchHorses"]==str(sum(x["horses"] for x in observed_by_group.values()))+"頭分",(width,info)
        assert info["topics"] and len(info["topics"])==len(d["formal"]["hypotheses"]),(width,info)
        assert len(info["studies"])==len(d["research"]["regimes"])==3,(width,info)
        assert info["weeks"]==len(d["formal"]["meetings"]),(width,info)
        for x,src in zip(info["topics"],d["formal"]["hypotheses"]):
            assert x["title"]==src["title"],(width,x)
            assert x["first"]==str(src["race_observation_count"])+"レース",(width,x)
            assert x["second"].startswith(str(src["next_decision"]["screening"]["qualifying_race_reviews"])+"件"),(width,x)
            assert x["states"]==5 and len(x["current"])==1,(width,x)
            assert len(x["bars"])==3 and x["bars"][-1][0]==0,(width,x)
            assert "20" in x["comparison"] and "20" in x["eta"] or "実績からは未算出" in x["eta"],(width,x)
        for x,src in zip(info["studies"],d["research"]["regimes"]):
            n=src["next_decision"]
            code=src["id"].replace("experience_","").upper()
            observed=observed_by_group[code]
            assert x["first"].startswith(str(observed["races"])+"レース"),(width,x)
            assert str(observed["horses"])+"頭分" in x["first"],(width,x)
            assert x["second"].startswith(str(src["cumulative_reviewed_horse_observations"])+"頭分"),(width,x)
            assert x["states"]==5 and x["current"]==1,(width,x)
            assert len(x["bars"])==3 and all(b[0]==0 for b in x["bars"]),(width,x)
            remaining=max(n["win_probability_horse_records_remaining"],n["top3_probability_horse_records_remaining"])
            approx=max(n["minimum_distinct_new_qualifying_races"],
                       -(-remaining*observed["races"]//observed["horses"]))
            assert "あと約"+str(approx)+"レース" in x["eta"],(width,x)
        page.select_option('#scenarioPace','6')
        updated=page.locator('#topicRoadmaps .timing-row').first.inner_text()
        assert "4開催週" in updated,(width,updated)
        page.select_option('#scenarioPace','3')
        reset=page.locator('#topicRoadmaps .timing-row').first.inner_text()
        assert "7開催週" in reset,(width,reset)
        # Fake numerical pair counts without registration and an original
        # proven pair ledger must never advance any topic.
        fake=page.evaluate("""() => {
          const d={latest_formal_prompt_version:'v3.13',
            formal:{comparison:{candidate:'trial',baseline:'v3.13',pair_matches_current_formal:true,
              paired_strict_cases:20,minimum_paired_cases:20,weekly_paired_actuals:[]}},
            experiments:[]};
          const withoutPlan=pairForTopic(d,['pace_positioning']);
          d.experiments=[{id:'exp',baseline:'v3.13',challenger:'trial',hypothesis_ids:['pace_positioning']}];
          const withoutProof=pairForTopic(d,['pace_positioning']);
          d.formal.comparison.weekly_paired_actuals=[
            {week_start:'2026-11-02',valid_pairs:10},{week_start:'2026-11-09',valid_pairs:10}];
          const withProof=pairForTopic(d,['pace_positioning']);
          const unrelated=pairForTopic(d,['track_condition']);
          return {withoutPlan,withoutProof,withProof,unrelated};
        }""")
        assert fake["withoutPlan"]["count"]==0
        assert fake["withoutProof"]["count"]==0 and fake["withoutProof"]["registered"]
        assert fake["withProof"]["count"]==20
        assert not fake["unrelated"]["registered"] and fake["unrelated"]["count"]==0
        if width in (320,390,768,1440):
            page.screenshot(path=f"/tmp/jra-improvement-stage-{width}.png",full_page=True)
        print("PASS_THEME_ROADMAP_REAL_CHROME",width,info["scroll"])
        page.close()
    browser.close()
