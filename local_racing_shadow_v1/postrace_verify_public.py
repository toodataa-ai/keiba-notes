#!/usr/bin/env python3
"""Verify deployed GitHub Pages is not stale and matches every reviewed file byte-for-byte."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import urljoin
import requests

BASE="https://toodataa-ai.github.io/keiba-notes/"
ROOT=Path("docs")
def digest(blob): return hashlib.sha256(blob).hexdigest()
def main(date, retries, delay):
    local_manifest = (ROOT/"data/local_racing_shadow_public.json").read_bytes()
    loc = json.loads(local_manifest)
    records = [x for x in loc["races"] if x["date"] == date]
    assert records, "No manifest races found"
    expected = {x["race_id"] for x in records}
    session=requests.Session()
    for n in range(1,retries+1):
        try:
            response=session.get(urljoin(BASE,"data/local_racing_shadow_public.json"),
                                 timeout=20,headers={"Cache-Control":"no-cache"})
            response.raise_for_status()
            remote=json.loads(response.content)
            if remote.get("updated_at") != loc.get("updated_at"):
                raise RuntimeError(f"Stale manifest updated_at: {remote.get('updated_at')}")
            if remote != loc:
                raise RuntimeError("Published manifest fields differ from committed manifest")
            if {r["race_id"] for r in remote["races"] if r["date"]==date} != expected:
                raise RuntimeError("Remote manifest race coverage differs")
            for row in records:
                if row["status"] != "reviewed":
                    continue
                for key in ("prediction_path","result_path","review_path"):
                    urlpath = row[key]
                    assert urlpath, f"{row['race_id']} missing {key}"
                    local = (ROOT/urlpath).read_bytes()
                    live=session.get(urljoin(BASE,urlpath), timeout=25,
                                     headers={"Cache-Control":"no-cache"})
                    live.raise_for_status()
                    if digest(live.content)!=digest(local):
                        raise RuntimeError(f"Remote file mismatch: {row['race_id']} {key}")
            for x in loc.get("daily_analysis",[]):
                if x.get("date") == date:
                    rel=x["path"]
                    local=(ROOT/rel).read_bytes()
                    live=session.get(urljoin(BASE,rel),timeout=25,headers={"Cache-Control":"no-cache"})
                    live.raise_for_status()
                    if digest(live.content)!=digest(local):
                        raise RuntimeError(f"Remote daily analysis differs: {rel}")
            print(json.dumps({"status":"VERIFIED","date":date,"manifest_updated_at":loc["updated_at"],
                  "predictions":len(records),"reviewed":sum(x["status"]=="reviewed" for x in records),
                  "base":BASE},ensure_ascii=False))
            return 0
        except (requests.RequestException, ValueError, AssertionError, RuntimeError) as ex:
            print(f"COMMITTED_NOT_PUBLISHED attempt={n}/{retries}: {ex}",flush=True)
            if n < retries:
                time.sleep(delay)
    return 2

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",required=True)
    ap.add_argument("--retries",type=int,default=15)
    ap.add_argument("--delay",type=int,default=12)
    args=ap.parse_args()
    try: sys.exit(main(args.date,args.retries,args.delay))
    except Exception as ex:
        print(f"BLOCKED_PUBLICATION: {type(ex).__name__}: {ex}",file=sys.stderr)
        sys.exit(3)
