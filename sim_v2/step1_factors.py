"""STEP1（全頭の確率）の補助データを、開催日ごとに自動で作る。
 ・調教師の強さ T1（その調教師の過去のJRA成績：3着内率−全体、少ない時は全体へ縮小）
 ・上がり順位のよさ K2（直近3走の上がり3Fが、そのレースの出走馬の中で何番目だったか）。直近3走の順位は予想の参考情報として必ず書く
 ・この距離帯での過去の成績 apt（shared-v1.2 の補正を計算済みにしたもの）
出力：docs/data/step1_factors/<日付>_<競馬場>.json（馬ごとの数字と倍率。レースの結果・オッズは含まない。公開してよい集計・派生値だけ）
元データ：非公開リポジトリ data_v2（馬ごとの履歴・race_pages）＋ Sportnavi の出馬表・馬のページ・結果ページ（最新の分は取得、2秒おき）
倍率の係数は sim_v2/step1_factor_coef.json（step1_fit.py が決める）。使い方：
  python3 -m sim_v2.step1_factors --data private/data_v2 --dates 2026-11-28"""
from __future__ import annotations
import argparse, collections, glob, json, math, re, sys, time
from datetime import date as D
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parents[1]
COEF = json.loads((ROOT / "sim_v2/step1_factor_coef.json").read_text(encoding="utf-8"))
GAP = 2.0
UA = "keiba-notes research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
CAP_SD = 1.5          # 各要素は標準偏差の±1.5倍で打ち切る（検証の範囲の外へ出さない）
K_TRAINER = 30.0      # 調教師の3着内率の縮小（全体の率を30走ぶん足す）
LOOKBACK = 5          # 上がり順位は、直近5走のうち順位の分かる最新3走


def bucket(d): return int(round(d / 200.0) * 200)


def last3f_list(tables):
    out = []
    for t in tables:
        if t and t[0] and t[0][0] == "着順":
            for row in t[1:]:
                for c in row:
                    m = re.fullmatch(r"(?:\d+-?)+ (\d\d\.\d)", (c or "").strip())
                    if m: out.append(float(m.group(1))); break
    return out


def load_race_index(pages_dir):
    """race_pages から 調教師（{code:{馬ID:調教師ID}}）と 上がり3Fの一覧（{code:[…]}）を一度に読む"""
    trainers, l3 = {}, {}
    runs = []          # 調教師ごとの数え上げ用：(日付, 調教師ID, 3着内か)。レース結果ページから直接＝最新のレースまで入る
    for f in sorted(glob.glob(str(Path(pages_dir) / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line); r = (d.get("pages") or {}).get("result") or {}
            tb = r.get("tables") or []
            m = {}
            for t in tb:
                if t and t[0] and t[0][0] == "着順":
                    for row in t[1:]:
                        h = tr = None
                        for c in row:
                            a = re.search(r"horse/(\d+)/", c or ""); b = re.search(r"trainer/(\d+)/", c or "")
                            if a: h = a.group(1)
                            if b: tr = b.group(1)
                        if h and tr:
                            m[h] = tr
                            fin = (row[0] or "").strip()
                            if fin.isdigit() and d.get("date"):
                                runs.append((d["date"], tr, 1 if int(fin) <= 3 else 0))
            if m: trainers[d["code"]] = m
            v = last3f_list(tb)
            if len(v) >= 5: l3[d["code"]] = v
    load_race_index.runs = runs
    return trainers, l3


def trainer_counts_from_runs(runs, before):
    """{調教師ID:[3着内, 出走]} と全体 [3着内, 出走]（before より前の出走だけ）。runs は load_race_index.runs"""
    cnt = collections.defaultdict(lambda: [0, 0]); allc = [0, 0]
    for date, tr, top in runs:
        if date >= before: continue
        cnt[tr][0] += top; cnt[tr][1] += 1; allc[0] += top; allc[1] += 1
    return cnt, allc


def trainer_counts(hs, trainers, before):
    """{調教師ID:[3着内, 出走]} と全体 [3着内, 出走]（before より前の出走だけ）"""
    cnt = collections.defaultdict(lambda: [0, 0]); allc = [0, 0]
    for h in hs.values():
        for r in h.get("history") or []:
            tr = (trainers.get(r.get("code")) or {}).get(h["id"])
            if not tr or not r.get("date") or r["date"] >= before or not isinstance(r.get("finish"), int): continue
            top = 1 if r["finish"] <= 3 else 0
            cnt[tr][0] += top; cnt[tr][1] += 1; allc[0] += top; allc[1] += 1
    return cnt, allc


def trainer_factor(cnt, allc, tid):
    base = allc[0] / allc[1] if allc[1] > 1000 else 0.2
    n = cnt.get(tid, [0, 0]) if tid else [0, 0]
    rate = (n[0] + K_TRAINER * base) / (n[1] + K_TRAINER)
    t1 = rate - base
    sd = COEF["T1"]["sd"]; t1c = max(-CAP_SD * sd, min(CAP_SD * sd, t1))
    return {"t1": round(t1, 4), "runs": n[1], "top3": n[0], "top3_rate_raw": round(n[0] / n[1], 3) if n[1] else None, "base": round(base, 3),
            "mult": round(math.exp(COEF["T1"]["coef_per_unit"] * t1c), 3)}


def kick_factor(hist, before, l3map):
    """直近5走のうち上がり順位の分かる最新3走から K2。順位は同タイムを同順位に数える（速い馬の数＋1）。"""
    past = [r for r in (hist or []) if r.get("date") and r["date"] < before and isinstance(r.get("finish"), int)]
    past.sort(key=lambda r: r["date"]); past = past[-LOOKBACK:]
    used = []
    for r in reversed(past):
        l3 = l3map.get(r.get("code")); t = r.get("last3f")
        if not l3 or not t: continue
        faster = sum(1 for x in l3 if x < t)
        used.append({"date": r["date"], "code": r["code"], "venue": r.get("venue"), "race": r.get("race"), "surface": r.get("surface"), "dist": r.get("dist"),
                     "last3f": t, "rank": faster + 1, "field": len(l3), "finish": r["finish"], "share_faster": round(faster / len(l3), 3)})
        if len(used) == 3: break
    n = len(used)
    if n == 0:
        return {"k2": None, "runs_used": 0, "recent": [], "mult": 1.0}
    k2 = sum(1 - u["share_faster"] for u in used) / (n + 1)
    sd, mu = COEF["K2"]["sd"], COEF["K2"]["mean"]; k2c = max(mu - CAP_SD * sd, min(mu + CAP_SD * sd, k2))
    return {"k2": round(k2, 4), "runs_used": n, "recent": used, "mult": round(math.exp(COEF["K2"]["coef_per_unit"] * (k2c - mu)), 3)}


def dist_factor(hist, before, dist):
    rows = [r for r in (hist or []) if r.get("date") and r["date"] < before and isinstance(r.get("finish"), int) and r.get("dist")]
    n_all = len(rows); t_all = sum(1 for r in rows if r["finish"] <= 3)
    base = (t_all + 0.25 * 3) / (n_all + 3)
    b = bucket(dist); inb = [r for r in rows if bucket(r["dist"]) == b]
    n = len(inb); t = sum(1 for r in inb if r["finish"] <= 3)
    apt = (t + base * 3) / (n + 3) - base if n else 0.0
    aptc = max(-0.15, min(0.15, apt))
    return {"apt": round(apt, 4), "bucket_m": b, "runs_in_bucket": n, "top3_in_bucket": t, "mult": round(math.exp(0.7 * aptc), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--dates", required=True)
    ap.add_argument("--cards", nargs="*", help="出馬表JSONを直接指定（試験用）")
    ap.add_argument("--no-fetch", action="store_true", help="ネットから取らず、非公開データだけで作る（試験用）")
    ap.add_argument("--out-dir", default=str(ROOT / "docs/data/step1_factors"))
    a = ap.parse_args()
    import requests
    from bs4 import BeautifulSoup
    from sim_v2.upcoming import latest_cards
    from sire_db_v1.crawl import parse_horse, HORSE
    from sire_db_v1.race_crawl import dump_page, PAGES
    from sire_db_v1.debut_common import load_horses
    from claude_track.fetch_odds import race_code

    dates = [d.strip() for d in a.dates.split(",") if d.strip()]
    cards = [json.loads(Path(c).read_text(encoding="utf-8")) for c in a.cards] if a.cards else latest_cards(dates)
    if not cards:
        print("no cards"); return
    s = requests.Session(); s.headers["User-Agent"] = UA

    def get(u):
        for i in range(3):
            try:
                r = s.get(u, timeout=30); time.sleep(GAP)
                if r.status_code == 404: return None
                r.raise_for_status(); return BeautifulSoup(r.text, "html.parser")
            except requests.RequestException as e:
                print("retry", u, e, file=sys.stderr); time.sleep(5 * (i + 1))
        return None

    print("非公開データを読み込み中…", file=sys.stderr)
    hs = load_horses(a.data)
    trainers, l3map = load_race_index(Path(a.data) / "race_pages")
    print(f"馬 {len(hs)} / 調教師の分かるレース {len(trainers)} / 上がりの分かるレース {len(l3map)}", file=sys.stderr)
    byname = collections.defaultdict(list)
    for hid_, h_ in hs.items():
        if h_.get("name"): byname[h_["name"]].append(hid_)
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    fetched_races = {}

    def l3_for(code):
        if code in l3map: return
        if a.no_fetch or code in fetched_races: return
        soup = get(PAGES["result"].format(code=code)); fetched_races[code] = 1
        if soup is None: return
        v = last3f_list(dump_page(soup, "")["tables"])
        if len(v) >= 5: l3map[code] = v

    for c in cards:
        d = c["date"]; venue = c["venue"]; dist = c["distance_m"]
        cnt, allc = trainer_counts_from_runs(load_race_index.runs, d)
        code = race_code(c["source_cname"])
        # 出馬表（Sportnavi）：馬番→馬ID・調教師
        by_no = {}
        if not a.no_fetch:
            soup = get(PAGES["denma"].format(code=code))
            if soup is not None:
                tb = dump_page(soup, "")["tables"]
                for t in tb:
                    if t and t[0] and "馬番" in t[0]:
                        for row in t[1:]:
                            try: no = int(row[1])
                            except Exception: continue
                            hid = (re.search(r"horse/(\d+)/", row[2]) or [None, None])[1]
                            trm = re.search(r"trainer/(\d+)/", row[4]); trn = re.sub(r"[⟨].*", "", row[4]).strip()
                            by_no[no] = {"hid": hid, "trainer_id": trm.group(1) if trm else None, "trainer": re.sub(r"\s*\(.*\)$", "", trn)}
        out = []
        for h in c["horses"]:
            info = by_no.get(h["number"], {}); hid = info.get("hid")
            if not hid:    # 出馬表が取れないとき：馬名で非公開データと照合（同名は年齢が近い馬）
                ids = byname.get(h["name"]) or []
                if ids:
                    hid = sorted(ids, key=lambda i: abs((D.fromisoformat(d).year - int((hs[i].get("birth") or "2000")[:4])) - (h.get("age") or 0)))[0]
                    pr = hs[hid].get("profile") or {}
                    info = {"hid": hid, "trainer_id": pr.get("調教師（所属）_id"), "trainer": re.sub(r"\s*\(.*\)$", "", pr.get("調教師（所属）") or "")}
            hist = None; note = []
            if hid and not a.no_fetch:
                soup = get(HORSE.format(hid=hid))
                if soup is not None:
                    try: hist = parse_horse(soup).get("history") or []
                    except Exception as e: note.append(f"馬のページを読めない: {e}")
            if hist is None and hid and hid in hs: hist = hs[hid].get("history") or []; note.append("最新の履歴が取れず、非公開データの履歴を使用")
            if hist is None: note.append("履歴が取れない（中立の倍率1.0）")
            if hist:
                for r in sorted([r for r in hist if r.get("date") and r["date"] < d], key=lambda r: r["date"])[-LOOKBACK:]:
                    if r.get("code"): l3_for(r["code"])
            tf = trainer_factor(cnt, allc, info.get("trainer_id")) if info.get("trainer_id") else {"t1": None, "mult": 1.0}
            kf = kick_factor(hist, d, l3map) if hist else {"k2": None, "runs_used": 0, "recent": [], "mult": 1.0}
            df = dist_factor(hist, d, dist) if hist else {"apt": None, "mult": 1.0}
            tot = tf["mult"] * kf["mult"] * df["mult"]
            ref = "・".join(f'{u["rank"]}位/{u["field"]}頭({u["last3f"]})' for u in kf["recent"]) or "直近の上がり順位が不明"
            out.append({"no": h["number"], "name": h["name"], "horse_id": hid, "trainer": info.get("trainer"), "trainer_id": info.get("trainer_id"),
                        "trainer_factor": tf, "kick_factor": {k: v for k, v in kf.items()}, "dist_factor": df,
                        "mult_trainer": tf["mult"], "mult_kick": kf["mult"], "mult_dist": df["mult"], "mult_total": round(tot, 3),
                        "kick_reference": "上がり3F順位（新しい順）：" + ref, "notes": note})
        res = {"schema": "step1_factors_v1", "date": d, "venue": venue, "race_name": c.get("race_name"), "race_no": c.get("race_no"),
               "distance_m": dist, "coef_version": "step1_factor_coef.json", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00", time.gmtime(time.time() + 9 * 3600)),
               "usage": "勝率に mult_total を掛けて全頭の合計を1に直す。kick_reference は各馬の reason に必ず書く", "horses": out}
        p = Path(a.out_dir) / f"{d}_{venue}.json"
        p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print("saved", p, "馬", len(out), "調教師あり", sum(1 for x in out if x["trainer_id"]), "上がり順位あり", sum(1 for x in out if x["kick_factor"]["runs_used"]), file=sys.stderr)


if __name__ == "__main__":
    main()
