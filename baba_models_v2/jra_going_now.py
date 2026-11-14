"""Parse the JRA 'current going' page (https://www.jra.go.jp/keiba/baba/index[2,3].html).
One page per meeting venue (index.html = 1st venue, index2.html = 2nd, index3.html = 3rd; order changes by week).
Returns the officially announced going (turf/dirt), as-of time, weather, moisture and course in use.
Record/analysis only: nothing here feeds a prediction by itself."""
import re
from datetime import date as _date, timedelta as _timedelta

def _text(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))

def parse_going_page(html):
    t = _text(html)
    out = {"venue": None, "kai": None, "nichi": None, "date": None, "as_of": None,
           "weather": None, "turf_going": None, "dirt_going": None,
           "moist_turf_goal": None, "moist_turf_4c": None, "moist_dirt_goal": None, "moist_dirt_4c": None,
           "course": None, "pre_day": False}
    nav = re.search(r'<div class="current"><a href="index\d*\.html">([^<]+?)競馬場', html)
    out["venue"] = nav.group(1) if nav else None
    # Race-day morning before JRA flips the page, the header reads "第3回福島競馬第3日前日 （2026年11月13日（金曜））":
    # the shown date is the day BEFORE the race day. Report the race day itself and flag it (pre_day=True).
    m = re.search(r"第(\d+)回\S+?競馬第(\d+)日(前日)?\s*（(\d{4})年(\d+)月(\d+)日", t)
    out["pre_day"] = False
    if m:
        out["kai"], out["nichi"] = int(m.group(1)), int(m.group(2))
        shown = _date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
        if m.group(3):
            shown += _timedelta(days=1); out["pre_day"] = True
        out["date"] = shown.isoformat()
    m = re.search(r"馬場状態\s*（(\d+月\d+日（.曜）[^）]*現在)）", t)
    if m: out["as_of"] = m.group(1)
    m = re.search(r"天候：\s*(\S+)", t)
    if m: out["weather"] = m.group(1)
    m = re.search(r"芝\s+(良|稍重|重|不良)\s+ダート\s+(良|稍重|重|不良)", t)
    if m: out["turf_going"], out["dirt_going"] = m.group(1), m.group(2)
    m = re.search(r"ゴール前\s+4コーナー\s+芝\s+([\d.]+)\s+([\d.]+)\s+ダート\s+([\d.]+)\s+([\d.]+)", t)
    if m:
        a, b, c, d = (float(x) for x in m.groups())
        out["moist_turf_goal"], out["moist_turf_4c"], out["moist_dirt_goal"], out["moist_dirt_4c"] = a, b, c, d
    m = re.search(r"使用コース\s+(\S+)\s+コース", t)
    if m: out["course"] = m.group(1)
    return out
