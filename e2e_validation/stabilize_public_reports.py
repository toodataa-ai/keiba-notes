#!/usr/bin/env python3
"""Preserve generated_at when generated public audit meaning has not changed.

Eliminates timestamp-only commits, unnecessary Pages deployments, and live
byte-parity races between concurrent workflows. Does not suppress real errors.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATHS=("docs/data/e2e_status.json","docs/data/experience_regime_status.json",
       "docs/data/jra_review_completion.json","docs/data/e2e_public.json")

def without_generation(value):
    if isinstance(value,dict):
        return {k:without_generation(v) for k,v in value.items() if k!="generated_at"}
    if isinstance(value,list):
        return [without_generation(v) for v in value]
    return value

def stabilize(current,previous):
    if isinstance(current,dict) and isinstance(previous,dict):
        result={k:stabilize(v,previous.get(k)) for k,v in current.items()}
        if ("generated_at" in current and "generated_at" in previous and
                without_generation(current)==without_generation(previous)):
            result["generated_at"]=previous["generated_at"]
        return result
    if isinstance(current,list) and isinstance(previous,list) and len(current)==len(previous):
        return [stabilize(c,p) for c,p in zip(current,previous)]
    return current

def main():
    stable=0
    for path in PATHS:
        dest=ROOT/path
        if not dest.exists():
            continue
        old=subprocess.run(["git","show","HEAD:"+path],cwd=ROOT,
                           capture_output=True,text=True)
        if old.returncode:
            continue
        current=json.loads(dest.read_text(encoding="utf-8"))
        previous=json.loads(old.stdout)
        fixed=stabilize(current,previous)
        if fixed!=current:
            dest.write_text(json.dumps(fixed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            stable+=1
    print("PUBLIC_AUDIT_TIMESTAMP_STABILIZED",stable)

if __name__=="__main__":
    main()
