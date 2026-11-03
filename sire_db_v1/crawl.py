#!/usr/bin/env python3
"""父×距離×芝ダート×月齢の傾向表のための元データを集める（過去のJRAレース → 出走馬 → 馬のページ）。
GitHub だけで動く・Claude の使用量は 0。予想には使わない（研究のみ）。

流れ: baba_models_v2/going_labels/jra_going_<年>.csv のレースごとに Sportnavi の出馬表から馬のページへ。
保存: sire_db_v1/data/horses_<生まれ年>.jsonl（追加のみ）、処理済みレース sire_db_v1/data/races_done.txt。
途中で止まっても続きから再開できる。
"""
from __future__ import annotations
import argparse, csv, json, os, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 馬ごとの生データは公開リポジトリに置かない：環境変数 SIRE_DATA_DIR（非公開リポジトリの中）に保存する
DATA = Path(os.environ["SIRE_DATA_DIR"]) if os.environ.get("SIRE_DATA_DIR") else ROOT / "sire_db_v1" / "data"
LABELS = ROOT / "baba_models_v2" / "going_labels"
UA = "keiba-notes research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
VENUE = {"札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
         "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10"}
DENMA = "https://sports.yahoo.co.jp/keiba/race/denma/{code}"
HORSE = "https://sports.yahoo.co.jp/keiba/directory/horse/{hid}/"
GAP = 2.0


def _t(x) -> str:
    return re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()


def race_codes(years) -> list[tuple[str, str]]:
    """[(date, code)] 新しい順。code = 年2桁+競馬場+回+日目+R。"""
    out = []
    for y in years:
        p = LABELS / f"jra_going_{y}.csv"
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(encoding="utf-8")):
            v = VENUE.get(r["track"])
            if not v:
                continue
            out.append((r["date"], f"{r['date'][2:4]}{v}{int(r['kai']):02d}{int(r['nichime']):02d}{int(r['race_no']):02d}"))
    out.sort(reverse=True)
    return out


def parse_denma_horses(soup) -> list[str]:
    """出走表の馬だけ（ページには各馬の父などの血統リンクも載るので、表の行の馬名セルだけを見る）。"""
    ids = []
    for t in soup.select("table"):
        rows = t.select("tr")
        if not rows:
            continue
        head = [_t(c) for c in rows[0].find_all(["th", "td"], recursive=False)]
        if "馬番" not in head:
            continue
        ix = next((i for i, h in enumerate(head) if h.startswith("馬名")), None)
        for tr in rows[1:]:
            cells = tr.find_all(["th", "td"], recursive=False)
            if ix is None or len(cells) <= ix:
                continue
            a = cells[ix].find("a", href=re.compile(r"^/keiba/directory/horse/\d+/$"))
            if a:
                hid = re.search(r"(\d+)/$", a["href"]).group(1)
                if hid not in ids:
                    ids.append(hid)
        break
    return ids


def _gen(soup, name):
    out = []
    for d in soup.find_all("div", class_=True):
        cls = d.get("class")
        if f"hr-horsePedigree__gen{name}" in cls and any(c.endswith("--sire") or c.endswith("--dam") for c in cls):
            out.append(_t(d))
    return out


def parse_horse(soup) -> dict:
    """-> {name, sex, age_text, birth, ped:{sire,dam,damsire,...}, history:[...]}"""
    name = ""
    tm = re.match(r"競馬 - (.+?) データベース", _t(soup.title)) if soup.title else None
    if tm:
        name = tm.group(1)
    txt = _t(soup)
    m = re.search(r"性齢 (牡|牝|セ)", txt)
    sex = m.group(1) if m else None
    m = re.search(r"生年月日 (\d{4})年(\d{1,2})月(\d{1,2})日", txt)
    birth = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    g1, g2, g3 = _gen(soup, "1st"), _gen(soup, "Second"), _gen(soup, "Third")
    ped = {"sire": g1[0] if len(g1) > 0 else None, "dam": g1[1] if len(g1) > 1 else None,
           "sire_sire": g2[0] if len(g2) > 0 else None, "sire_dam": g2[1] if len(g2) > 1 else None,
           "dam_sire": g2[2] if len(g2) > 2 else None, "dam_dam": g2[3] if len(g2) > 3 else None,
           "gen3": g3}
    prof = {}
    for it in soup.select(".hr-profile__item"):
        dt, dd = it.find("dt"), it.find("dd")
        if dt and dd:
            prof[_t(dt)] = _t(dd)
            a_ = dd.find("a", href=True)
            if a_:
                mm = re.search(r"/directory/(trainer|jockey)/(\d+)/", a_["href"])
                if mm:
                    prof[_t(dt) + "_id"] = mm.group(2)
    mp = re.search(r"本賞金 付加賞金 収得賞金 (.+?) 連対時の馬体重", txt)
    prize = mp.group(1) if mp else None
    ms = re.search(r"総合成績 (.+?) 出走レース", txt)
    totals_text = ms.group(1)[:600] if ms else None
    hist = []
    for t in soup.select("table"):
        rows = t.select("tr")
        if not rows:
            continue
        head = [_t(c) for c in rows[0].find_all(["th", "td"], recursive=False)]
        if head[:2] != ["日付", "レース"]:
            continue
        for tr in rows[1:]:
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 6:
                continue
            dm = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", _t(tds[0]))
            if not dm:
                continue
            a = tds[1].find("a")
            code = None
            if a and a.get("href"):
                cm = re.search(r"/keiba/race/index/(\d+)", a["href"])
                code = cm.group(1) if cm else None
            p = tds[1].find("p")
            loc = _t(p) if p else ""
            lm = re.match(r"(\S+) (芝|ダ|障)\S*?(\d+)m(?: (\d+)頭)?", loc)
            lab = tds[1].find("span", class_=re.compile("hr-label"))
            om = re.match(r"(\d+)\s*\(([\d.]+)\)", _t(tds[5]))
            fin = _t(tds[2])
            jk = tds[4].find("a", href=True) if len(tds) > 4 else None
            jm = re.search(r"/jockey/(\d+)/", jk["href"]) if jk else None
            kg = re.search(r"\(([\d.]+)\)", _t(tds[4])) if len(tds) > 4 else None
            wm = re.match(r"(\d+)\(([+-]?\d+)\)", _t(tds[6])) if len(tds) > 6 else None
            tm = re.match(r"(\d+:\d+\.\d)(?: \(([+-]?[\d.]+)\))?", _t(tds[7])) if len(tds) > 7 else None
            od = re.match(r"(\S+)(?: ([\d.]+))?", _t(tds[8])) if len(tds) > 8 else None
            hist.append({"date": "-".join(dm.groups()), "code": code,
                         "race": _t(a) if a else _t(tds[1]), "grade": _t(lab) if lab else None, "loc": loc,
                         "venue": lm.group(1) if lm else None,
                         "surface": {"芝": "芝", "ダ": "ダート", "障": "障害"}.get(lm.group(2)) if lm else None,
                         "dist": int(lm.group(3)) if lm else None,
                         "heads": int(lm.group(4)) if lm and lm.group(4) else None,
                         "finish": int(fin) if fin.isdigit() else fin,
                         "horse_no": _t(tds[3]) if len(tds) > 3 else None,
                         "jockey": _t(jk) if jk else (_t(tds[4]) if len(tds) > 4 else None),
                         "jockey_id": jm.group(1) if jm else None,
                         "carried": float(kg.group(1)) if kg else None,
                         "ninki": int(om.group(1)) if om else None,
                         "odds": float(om.group(2)) if om else None,
                         "body_weight": int(wm.group(1)) if wm else None,
                         "body_weight_diff": int(wm.group(2)) if wm else None,
                         "time": tm.group(1) if tm else None,
                         "margin": tm.group(2) if tm and tm.group(2) else None,
                         "passing": od.group(1) if od else None,
                         "last3f": float(od.group(2)) if od and od.group(2) else None})
        break
    return {"name": name, "sex": sex, "birth": birth, "profile": prof, "prize_text": prize,
            "totals_text": totals_text, "ped": ped, "history": hist}


def known_ids() -> set[str]:
    s = set()
    for p in DATA.glob("horses_*.jsonl"):
        for line in p.open(encoding="utf-8"):
            try:
                s.add(json.loads(line)["id"])
            except Exception:
                pass
    return s


def main():
    import requests
    from bs4 import BeautifulSoup
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2026,2025,2024,2023,2022")
    ap.add_argument("--max-minutes", type=float, default=300)
    ap.add_argument("--max-races", type=int, default=0)
    ap.add_argument("--probe", default="", help="race code: parse only, print summary, save nothing")
    a = ap.parse_args()
    s = requests.Session(); s.headers["User-Agent"] = UA

    def get(u):
        for i in range(3):
            try:
                r = s.get(u, timeout=30); time.sleep(GAP)
                if r.status_code == 404:
                    return None
                r.raise_for_status(); return BeautifulSoup(r.text, "html.parser")
            except requests.RequestException as e:
                print("retry", u, e, file=sys.stderr); time.sleep(5 * (i + 1))
        return None

    if a.probe:
        ids = parse_denma_horses(get(DENMA.format(code=a.probe)))
        print("horses in race:", len(ids))
        h = parse_horse(get(HORSE.format(hid=ids[0])))
        print(json.dumps({k: h[k] for k in ("name", "sex", "birth", "ped")}, ensure_ascii=False))
        print("history rows:", len(h["history"])); print(h["history"][:2])
        return

    DATA.mkdir(parents=True, exist_ok=True)
    done_p = DATA / "races_done.txt"
    done = set(done_p.read_text().split()) if done_p.exists() else set()
    seen = known_ids()
    t0 = time.time(); nr = nh = 0
    todo = [(d, c) for d, c in race_codes(a.years.split(",")) if c not in done]
    print("races todo:", len(todo), "horses known:", len(seen))
    for d, code in todo:
        if (time.time() - t0) / 60 > a.max_minutes or (a.max_races and nr >= a.max_races):
            break
        soup = get(DENMA.format(code=code))
        if soup is None:
            continue                           # 取れなかったレースは done にしない（次回また試す）
        for hid in parse_denma_horses(soup):
            if hid in seen:
                continue
            hs = get(HORSE.format(hid=hid))
            if hs is None:
                continue
            h = parse_horse(hs)
            if not h["birth"] or not h["ped"]["sire"]:
                print("skip (no birth/sire):", hid); continue
            rec = {"id": hid, **h, "fetched": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")}
            with (DATA / f"horses_{h['birth'][:4]}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seen.add(hid); nh += 1
        with done_p.open("a") as f:
            f.write(code + "\n")
        nr += 1
        if nr % 50 == 0:
            print(f"races {nr} horses +{nh} elapsed {(time.time()-t0)/60:.0f} min", flush=True)
    print(f"done: races +{nr}, horses +{nh}, remaining races {len(todo) - nr}")


if __name__ == "__main__":
    main()
