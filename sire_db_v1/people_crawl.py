#!/usr/bin/env python3
"""騎手・調教師のページを、見えるものは全部そのまま保存する（研究用・予想には使わない）。
対象＝race_pages に出てくる騎手・調教師のID（/keiba/directory/jockey|trainer/<id>/）。
保存先は非公開リポジトリ（環境変数 SIRE_DATA_DIR）：data_v2/people/jockey.jsonl・trainer.jsonl（1人1行）、
取れた一覧 data_v2/people_done.txt（途中で止まっても続きから）。race_crawl.py と同じ作り（表と文字を全部）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sire_db_v1.race_crawl import GAP, UA, dump_page  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ["SIRE_DATA_DIR"]) if os.environ.get("SIRE_DATA_DIR") else ROOT / "sire_db_v1" / "data"
URL = "https://sports.yahoo.co.jp/keiba/directory/{kind}/{pid}/"
KINDS = ("jockey", "trainer")


def people_ids(data: Path) -> dict[str, list[str]]:
    """保存済みのレースのページに出てくる騎手・調教師のIDを集める"""
    out = {k: set() for k in KINDS}
    for p in sorted((data / "race_pages").glob("*.jsonl")):
        s = p.read_text(encoding="utf-8")
        for k in KINDS:
            out[k] |= set(re.findall(rf"/keiba/directory/{k}/(\d+)", s))
    return {k: sorted(v) for k, v in out.items()}


def main():
    import requests
    from bs4 import BeautifulSoup
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=100)
    ap.add_argument("--probe", default="", help="例 jockey/01171：取って構造を表示するだけ（保存しない）")
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
        kind, pid = a.probe.split("/")
        soup = get(URL.format(kind=kind, pid=pid))
        if soup is None:
            print("not found"); return
        p = dump_page(soup, URL.format(kind=kind, pid=pid))
        print("title:", p["title"], "| text chars:", len(p["text"]), "| tables:", len(p["tables"]))
        for i, t in enumerate(p["tables"]):
            print(f"  table {i}: rows={len(t)} head={t[0][:8]}")
        print("text head:", p["text"][:500])
        return

    (DATA / "people").mkdir(parents=True, exist_ok=True)
    done_p = DATA / "people_done.txt"
    done = set(done_p.read_text().split()) if done_p.exists() else set()
    ids = people_ids(DATA)
    todo = [(k, i) for k in KINDS for i in ids[k] if f"{k}/{i}" not in done]
    print("people todo:", len(todo), {k: len(v) for k, v in ids.items()})
    t0 = time.time(); n = 0
    for k, pid in todo:
        if (time.time() - t0) / 60 > a.max_minutes:
            break
        u = URL.format(kind=k, pid=pid)
        soup = get(u)
        if soup is None:
            continue                            # 取れなかった人は done にしない（次回また試す）
        rec = {"id": pid, "kind": k, "fetched": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
               "parse_v": 1, "page": dump_page(soup, u)}
        with (DATA / "people" / f"{k}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        with done_p.open("a") as f:
            f.write(f"{k}/{pid}\n")
        n += 1
    print(f"done: people +{n}, remaining {len(todo) - n}")


if __name__ == "__main__":
    main()
