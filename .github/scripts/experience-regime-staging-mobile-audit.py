#!/usr/bin/env python3
"""Actual Chrome viewport regression gate for E0/E1/E2 staging only."""
from pathlib import Path
import json
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/staging/experience-regime.html"
DATA = json.loads(Path("docs/data/experience_regime_status.json").read_text(encoding="utf-8"))
RUN = DATA["collection_runs"]["2026-10-17"]
assert RUN["selected_today"] == RUN["complete_evidence_races"] == RUN["prerace_proof_valid_races"]
assert sum(x["horse_observations"] for x in RUN["regimes"].values()) > 0
html = Path("docs/staging/experience-regime.html").read_text(encoding="utf-8")
prod = Path("docs/experience-regime.html").read_text(encoding="utf-8")
assert 'id="e012-live-collection"' in html
assert 'id="experience-regime-mobile-overflow-fix"' in html
assert 'data-stage="preview"' in html and 'staging-shell-marker' in html
assert "stage-indicator.css" in html
assert 'id="experience-regime-mobile-overflow-fix"' not in prod
assert 'data-stage="preview"' not in prod

with sync_playwright() as p:
    import shutil
    chrome = next((p for p in (shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")) if p), None)
    if not chrome:
        raise RuntimeError("Chrome/Chromium not installed; a successful test must use a real browser.")
    browser = p.chromium.launch(headless=True, executable_path=chrome, args=["--no-sandbox"])
    for w in (320, 360, 375, 390, 430, 600, 650, 768, 1024):
        page = browser.new_page(viewport={"width": w, "height": 844}, device_scale_factor=1, is_mobile=w <= 650, has_touch=w <= 650)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL, wait_until="load", timeout=45000)
        page.wait_for_function("document.querySelector('#e012-run-date')?.textContent.startsWith('取得対象：')", timeout=20000)
        results = page.evaluate("""() => {
          const q=s=>document.querySelector(s);
          const sels=['html','body','.wrap','.method-hero','.status-strip','.article','.chapter','#e012-live-collection','.metric-table','#e012-commit'];
          const elements={};
          for(const s of sels) {
            const el=q(s);if(!el)continue;
            const r=el.getBoundingClientRect();
            elements[s]={left:r.left,right:r.right,clientWidth:el.clientWidth,scrollWidth:el.scrollWidth};
          }
          const data=[...q('#e012-live-collection .metric-table tbody').children];
          return {
            vw:window.innerWidth,
            rootScroll:document.documentElement.scrollWidth,
            bodyScroll:document.body.scrollWidth,
            elements,
            cards:getComputedStyle(data[0]).display,
            labels:getComputedStyle(data[0].querySelector('td')).whiteSpace,
            values:{
              selected:q('#e012-selected').textContent,
              proof:q('#e012-proof').textContent,
              e0:q('#e012-e0').textContent,
              e1:q('#e012-e1').textContent,
              e2:q('#e012-e2').textContent,
              commit:q('#e012-commit').textContent
            }
          };
        }""")
        assert not errors, f"browser JS error at {w}: {errors}"
        assert results["rootScroll"] <= w+2 and results["bodyScroll"] <= w+2, f"whole-page horizontal overflow at {w}: {results}"
        for sel, rect in results["elements"].items():
            assert rect["right"] <= w+2 and rect["left"] >= -2, f"element offscreen {w} {sel}: {rect}"
        assert results["values"]["proof"] == f'{RUN["prerace_proof_valid_races"]} / {RUN["complete_evidence_races"]} レース'
        for name in ("E0","E1","E2"):
            e=RUN["regimes"][name]
            assert results["values"][name.lower()] == f'{e["horse_observations"]}頭 / {e["races"]}レース'
        assert RUN["proof_commit"] in results["values"]["commit"]
        assert results["cards"] == ("block" if w <= 650 else "table-row"), (w,results["cards"])
        if w in (320,390,768):
            page.screenshot(path=f"/tmp/experience-regime-stage-{w}.png", full_page=True)
        print("PASS_STAGE_MOBILE_VIEWPORT",w,"scroll",results["rootScroll"],"layout",results["cards"])
        page.close()
    browser.close()
print("PASS_STAGE_MOBILE_ALL_VIEWPORTS_REAL_CHROME")
