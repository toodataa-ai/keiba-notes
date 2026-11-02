"""Archive JMA forecasts (raw JSON) and the JRA going-information page (raw HTML) with a timestamp.
Past forecasts are not published, so the only way to measure real forecast skill is to save them as they are issued.
Record-only: nothing here feeds a prediction. Output: forecast_archive/<YYYY>/<MM>/<YYYYMMDD_HHMM>.json.gz"""
import gzip, json, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

UA = "keiba-notes track-condition research/1.0"
JST = timezone(timedelta(hours=9))
AREA_URL = "https://www.jma.go.jp/bosai/common/const/area.json"
FC_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/{code}.json"
# JMA forecast office name -> racecourses covered
OFFICES = {"石狩地方": ["sapporo"], "渡島地方": ["hakodate"], "福島県": ["fukushima"], "新潟県": ["niigata"],
           "愛知県": ["chukyo"], "福岡県": ["kokura"], "東京都": ["tokyo"], "千葉県": ["nakayama"],
           "京都府": ["kyoto"], "兵庫県": ["hanshin"]}
JRA_PAGES = {"jra_baba_top": "https://www.jra.go.jp/keiba/baba/"}


def get(s, url, as_json):
    last = None
    for i in range(3):
        try:
            r = s.get(url, timeout=30, headers={"User-Agent": UA}); r.raise_for_status()
            return r.json() if as_json else r.text
        except Exception as e:
            last = e; time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def main(out_dir="baba_models_v2/forecast_archive"):
    now = datetime.now(JST)
    rec = {"fetched_at_jst": now.isoformat(timespec="seconds"), "forecasts": {}, "jra": {}, "errors": []}
    s = requests.Session()
    try:
        offices = get(s, AREA_URL, True)["offices"]
        code_by_name = {v["name"]: k for k, v in offices.items()}
    except Exception as e:
        rec["errors"].append(str(e)); code_by_name = {}
    for name, tracks in OFFICES.items():
        code = code_by_name.get(name)
        if not code:
            rec["errors"].append(f"office not found: {name}"); continue
        try:
            rec["forecasts"][code] = {"office": name, "tracks": tracks, "data": get(s, FC_URL.format(code=code), True)}
        except Exception as e:
            rec["errors"].append(str(e))
    for key, url in JRA_PAGES.items():
        try:
            rec["jra"][key] = {"url": url, "html": get(s, url, False)}
        except Exception as e:
            rec["errors"].append(str(e))
    p = Path(out_dir) / f"{now:%Y}" / f"{now:%m}"
    p.mkdir(parents=True, exist_ok=True)
    f = p / f"{now:%Y%m%d_%H%M}.json.gz"
    with gzip.open(f, "wt", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"saved {f} forecasts={len(rec['forecasts'])}/10 jra={len(rec['jra'])} errors={len(rec['errors'])} size={f.stat().st_size}")
    for e in rec["errors"]: print("ERROR", e)
    return 0 if rec["forecasts"] else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
