"""JRA-VAN記事（血統予想）の主張がデータで確かめられるかの分析（研究のみ・予想には使わない）。
主張：①種牡馬ごとに距離・芝ダの得意不得意がある ②晩成/早熟の型がある ③同じ母の子は似る ④母の父の影響 ⑤系統（父の父）で傾向が違う。
見方：全体の「勝ちやすさ」は単勝オッズ（0.8÷オッズ）で期待値を作り、勝ち÷期待(A/E)で、オッズに織り込み済みかを見る。
「前半の期間で見えた差が後半でも続くか」（持続性）で、偶然でない違いかを確かめる。"""
from __future__ import annotations
import argparse, collections, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sire_db_v1.debut_common import load_horses, mb

K = 3.0
SPLIT = "2024-07-01"


def dband(d):
    return "短(~1400)" if d <= 1400 else "マイル(~1800)" if d <= 1800 else "中(~2200)" if d <= 2200 else "長(2201~)"


def rows_of(hs, since="2022-01-01"):
    out = []
    for h in hs.values():
        p = h["ped"]
        for r in h.get("history") or []:
            if r.get("date", "") < since or not r.get("odds") or not isinstance(r.get("finish"), int) or r.get("surface") not in ("芝", "ダート") or not r.get("dist"):
                continue
            try: m = mb(h["birth"], r["date"])
            except Exception: continue
            out.append(dict(date=r["date"], sire=p["sire"], ss=p.get("sire_sire"), ds=p.get("dam_sire"), dam=p.get("dam"), hid=h["id"], sur=r["surface"], d=r["dist"], band=dband(r["dist"]), m=m,
                            age="2〜3歳" if m <= 47 else "4歳以上", win=1 if r["finish"] == 1 else 0, p=0.8 / r["odds"], fin=(r["finish"] - 1) / max(1, (r.get("heads") or 2) - 1), code=r.get("code")))
    return out


def lae(w, e): return math.log((w + K) / (e + K))


def cell_stats(rows, key, seg):
    S = collections.defaultdict(lambda: [0, 0.0, 0])
    for r in rows:
        c = S[(r[key], r[seg])]; c[0] += r["win"]; c[1] += r["p"]; c[2] += 1
    return S


def persistence(rows, key, seg, min_e=6.0):
    """父ごとの『その区分のA/E − 父全体のA/E』が、前半と後半で相関するか"""
    a = [r for r in rows if r["date"] < SPLIT]; b = [r for r in rows if r["date"] >= SPLIT]
    res = {}
    for nm, rr in (("a", a), ("b", b)):
        S = cell_stats(rr, key, seg); tot = collections.defaultdict(lambda: [0, 0.0])
        for (s, g), (w, e, n) in S.items(): tot[s][0] += w; tot[s][1] += e
        res[nm] = (S, tot)
    sires = sorted({s for (s, g) in res["a"][0]} & {s for (s, g) in res["b"][0]})
    segs = sorted({g for (s, g) in res["a"][0]})
    X, Y, W = [], [], []
    for s in sires:
        ta, tb = res["a"][1][s], res["b"][1][s]
        if ta[1] < min_e * 2 or tb[1] < min_e * 2: continue
        for g in segs:
            ca = res["a"][0].get((s, g)); cb = res["b"][0].get((s, g))
            if not ca or not cb or ca[1] < min_e or cb[1] < min_e: continue
            X.append(lae(ca[0], ca[1]) - lae(*ta)); Y.append(lae(cb[0], cb[1]) - lae(*tb)); W.append(min(ca[1], cb[1]))
    if len(X) < 20: return None
    X, Y = np.array(X), np.array(Y)
    r = float(np.corrcoef(X, Y)[0, 1]); rng = np.random.default_rng(0)
    bs = [np.corrcoef(X[i], Y[i])[0, 1] for i in (rng.integers(0, len(X), len(X)) for _ in range(1000))]
    return {"cells": len(X), "r": r, "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


def sire_table(rows, sire, segkey):
    S = cell_stats([r for r in rows if r["sire"] == sire], "sire", segkey); out = {}
    for (s, g), (w, e, n) in sorted(S.items(), key=lambda kv: str(kv[0][1])):
        out[g] = {"出走": n, "勝ち": w, "期待": round(e, 1), "AE": round(w / e, 2) if e else None, "z": round((w - e) / math.sqrt(e), 2) if e else None}
    return out


def eps2_group(vals, groups, rng, nperm=300, mingroup=2, maxn=60000):
    v = np.array(vals, float); g = np.array(groups, dtype=object)
    cnt = collections.Counter(g); keep = np.array([cnt[x] >= mingroup for x in g]); v = v[keep]; g = g[keep]
    codes = {k: i for i, k in enumerate(sorted(set(g), key=str))}; gi = np.array([codes[x] for x in g]); k = len(codes)
    n = len(v)
    if n < 300 or k < 30: return None
    def stat(gi_):
        gm = v.mean(); sums = np.bincount(gi_, v, k); cs = np.bincount(gi_, minlength=k)
        ssb = float(((sums / cs - gm) ** 2 @ cs)); sst = float(((v - gm) ** 2).sum()); msw = (sst - ssb) / (n - k)
        return (ssb - (k - 1) * msw) / (sst + msw)
    obs = stat(gi); perm = [stat(rng.permutation(gi)) for _ in range(nperm)]
    return {"n": int(n), "groups": int(k), "eps2": float(obs), "null95": float(np.percentile(perm, 95)), "p": (1 + sum(1 for x in perm if x >= obs)) / (nperm + 1)}


def horse_level(rows):
    """馬ごとの成績（最初の6走まで）：着順の頭数比（小さいほど上位）、勝ちの有無、オッズ由来の期待に対する差"""
    by = collections.defaultdict(list)
    for r in sorted(rows, key=lambda r: r["date"]): by[r["hid"]].append(r)
    H = {}
    for hid, rs in by.items():
        rs = rs[:6]
        if len(rs) < 3: continue
        H[hid] = dict(sire=rs[0]["sire"], ss=rs[0]["ss"], ds=rs[0]["ds"], dam=rs[0]["dam"], fin=float(np.mean([r["fin"] for r in rs])), win=float(any(r["win"] for r in rs)),
                      ae=float(sum(r["win"] - r["p"] for r in rs) / len(rs)), mkt=float(np.mean([r["p"] for r in rs])))
    return H


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--out", default="article_claims_result.json")
    a = ap.parse_args(); rng = np.random.default_rng(3)
    hs = load_horses(a.data); rows = rows_of(hs); print("出走", len(rows), "馬", len({r["hid"] for r in rows}))
    res = {}
    yc = collections.Counter(r["date"][:4] for r in rows); print("年別出走(2022〜)", dict(sorted(yc.items())))
    # --- ① 種牡馬の得意不得意（オッズ込み）：前半→後半の持続性
    print("\n【①②⑤ 前半(~2024/6)で見えた『父×区分の得意不得意』が後半でも続くか（相関r。0なら偶然・正ならほんもの）】")
    res["persist"] = {}
    for label, key, seg in (("父×芝ダ", "sire", "sur"), ("父×距離帯", "sire", "band"), ("父×年齢(2〜3歳/4歳以上=晩成)", "sire", "age"), ("父の父(系統)×芝ダ", "ss", "sur"), ("父の父(系統)×距離帯", "ss", "band"), ("母の父×芝ダ", "ds", "sur"), ("母の父×距離帯", "ds", "band")):
        r = persistence(rows, key, seg); res["persist"][label] = r
        print("  %-28s %s" % (label, "データ不足" if not r else "セル%d  r=%.3f  95%%[%.3f, %.3f]" % (r["cells"], r["r"], r["ci"][0], r["ci"][1])))
    # --- 記事に出てくる種牡馬
    print("\n【記事の例の種牡馬：オッズ込みの勝ち/期待(A/E)。z=(勝ち−期待)/√期待。±2を超えれば目立つ】")
    res["named"] = {}
    for s in ("ロードカナロア", "ゴールドアリュール", "モーリス", "ディープインパクト", "ハーツクライ", "ヘニーヒューズ", "キングカメハメハ", "エピファネイア"):
        t = {"芝ダ": sire_table(rows, s, "sur"), "距離帯": sire_table(rows, s, "band"), "年齢": sire_table(rows, s, "age")}; res["named"][s] = t
        if not t["芝ダ"]: print(" ", s, "データなし"); continue
        print(" ", s)
        for k, v in t.items(): print("    ", k, {g: (x["出走"], x["AE"], x["z"]) for g, x in v.items()})
    # --- 走る場所の偏り（産駒がどこを走るか）
    print("\n【産駒の走る場所の偏り（ロードカナロア・ゴールドアリュール等）】")
    base = collections.Counter(r["sur"] for r in rows); tot = sum(base.values()); bd = np.mean([r["d"] for r in rows])
    res["where"] = {}
    for s in ("ロードカナロア", "ゴールドアリュール", "ディープインパクト", "ヘニーヒューズ", "モーリス", "ハーツクライ"):
        rs = [r for r in rows if r["sire"] == s]
        if not rs: continue
        x = {"出走": len(rs), "ダート割合": round(sum(1 for r in rs if r["sur"] == "ダート") / len(rs), 3), "平均距離": round(float(np.mean([r["d"] for r in rs]))), "短距離(~1400)割合": round(sum(1 for r in rs if r["d"] <= 1400) / len(rs), 3), "4歳以上の出走割合": round(sum(1 for r in rs if r["m"] >= 48) / len(rs), 3)}
        res["where"][s] = x; print(" ", s, x)
    print("  全体: ダート割合 %.3f 平均距離 %.0f 短距離割合 %.3f 4歳以上割合 %.3f" % (base["ダート"] / tot, bd, np.mean([r["d"] <= 1400 for r in rows]), np.mean([r["m"] >= 48 for r in rows])))
    # --- ③④ 母・母の父の影響（馬ごとの成績の似かた）
    print("\n【③④ 馬ごとの成績が、母・母の父・父でどれだけ説明できるか（偏り補正ずみ説明率ε²。偶然95%線より大きければ有意）】")
    H = horse_level(rows); res["family"] = {}
    for metric, lab in (("fin", "着順の頭数比(小さいほど上位)"), ("win", "初6走で勝つ"), ("ae", "オッズ以上に勝った度合い")):
        for gk, gl in (("dam", "母(同じ母の子)"), ("sire", "父"), ("ds", "母の父"), ("ss", "父の父")):
            ids = [i for i, h in H.items() if h[gk]]
            r = eps2_group([H[i][metric] for i in ids], [H[i][gk] for i in ids], rng, mingroup=2 if gk == "dam" else 8)
            res["family"][f"{lab}|{gl}"] = r
            if r: print("  %-22s %-14s 馬%6d 群%5d  ε²=%.4f  偶然95%%=%.4f  p=%.3f" % (lab, gl, r["n"], r["groups"], r["eps2"], r["null95"], r["p"]))
    # 父の影響を取り除いたあとの母・母の父
    print("\n  ▷父の平均を引いたあと（父の影響を除く）の母・母の父")
    sm = collections.defaultdict(list)
    for h in H.values(): sm[h["sire"]].append(h)
    for metric, lab in (("fin", "着順の頭数比"), ("ae", "オッズ以上に勝った度合い")):
        mean_s = {s: np.mean([h[metric] for h in v]) for s, v in sm.items() if len(v) >= 5}
        ids = [i for i, h in H.items() if h["sire"] in mean_s]
        resid = {i: H[i][metric] - mean_s[H[i]["sire"]] for i in ids}
        for gk, gl in (("dam", "母"), ("ds", "母の父")):
            ii = [i for i in ids if H[i][gk]]
            r = eps2_group([resid[i] for i in ii], [H[i][gk] for i in ii], rng, mingroup=2 if gk == "dam" else 8)
            res["family"][f"父除く|{lab}|{gl}"] = r
            if r: print("  %-14s %-8s 馬%6d 群%5d  ε²=%.4f  偶然95%%=%.4f  p=%.3f" % (lab, gl, r["n"], r["groups"], r["eps2"], r["null95"], r["p"]))
    # --- 種牡馬別 勝ち数上位（記事の表の再現）
    print("\n【記事の表の再現：2022〜26年・勝ち数上位5（芝2000m以上／ダート1400m以下）。取得済みレースのみ】")
    res["top"] = {}
    for lab, f in (("芝2000m以上", lambda r: r["sur"] == "芝" and r["d"] >= 2000), ("ダート1400m以下", lambda r: r["sur"] == "ダート" and r["d"] <= 1400)):
        c = collections.defaultdict(lambda: [0, 0, 0.0])
        for r in rows:
            if f(r): x = c[r["sire"]]; x[0] += r["win"]; x[1] += 1; x[2] += r["p"]
        top = sorted(c.items(), key=lambda kv: -kv[1][0])[:5]
        res["top"][lab] = [(s, w, n, round(w / n * 100, 1), round(w / e, 2)) for s, (w, n, e) in top]
        print(" ", lab); [print("    %-12s 勝%3d 出走%4d 勝率%.1f%%  A/E %.2f" % t) for t in res["top"][lab]]
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()


def maturity(hs, a_years=("2019", "2021", "2023"), b_years=("2020", "2022")):
    """晩成/早熟：父ごとの『初勝利の月齢』が、別の世代（生まれ年）の産駒でも同じ向きに出るか"""
    stats = {}
    for h in hs.values():
        y = h["birth"][:4]
        if y not in a_years + b_years: continue
        ws = sorted(r["date"] for r in (h.get("history") or []) if r.get("finish") == 1 and r.get("date"))
        hist = sorted(r["date"] for r in (h.get("history") or []) if r.get("date"))
        if not hist or mb(h["birth"], hist[0]) > 36: continue  # 履歴の最初が古い途中からの馬は除く
        if ws:
            stats.setdefault(h["ped"]["sire"], {"a": [], "b": [], "d": []})["a" if y in a_years else "b"].append(mb(h["birth"], ws[0]))
    X, Y, names = [], [], []
    for s, v in stats.items():
        if len(v["a"]) >= 10 and len(v["b"]) >= 8:
            X.append(np.mean(v["a"])); Y.append(np.mean(v["b"])); names.append((s, len(v["a"]) + len(v["b"]), (np.mean(v["a"]) * len(v["a"]) + np.mean(v["b"]) * len(v["b"])) / (len(v["a"]) + len(v["b"]))))
    X, Y = np.array(X), np.array(Y); r = float(np.corrcoef(X, Y)[0, 1]); rng = np.random.default_rng(0)
    bs = [np.corrcoef(X[i], Y[i])[0, 1] for i in (rng.integers(0, len(X), len(X)) for _ in range(1000))]
    allw = [m for v in stats.values() for m in v["a"] + v["b"]]
    return {"sires": len(X), "r": r, "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "pop_mean": float(np.mean(allw)),
            "late": sorted(names, key=lambda t: -t[2])[:5], "early": sorted(names, key=lambda t: t[2])[:5], "named": {s: next(((n, round(m, 1)) for (q, n, m) in names if q == s), None) for s in ("モーリス", "ロードカナロア", "ディープインパクト", "ハーツクライ", "エピファネイア", "ヘニーヒューズ")}}


if __name__ == "__main__":
    pass
