#!/usr/bin/env python3
"""過去のレース（非公開リポジトリの race_pages）から、馬場傾向の基準を作る。出力は集計だけ（docs/data/baba_bias/baselines_v1.json）。"""
import argparse
import glob
import json
import os

from baba_bias_v1 import core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_races(data_dir):
    for f in sorted(glob.glob(os.path.join(data_dir, "race_pages", "*.jsonl"))):
        with open(f, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except ValueError:
                    continue
                page = (rec.get("pages") or {}).get("result")
                if page:
                    r = core.parse_result_page(page, rec.get("code", ""), rec.get("date", ""))
                    if r:
                        yield r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"), required=not os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "data", "baba_bias", "baselines_v1.json"))
    a = ap.parse_args(argv)
    races = list(load_races(a.data))
    dates = sorted(r["date"] for r in races)
    base = core.build_baselines(races, {"from": dates[0] if dates else None, "to": dates[-1] if dates else None})
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(json.dumps({"races": base["source"], "time_keys": len(base["time"]), "sd": base["sd"], "ef": base["ef"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
