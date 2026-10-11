#!/usr/bin/env python3
"""Site-only typography: strictly assert no template/data/PDF changes."""
from pathlib import Path
import subprocess
BASE="e8e0bec266cb8ed66c485989dc3852cb5abdebd4"
PAGES=["index","this-week","schedule","results","methodology","roadmap","e2e","experience-regime","baba-models","local-racing-shadow"]
for name in PAGES:
    p="docs/"+name+".html"
    html=Path(p).read_text()
    before=subprocess.check_output(["git","show",BASE+":"+p],text=True)
    assert html==before,p+" HTML must stay byte-identical"
    assert any(x in html for x in ("assets/style.css","assets/methodology.css")),p+" lacks common typography source"
for p in ("docs/assets/style.css","docs/assets/methodology.css"):
    source=subprocess.check_output(["git","show",BASE+":"+p],text=True)
    current=Path(p).read_text()
    assert current.startswith(source),p+" original stylesheet was edited"
    new=current[len(source):]
    assert "JRA site editorial density v1" in new
    assert "@media(max-width:760px)" in new
    for selector in (".week-race",".page-hero h1",".chapter h2",".portal-card",
                     ".method-hero",".brand-title.brand-lockup",".rd-conclusion",".schedule-day"):
        assert selector in new,(p,selector)
    assert "jra-pdf-reader-v1.css" not in new
    assert "display:none" not in new.replace(" ","")
    assert "font-size:14px!important" in new
for forbidden in ("docs/assets/jra-pdf-reader-v1.css","docs/assets/week.js",
  "docs/assets/app.js","docs/data/races.json","docs/data/latest_prompt.json",
  "docs/reports/2026-10-11-ireland-trophy-v3.12-rerun38113832729-attempt1-v312.html",
  "docs/reports/2026-10-11-uzumasa-stakes-v3.12-rerun38113827050-attempt2-v312.html"):
    assert subprocess.run(["git","diff","--quiet",BASE,"HEAD","--",forbidden]).returncode==0,forbidden
print("PASS: "+str(len(PAGES))+" public HTML pages share site CSS, identical HTML/JS/data/PDF, mobile responsive styles")
