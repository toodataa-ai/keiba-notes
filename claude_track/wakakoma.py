#!/usr/bin/env python3
"""若駒（経験の少ない馬）の機械採点。全レース（1R〜12R）・GitHub だけで動く・Claude の使用量は 0。

予想は使わない。公開されている最終の単勝オッズから「勝つ確率」を機械的に出し（確率 = (1/オッズ) / 全頭の合計）、
出走前の出走数（0戦／1〜3戦／4戦以上）ごとに、実際の勝ちと合っているかを集計する。
出走前の出走数は、各馬のページの出走履歴（JRA・地方・海外）から、そのレース日より前の件数を数える。
データ: claude_track/wakakoma/<日付>/<race_id>.json（追加のみ・上書きなし）
集計  : docs/data/predictors/claude_wakakoma_v1.json
"""
from __future__ import annotations
import argparse, json, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
UA = "keiba-notes claude-track research/1.0 (low rate, research only; contact: github.com/toodataa-ai/keiba-notes)"
DENMA_URL = "https://sports.yahoo.co.jp/keiba/race/denma/{code}"
HORSE_URL = "https://sports.yahoo.co.jp{path}"
CATS = [("E0", "0戦", 0, 0), ("E1", "1〜3戦", 1, 3), ("E2", "4戦以上", 4, 10**6)]
CONFIRM_HORSES = 30


def _text(x) -> str:
    return re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()


def category(starts: int) -> str:
    for cid, _label, lo, hi in CATS:
        if lo <= starts <= hi:
            return cid
    return "E2"


def parse_denma(soup) -> dict:
    """-> {title, horses:[{no, name, horse_path, odds, ninki}]}; raises ValueError if no entries."""
    horses = []
    for t in soup.select("table"):
        rows = t.select("tr")
        if not rows:
            continue
        head = [_text(c) for c in rows[0].find_all(["th", "td"], recursive=False)]
        if "馬番" not in head or not any(h.startswith("人気") for h in head):
            continue
        ix = {h.split(" ")[0]: i for i, h in enumerate(head)}
        for tr in rows[1:]:
            cells = tr.find_all(["th", "td"], recursive=False)
            if len(cells) < len(head):
                continue
            txt = [_text(c) for c in cells]
            no = txt[ix["馬番"]]
            if not no.isdigit():
                continue
            a = cells[ix["馬名"]].select_one("a[href*='/keiba/directory/horse/']")
            m = re.search(r"(\d+)\s*\(\s*([\d.,]+)\s*\)", txt[[i for i, h in enumerate(head) if h.startswith("人気")][0]])
            horses.append({"no": int(no), "name": txt[ix["馬名"]].split(" ")[0], "horse_path": a.get("href") if a else None,
                           "ninki": int(m.group(1)) if m else None, "odds": float(m.group(2).replace(",", "")) if m else None})
        break
    if not horses:
        raise ValueError("no entries")
    title = _text(soup.title) if soup.title else ""
    return {"title": title, "horses": horses}


def parse_horse_history(soup) -> list[str]:
    """Dates (YYYY-MM-DD) of every past race listed on a horse page (JRA, local, overseas)."""
    out = []
    for t in soup.select("table"):
        rows = t.select("tr")
        if not rows:
            continue
        head = [_text(c) for c in rows[0].find_all(["th", "td"], recursive=False)]
        if head[:2] == ["日付", "レース"] and "着順" in head:
            for tr in rows[1:]:
                c = _text(tr.find(["td", "th"])) if tr.find(["td", "th"]) else ""
                m = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", c)
                if m:
                    out.append("-".join(m.groups()))
            break
    return out


def prior_starts(history_dates: list[str], race_date: str) -> int:
    return sum(1 for d in history_dates if d < race_date)


def implied(horses: list[dict]) -> None:
    inv = {h["no"]: 1.0 / h["odds"] for h in horses if h.get("odds")}
    s = sum(inv.values())
    for h in horses:
        h["p"] = round(inv[h["no"]] / s, 6) if h["no"] in inv and s else None


def race_codes_for_day(card: dict) -> list[tuple[str, str]]:
    from claude_track.fetch_odds import race_code
    base = race_code(card["source_cname"])[:-2]
    return [(f"{card['date']}-{card['venue_code']}-{r:02d}", f"{base}{r:02d}") for r in range(1, 13)]


def aggregate(root: Path) -> dict:
    cats = {cid: {"label": label, "horses": 0, "races": set(), "expected_wins": 0.0, "actual_wins": 0} for cid, label, _a, _b in CATS}
    n_races = 0
    for f in sorted(root.glob("*/*.json")):
        d = json.loads(f.read_text(encoding="utf-8")); n_races += 1
        for h in d["horses"]:
            if h.get("p") is None or h.get("prior_starts") is None:
                continue
            c = cats[category(h["prior_starts"])]
            c["horses"] += 1; c["races"].add(d["race_id"]); c["expected_wins"] += h["p"]; c["actual_wins"] += int(bool(h["win"]))
    out = {}
    for cid, c in cats.items():
        e = c["expected_wins"]
        out[cid] = {"label": c["label"], "horses": c["horses"], "races": len(c["races"]),
                    "expected_wins": round(e, 3), "actual_wins": c["actual_wins"],
                    "ratio_actual_to_expected": round(c["actual_wins"] / e, 3) if e else None,
                    "confirmable": c["horses"] >= CONFIRM_HORSES}
    return {"schema_version": 1, "kind": "wakakoma_market_check", "research_only": True,
            "method": "公開の最終単勝オッズから (1/オッズ)÷全頭の合計 で勝つ確率を機械的に出し、出走前の出走数の区分ごとに実際の勝ちと比べる。予想（LLM）は使わない。",
            "confirm_horses_per_category": CONFIRM_HORSES, "races_scored": n_races, "categories": out}


def main():
    import requests
    from bs4 import BeautifulSoup
    from claude_track.fetch_results import parse_result, RESULT_URL
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append")
    ap.add_argument("--inputs", default=str(ROOT / "claude_track/inputs"))
    ap.add_argument("--out", default=str(ROOT / "claude_track/wakakoma"))
    ap.add_argument("--agg", default=str(ROOT / "docs/data/predictors/claude_wakakoma_v1.json"))
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--probe-code", help="test only: denma code of any past race (first 3 horses' pages), nothing saved")
    ap.add_argument("--probe-date", help="with --probe-code: the race date YYYY-MM-DD")
    ap.add_argument("--aggregate-only", action="store_true")
    a = ap.parse_args()
    s = requests.Session(); s.headers["User-Agent"] = UA
    def get(url):
        time.sleep(a.delay); r = s.get(url, timeout=30); r.raise_for_status(); return BeautifulSoup(r.content, "html.parser")
    if a.probe_code:
        d = parse_denma(get(DENMA_URL.format(code=a.probe_code))); implied(d["horses"])
        for h in d["horses"][:3]:
            hist = parse_horse_history(get(HORSE_URL.format(path=h["horse_path"])))
            h["history_n"] = len(hist); h["prior_starts"] = prior_starts(hist, a.probe_date)
        print(json.dumps({"title": d["title"], "n": len(d["horses"]), "first3": d["horses"][:3]}, ensure_ascii=False)); return
    out = Path(a.out)
    if not a.aggregate_only:
        now = datetime.now(JST)
        dates = a.date or [now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")]
        for d in sorted(Path(a.inputs).glob("*-11")):
            if not any(d.name.startswith(x) for x in dates):
                continue
            files = sorted(d.glob("*.json"))
            if not files:
                continue
            card = json.loads(files[-1].read_text(encoding="utf-8"))
            for rid, code in race_codes_for_day(card):
                dest = out / card["date"] / f"{rid}.json"
                if dest.exists():
                    continue
                try:
                    res = parse_result(get(RESULT_URL.format(code=code)))      # only confirmed results
                    den = parse_denma(get(DENMA_URL.format(code=code)))
                    implied(den["horses"])
                    win_no = res["finish_order"][0]
                    for h in den["horses"]:
                        hist = parse_horse_history(get(HORSE_URL.format(path=h["horse_path"]))) if h["horse_path"] else None
                        h["prior_starts"] = prior_starts(hist, card["date"]) if hist is not None else None
                        h["win"] = h["no"] == win_no
                        h.pop("horse_path", None)
                except Exception as e:
                    print("SKIP", rid, e, file=sys.stderr); continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps({"schema_version": 1, "race_id": rid, "date": card["date"], "title": den["title"],
                                            "captured_at": datetime.now(JST).isoformat(timespec="seconds"), "horses": den["horses"]},
                                           ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print("saved", rid, len(den["horses"]), "horses")
    agg = aggregate(out)
    Path(a.agg).parent.mkdir(parents=True, exist_ok=True)
    agg["generated_at"] = datetime.now(JST).isoformat(timespec="seconds")
    Path(a.agg).write_text(json.dumps(agg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
