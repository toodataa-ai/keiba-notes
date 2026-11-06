"""血統（父・母の父・母）と相関のありそうな項目を探す（研究のみ）。
各項目について「父ごとの違い」が偶然（父のラベルを入れ替えた場合）を超えて大きいかを、
分散のうち父で説明できる割合（ε²＝偏りを補正した説明率）と入れ替え検定で見る。出生年で平均を引いてから比べる。"""
from __future__ import annotations
import argparse, collections, json, math, statistics, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sire_db_v1.debut_common import load_horses, mb


def traits(hs):
    # レースごとの上がり3Fの中央値（同じレースの馬が4頭以上取れているもの）
    by = collections.defaultdict(list)
    for h in hs.values():
        for r in h["history"] or []:
            if r.get("last3f") and r.get("code"):
                by[r["code"]].append(r["last3f"])
    med = {c: statistics.median(v) for c, v in by.items() if len(v) >= 6}
    out = {}
    for h in hs.values():
        hist = sorted([r for r in (h["history"] or []) if r.get("date") and r.get("surface") in ("芝", "ダート") and r.get("dist")], key=lambda r: r["date"])
        if not hist:
            continue
        d0 = hist[0]
        if mb(h["birth"], d0["date"]) > 40:  # 初出走が古い馬（履歴が途中から）は除く
            continue
        prof = h.get("profile") or {}
        t = {}
        t["デビュー月齢"] = mb(h["birth"], d0["date"])
        t["デビューが芝(1/0)"] = 1.0 if d0["surface"] == "芝" else 0.0
        t["デビュー距離(m)"] = float(d0["dist"])
        if d0.get("body_weight"):
            t["デビュー馬体重(kg)"] = float(d0["body_weight"])
        t["デビュー人気(対数オッズ)"] = math.log(d0["odds"]) if d0.get("odds") else None
        if isinstance(d0.get("finish"), int) and d0.get("heads"):
            t["デビュー着順(頭数比)"] = (d0["finish"] - 1) / max(1, d0["heads"] - 1)
        f3 = hist[:3]
        t["初3走で勝つ(1/0)"] = 1.0 if any(r.get("finish") == 1 for r in f3) else 0.0
        pos = []
        for r in hist[:3]:
            p = r.get("passing")
            if p and r.get("heads"):
                try:
                    pos.append((int(p.split("-")[0]) - 1) / max(1, r["heads"] - 1))
                except Exception:
                    pass
        if pos:
            t["序盤の位置取り(前0〜後1)"] = float(np.mean(pos))
        rel = [r["last3f"] - med[r["code"]] for r in hist[:3] if r.get("last3f") and r.get("code") in med]
        if rel:
            t["上がり3F(同レース中央値差・秒)"] = float(np.mean(rel))
        sm = [r["dist"] for r in hist[:5]]
        if len(hist) >= 4:
            t["距離の変化(初戦→4走目)"] = float(hist[3]["dist"] - hist[0]["dist"])
        if len(hist) >= 2 and hist[0]["surface"] and hist[1]["surface"]:
            t["2走目で芝ダを替える(1/0)"] = 1.0 if hist[0]["surface"] != hist[1]["surface"] else 0.0
        t["性が牡(1/0)"] = 1.0 if h.get("sex") == "牡" else 0.0
        t["生まれ月"] = float(int(h["birth"][5:7]))
        reg = prof.get("調教師（所属）", "")
        t["所属が栗東(1/0)"] = 1.0 if "栗東" in reg else (0.0 if "美浦" in reg else None)
        t["_year"] = h["birth"][:4]
        t["_sire"] = h["ped"]["sire"]; t["_dsire"] = h["ped"].get("dam_sire"); t["_dam"] = h["ped"].get("dam")
        t["_coat"] = prof.get("毛色"); t["_breeder"] = prof.get("生産者")
        out[h["id"]] = t
    return out


def eps2(vals, groups, rng, nperm=300):
    """分散のうちグループで説明できる割合（偏り補正）と、ラベル入れ替えの p 値。"""
    v = np.array(vals, float); g = np.array(groups)
    cnt = collections.Counter(g); keep = np.array([cnt[x] >= 8 for x in g])
    v = v[keep]; g = g[keep]
    if len(v) < 300: return None
    codes = {k: i for i, k in enumerate(sorted(set(g)))}; gi = np.array([codes[x] for x in g]); k = len(codes)
    def stat(gi_):
        n = len(v); gm = v.mean(); sums = np.bincount(gi_, v, k); cs = np.bincount(gi_, minlength=k)
        ssb = float(((sums / cs - gm) ** 2 @ cs)); sst = float(((v - gm) ** 2).sum()); ssw = sst - ssb
        msw = ssw / (n - k)
        return (ssb - (k - 1) * msw) / (sst + msw)
    obs = stat(gi); perm = [stat(rng.permutation(gi)) for _ in range(nperm)]
    p = (1 + sum(1 for x in perm if x >= obs)) / (nperm + 1)
    return {"n": int(len(v)), "groups": int(k), "eps2": float(obs), "null95": float(np.percentile(perm, 95)), "p": p}


def cramer(cats, groups):
    """カテゴリ項目（毛色・生産者）との関連：偏り補正ずみ Cramér の V"""
    cnt = collections.Counter(groups); cc = collections.Counter(cats)
    pairs = [(a, b) for a, b in zip(groups, cats) if b and cnt[a] >= 8 and cc[b] >= 8]
    if len(pairs) < 300: return None
    A = sorted({a for a, _ in pairs}); B = sorted({b for _, b in pairs}); ia = {a: i for i, a in enumerate(A)}; ib = {b: i for i, b in enumerate(B)}
    M = np.zeros((len(A), len(B)))
    for a, b in pairs: M[ia[a], ib[b]] += 1
    n = M.sum(); e = M.sum(1, keepdims=True) @ M.sum(0, keepdims=True) / n
    chi = ((M - e) ** 2 / e).sum(); phi2 = chi / n; r, c = M.shape
    phi2c = max(0, phi2 - (r - 1) * (c - 1) / (n - 1)); rc = r - (r - 1) ** 2 / (n - 1); cc2 = c - (c - 1) ** 2 / (n - 1)
    return {"n": int(n), "rows": r, "cols": c, "V": float(math.sqrt(phi2c / max(1e-9, min(rc - 1, cc2 - 1))))}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--out", default="pedigree_traits_result.json")
    a = ap.parse_args(); rng = np.random.default_rng(1)
    hs = load_horses(a.data); T = traits(hs); print("馬", len(T))
    # 出生年で平均を引く
    names = [k for k in {k for t in T.values() for k in t} if not k.startswith("_")]
    res = []
    for key, gkey in (("父", "_sire"), ("母の父", "_dsire"), ("母", "_dam")):
        for nm in sorted(names):
            ids = [i for i, t in T.items() if t.get(nm) is not None and t.get(gkey)]
            by = collections.defaultdict(list)
            for i in ids: by[T[i]["_year"]].append(T[i][nm])
            ym = {y: float(np.mean(v)) for y, v in by.items()}
            vals = [T[i][nm] - ym[T[i]["_year"]] for i in ids]; grp = [T[i][gkey] for i in ids]
            r = eps2(vals, grp, rng)
            if r: r.update({"by": key, "trait": nm}); res.append(r)
    for key, gkey in (("父", "_sire"), ("母の父", "_dsire")):
        for nm, ck in (("毛色", "_coat"), ("生産者", "_breeder")):
            ids = [i for i, t in T.items() if t.get(gkey) and t.get(ck)]
            r = cramer([T[i][ck] for i in ids], [T[i][gkey] for i in ids])
            if r: r.update({"by": key, "trait": nm, "kind": "cramer"}); res.append(r)
    print("%-6s %-26s %6s %6s %8s %8s %7s" % ("血統", "項目", "馬数", "父数", "ε²/V", "偶然95%", "p"))
    for r in sorted(res, key=lambda r: (r["by"], -(r.get("eps2") or r.get("V") or 0))):
        print("%-6s %-26s %6d %6d %8.4f %8s %7s" % (r["by"], r["trait"], r["n"], r.get("groups", r.get("rows")), r.get("eps2", r.get("V")), "%.4f" % r["null95"] if "null95" in r else "-", "%.3f" % r["p"] if "p" in r else "-"))
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
