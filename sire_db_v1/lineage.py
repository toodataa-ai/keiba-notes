"""種牡馬の「系統」の割り当て（研究のみ・予想には使わない）。

取得済みの血統（各馬の 父・父の父・3代目）から「種牡馬 → その父」の対応表を作り、
父をさかのぼって、最初に当たった「系統の長」で系統を決める（近いほうが優先）。
系統の長の一覧は下の HEADS（日本で一般に使われる呼び方に近い大きさ）。
どれにも当たらない種牡馬は、さかのぼった最後の祖先の名前を付けた「その他(祖先名)」にする。
"""
from __future__ import annotations
import collections, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 近いほうが優先（先にさかのぼって当たったもの）。左＝系統の長の名前（表記の揺れも含む）、右＝表示名
HEADS = [
    (("サンデーサイレンス", "Sunday Silence"), "サンデーサイレンス系"),
    (("キングカメハメハ",), "キングカメハメハ系"),
    (("Roberto",), "ロベルト系"),
    (("Seattle Slew",), "シアトルスルー系"),
    (("Fappiano",), "ファピアノ系"),
    (("Storm Cat",), "ストームキャット系"),
    (("Danzig",), "ダンチヒ系"),
    (("Sadler’s Wells", "Sadler's Wells"), "サドラーズウェルズ系"),
    (("Nijinsky",), "ニジンスキー系"),
    (("Blushing Groom",), "ブラッシンググルーム系"),
    (("Mr. Prospector",), "ミスタープロスペクター系(他)"),
    (("Northern Dancer",), "ノーザンダンサー系(他)"),
    (("Halo",), "ヘイロー系(他)"),
    (("Hail to Reason",), "ヘイルトゥリーズン系(他)"),
    (("Raise a Native",), "レイズアネイティヴ系(他)"),
    (("Caro",), "カロ系"),
    (("テスコボーイ",), "テスコボーイ系"),
]
_HEAD = {n: label for names, label in HEADS for n in names}


def parent_map(hs):
    """種牡馬 → 父。同じ馬に別の父が出たら、多いほうを採る。"""
    P = collections.defaultdict(collections.Counter)

    def add(c, p):
        if c and p:
            P[c][p] += 1

    for h in hs.values():
        p = h.get("ped") or {}
        g = p.get("gen3") or []
        add(p.get("sire"), p.get("sire_sire"))
        add(p.get("sire_sire"), g[0] if len(g) > 0 else None)   # 父の父の父
        add(p.get("dam_sire"), g[4] if len(g) > 4 else None)    # 母の父の父
    return {k: v.most_common(1)[0][0] for k, v in P.items()}


def chain(name, par, limit=12):
    out = [name]
    while out[-1] in par and par[out[-1]] not in out and len(out) < limit:
        out.append(par[out[-1]])
    return out


def line_of(name, par):
    if not name:
        return None
    c = chain(name, par)
    for a in c:  # 自分自身も含めて、近い順に最初に当たった系統の長
        if a in _HEAD:
            return _HEAD[a]
    return "その他(%s)" % c[-1]


def lineage_map(hs):
    par = parent_map(hs)
    names = set()
    for h in hs.values():
        p = h.get("ped") or {}
        names.update(x for x in (p.get("sire"), p.get("dam_sire"), p.get("sire_sire")) if x)
    return {n: line_of(n, par) for n in sorted(names)}, par


def grp(x):
    return "その他" if x and x.startswith("その他") else x


def summary(hs, min_starters=150, split="2024-01-01", since="2021-01-01"):
    """公開してよい集計だけ：系統ごとの頭数の割合と、新馬戦のオッズ比（A/E＝実際の勝ち÷オッズ由来の期待）。
    前半（since〜split前）と後半（split以降）に分けて、同じ向きが続くかを見る。馬や父の名前は出さない（系統名のみ）。"""
    from sire_db_v1.debut_common import debut_races
    LM, _ = lineage_map(hs)
    sires = collections.Counter(grp(LM.get(h["ped"]["sire"])) for h in hs.values())
    tot = sum(sires.values())
    T = collections.defaultdict(lambda: [0, 0, 0.0, 0, 0, 0.0])
    nrace = 0
    for code, lst in debut_races(hs).items():
        d = lst[0][1]["date"]
        if d < since:
            continue
        ps = [0.8 / r["odds"] for h, r in lst]; z = sum(ps); nrace += 1
        i = 0 if d < split else 3
        for (h, r), p in zip(lst, ps):
            k = T[grp(LM.get(h["ped"]["sire"]))]
            k[i] += 1; k[i + 1] += 1 if r["finish"] == 1 else 0; k[i + 2] += p / z
    ae = lambda w, e: round(w / e, 2) if e else None
    rows = [{"line": ln, "starters_early": k[0], "starters_late": k[3], "ae_early": ae(k[1], k[2]), "ae_late": ae(k[4], k[5])}
            for ln, k in sorted(T.items(), key=lambda x: -(x[1][0] + x[1][3])) if k[0] + k[3] >= min_starters]
    return {"horses": tot, "sires": len({h["ped"]["sire"] for h in hs.values()}),
            "share": [{"line": k, "pct": round(100 * n / tot, 1)} for k, n in sires.most_common() if n / tot >= 0.01],
            "debut_races": nrace, "split": split, "debut_ae": rows}


def main():
    import argparse
    from sire_db_v1.debut_common import load_horses
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="sire_db_v1/lineage_v1.json")
    a = ap.parse_args()
    hs = load_horses(a.data)
    m, par = lineage_map(hs)
    sires = collections.Counter(h["ped"]["sire"] for h in hs.values())
    by = collections.Counter()
    for s, n in sires.items():
        by[m.get(s)] += n
    tot = sum(by.values())
    print("種牡馬", len(sires), "頭数", tot)
    for k, n in by.most_common():
        print("  %-26s %6d  %4.1f%%" % (k, n, 100 * n / tot))
    Path(a.out).write_text(json.dumps({"line_of": m, "parent_of": par}, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
