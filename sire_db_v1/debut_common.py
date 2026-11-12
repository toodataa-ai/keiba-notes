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


def fill_debut_weights(drs, data_dir):
    """新馬戦の馬体重を、レースの結果ページ（race_pages）から補う。
    馬のページの履歴は『前走との増減』が無い初出走の体重を取り込めていないため（取り込み側の既知の欠け）。
    結果ページの『牝2/416』の416を、(レースコード, 馬ID)で結びつけて、出走の行（body_weight）に入れる。"""
    import re
    want = set(drs)
    pat_w = re.compile(r"/(\d{3,4})(?:\(|⟨|$)")
    pat_h = re.compile(r"/keiba/directory/horse/(\w+)/")
    got = total = 0
    for f in sorted(glob.glob(str(Path(data_dir) / "race_pages" / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            if '"code"' not in line:
                continue
            d = json.loads(line)
            code = d.get("code")
            if code not in want:
                continue
            tabs = ((d.get("pages") or {}).get("result") or {}).get("tables") or []
            wmap = {}
            for t in tabs:
                if not t or not t[0] or not any("馬体重" in (c or "") for c in t[0]):
                    continue
                ci = next(i for i, c in enumerate(t[0]) if "馬体重" in (c or ""))
                for row in t[1:]:
                    if len(row) <= ci:
                        continue
                    mh = pat_h.search(row[ci]); mw = pat_w.search(row[ci])
                    if mh and mw:
                        wmap[mh.group(1)] = int(mw.group(1))
            for h, r in drs[code]:
                total += 1
                w = wmap.get(str(h["id"]))
                if w and 300 <= w <= 650:
                    r["body_weight"] = w; got += 1
    return got, total
