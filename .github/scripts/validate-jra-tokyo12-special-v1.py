#!/usr/bin/env python3
import json,sys,re,subprocess
from pathlib import Path
root=Path("docs")
data=json.loads((root/"data"/"special-2026-10-11-tokyo12.json").read_text())
page=(root/"special-2026-10-11-tokyo12.html").read_text()
assert data["race_id"]=="2026-10-11-tokyo-12" and "kyoto" not in data["race_id"]
assert len(data["ranking"])==5 and len({x["number"] for x in data["ranking"]})==5
assert all(str(x["number"]) in page and x["horse"] in page for x in data["ranking"])
assert data["final_bets"]==[] and data["total_stake_yen"]==0
assert "正式監査未了" in page and "見送り" in page and "未完了" in page
assert page.count('class="special-card"')==1
assert "京都12R" not in page and "2026-10-11-kyoto-12" not in page
for name in ["index.html","this-week.html"]:
    assert "special-2026-10-11-tokyo12.html" in (root/name).read_text()
assert data["full_odds_8_types_verified"] is False and data["full_outcome_distribution_computed"] is False
assert data["historical_jra_predictions_mutated"] is False
changed=subprocess.check_output(["git","diff","--name-only","origin/main...HEAD"],text=True).splitlines()
allowed={"docs/index.html","docs/this-week.html","docs/special-2026-10-11-tokyo12.html","docs/data/special-2026-10-11-tokyo12.json",".github/scripts/validate-jra-tokyo12-special-v1.py",".github/workflows/validate-jra-tokyo12-special-v1.yml"}
assert set(changed)<=allowed,(set(changed)-allowed)
print("PASS: Tokyo12-only special reference page, honest prestart coverage, original JRA files untouched, links and marks verified")
