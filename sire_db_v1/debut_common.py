"""新馬戦の研究用の共通部品（研究のみ・予想には使わない）。入力は非公開リポジトリの data_v2。"""
from __future__ import annotations
import glob, json, collections
from datetime import date
from pathlib import Path


def mb(birth, dt):
    b = date.fromisoformat(birth); d = date.fromisoformat(dt)
    return (d.year - b.year) * 12 + d.month - b.month - (1 if d.day < b.day else 0)


def load_horses(data_dir):
    hs = {}
    for f in sorted(glob.glob(str(Path(data_dir) / "horses_*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            h = json.loads(line)
            if h.get("birth") and (h.get("ped") or {}).get("sire"):
                hs[h["id"]] = h
    return hs


def debut_races(hs, done=None):
    """新馬戦（レース名に「新馬」）のレース単位の表。出走馬が全員そろっているものだけ。"""
    races = collections.defaultdict(list)
    for h in hs.values():
        for r in h.get("history") or []:
            if "新馬" in (r.get("race") or "") and r.get("code"):
                races[r["code"]].append((h, r))
    out = {}
    for code, lst in races.items():
        heads = lst[0][1].get("heads")
        if not heads or len(lst) != heads:
            continue
        if any(not r.get("odds") for _, r in lst):
            continue
        if sum(1 for _, r in lst if r.get("finish") == 1) != 1:
            continue
        out[code] = lst
    return out
