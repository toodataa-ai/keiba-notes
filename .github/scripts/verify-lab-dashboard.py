#!/usr/bin/env python3
"""Real Chrome LAB UI smoke test, mobile to desktop, no application writes."""
import json
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

data=json.loads(Path("docs/lab/change-board.json").read_text(encoding="utf-8"))
expected=len(data["features"])
assert expected>=7
chrome=next((x for x in (shutil.which("google-chrome"),shutil.which("chromium"),shutil.which("chromium-browser")) if x),None)
assert chrome,"Browser smoke test requires a real Chrome/Chromium executable"
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=chrome,headless=True,args=["--no-sandbox"])
    for width in (320,360,375,390,430,650,768,1024):
        page=browser.new_page(viewport={"width":width,"height":844})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto("http://127.0.0.1:8765/lab/index.html",wait_until="load",timeout=25000)
        page.wait_for_function("(n)=>document.querySelectorAll('#featureList article.item').length===n",arg=expected,timeout=10000)
        report=page.evaluate("""() => {
          const els=[...document.querySelectorAll('#featureList article.item')];
          const n=id=>Number(document.getElementById(id).textContent);
          const scroll=document.documentElement.scrollWidth;
          const body=document.body.scrollWidth;
          return {width:innerWidth,scroll,body,links:document.querySelectorAll('.links a[href^="../staging/"]').length,
             summary:n('nLab')+n('nReview')+n('nReleased')+n('nReference'),
             allCardsInside:els.every(el=>{const r=el.getBoundingClientRect();return r.left>=-2&&r.right<=innerWidth+2;})};
        }""")
        assert not errors,(width,errors)
        assert report["scroll"]<=width+2 and report["body"]<=width+2,(width,report)
        assert report["allCardsInside"] and report["summary"]==expected and report["links"]==expected,(width,report)
        print("PASS_LAB_REAL_CHROME_RESPONSIVE",width,"features",expected)
        page.close()
    browser.close()
print("PASS_LAB_DASHBOARD_BROWSER_ALL_VIEWPORTS")
