"""父データベースの集計（研究のみ）。
入力: SIRE_DATA_DIR（非公開リポジトリの data_v2）。出力: 集計結果のJSONだけ（生データは出さない）。
考え方: 各出走について「同じ頭数の中で運だけなら 1/頭数 勝つ」を期待値として、
実際の勝ち数÷期待値（A/E）を 父×（芝ダ・距離帯）×（絶対月齢の帯）で比べる。
検証: cutoff より前のデータだけで作った傾向が、cutoff 以降の出走でも効くかを見る（漏れ防止）。"""
from __future__ import annotations
import argparse, collections, glob, json, math, os
from datetime import date
from pathlib import Path

AGE_BANDS = [(0, 23, "~1歳11か月"), (24, 29, "2歳0〜5か月"), (30, 35, "2歳6〜11か月"), (36, 41, "3歳前半"), (42, 47, "3歳後半"), (48, 59, "4歳"), (60, 999, "5歳~")]
AGE_BANDS = [(0, 26, "2歳前半まで(~26か月)"), (27, 35, "2歳後半(27〜35か月)"), (36, 41, "3歳前半(36〜41か月)"), (42, 47, "3歳後半(42〜47か月)"), (48, 59, "4歳(48〜59か月)"), (60, 999, "5歳以上(60か月~)")]


def age_band(m):
    for lo, hi, name in AGE_BANDS:
        if lo <= m <= hi:
            return name
    return None


def dist_band(d):
    return "短距離(~1400)" if d <= 1400 else "マイル(1401~1800)" if d <= 1800 else "中距離(1801~2200)" if d <= 2200 else "長距離(2201~)"


def months_between(birth: str, dt: str) -> int:
    b = date.fromisoformat(birth); d = date.fromisoformat(dt)
    return (d.year - b.year) * 12 + d.month - b.month - (1 if d.day < b.day else 0)


def load(data_dir: Path):
    rows = []
    for f in sorted(glob.glob(str(data_dir / "horses_*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            h = json.loads(line)
            sire = (h.get("ped") or {}).get("sire"); birth = h.get("birth")
            if not sire or not birth:
                continue
            for r in h.get("history") or []:
                if not isinstance(r.get("finish"), int) or not r.get("heads") or r.get("surface") not in ("芝", "ダート") or not r.get("dist"):
                    continue
                try:
                    m = months_between(birth, r["date"])
                except Exception:
                    continue
                ab = age_band(m)
                if ab is None or m < 18:
                    continue
                rows.append((r["date"], sire, r["surface"], dist_band(r["dist"]), ab, r["finish"], r["heads"], h["id"], r["code"], r.get("odds")))
    # 同じレースが複数の馬から重複しないよう、(馬, レースコード) で一意にする
    seen = set(); out = []
    for x in rows:
        k = (x[7], x[8])
        if k in seen:
            continue
        seen.add(k); out.append(x)
    return out


BASE = "heads"


def exp1(r):
    if BASE == "odds":
        return 0.8 / r[9]
    return 1.0 / r[6]


def ae(rows, k=0.0):
    w = sum(1 for r in rows if r[5] == 1); e = sum(exp1(r) for r in rows)
    return {"starts": len(rows), "wins": w, "exp": round(e, 2), "ae": round((w + k) / (e + k), 3) if e + k else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("SIRE_DATA_DIR"))
    ap.add_argument("--cutoff", default="2025-01-01")
    ap.add_argument("--min-starts", type=int, default=400)
    ap.add_argument("--out", default="sire_aggregate_v1.json")
    ap.add_argument("--baseline", choices=["heads", "odds"], default="heads", help="期待値：頭数だけ／単勝オッズ（0.8/オッズ）")
    a = ap.parse_args()
    global BASE
    BASE = a.baseline
    rows = load(Path(a.data))
    if BASE == "odds":
        rows = [r for r in rows if r[9] and r[9] > 0]
    train = [r for r in rows if r[0] < a.cutoff]; test = [r for r in rows if r[0] >= a.cutoff]
    out = {"baseline": a.baseline, "cutoff": a.cutoff, "total_starts": len(rows), "train_starts": len(train), "test_starts": len(test),
           "population_by_age": {n: ae([r for r in rows if r[4] == n]) for _, _, n in AGE_BANDS}}
    # 検証：訓練期間の 父×(芝ダ,距離帯)×月齢帯 のA/E（縮小）で、テスト期間の出走を予測
    K = 15.0
    cell = collections.defaultdict(list)
    for r in train:
        cell[(r[1], r[2], r[3])].append(r)
    sire_age = collections.defaultdict(list)
    for r in train:
        sire_age[(r[1], r[2], r[4])].append(r)
    cache = {}
    def mult(r, level):
        key = (level, r[1], r[2], r[3], r[4])
        if key in cache:
            return cache[key]
        rs = cell.get((r[1], r[2], r[3]), []) if level == "sire_dist" else sire_age.get((r[1], r[2], r[4]), [])
        w = sum(1 for x in rs if x[5] == 1); e = sum(exp1(x) for x in rs)
        cache[key] = (w + K) / (e + K)
        return cache[key]
    ver = {}
    for level in ("sire_dist", "sire_age"):
        sc = sorted(((mult(r, level), r) for r in test if r[1] in {s for s, *_ in cell} ), key=lambda t: t[0])
        n = len(sc); buckets = []
        for q in range(5):
            part = [r for _, r in sc[q * n // 5:(q + 1) * n // 5]]
            if not part:
                continue
            m = sum(mult(r, level) for r in part) / len(part)
            buckets.append({"bucket": q + 1, "pred_mult": round(m, 3), **ae(part)})
        ver[level] = buckets
    out["validation_after_cutoff"] = ver
    # 父ごとの成熟の型（訓練＋テスト全体・参考表示）
    prof = []
    bysire = collections.defaultdict(list)
    for r in rows:
        bysire[r[1]].append(r)
    for s, rs in bysire.items():
        if len(rs) < a.min_starts:
            continue
        ages = {n: ae([r for r in rs if r[4] == n], K) for _, _, n in AGE_BANDS}
        early = ae([r for r in rs if r[4] in ("2歳前半まで(~26か月)", "2歳後半(27〜35か月)")], K)["ae"]
        late = ae([r for r in rs if r[4] in ("4歳(48〜59か月)", "5歳以上(60か月~)")], K)["ae"]
        prof.append({"sire": s, "starts": len(rs), "ae_all": ae(rs, K)["ae"], "early_ae": early, "late_ae": late, "late_minus_early": round(late - early, 3), "by_age": {n: v["ae"] for n, v in ages.items()},
                     "starts_by_age": {n: v["starts"] for n, v in ages.items()}})
    prof.sort(key=lambda x: x["late_minus_early"])
    out["maturity_profiles"] = prof
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"total": len(rows), "train": len(train), "test": len(test), "sires": len(prof)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
