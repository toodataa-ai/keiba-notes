"""Capture currently displayed JRA track moisture before the day's racing.

This collector is intentionally NOT a backfill, a production predictor, or
proof that its source's measurement was taken at retrieval time. It records
HTTP retrieval and page dates separately. A previous-day page fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

JST = ZoneInfo("Asia/Tokyo")
SOURCES = {
    "tokyo": "https://www.jra.go.jp/keiba/baba/",
    "kyoto": "https://www.jra.go.jp/keiba/baba/index2.html",
}
JA_NAME = {"tokyo": "東京", "kyoto": "京都"}


def parse_official(html: str, track: str, *, expected_date: str, retrieved_at_jst: str,
                   source_url: str) -> dict:
    if track not in SOURCES or source_url != SOURCES[track]:
        raise ValueError("unapproved official live page")
    fetched_at = datetime.fromisoformat(retrieved_at_jst)
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise ValueError("retrieval timestamp must include JST offset")
    fetched_at = fetched_at.astimezone(JST)
    if fetched_at.date().isoformat() != expected_date:
        raise ValueError("requested day differs from capture day")
    if not html or len(html) < 50:
        raise ValueError("empty / implausible source page")

    text = unicodedata.normalize("NFKC", BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    text = re.sub(r"\s+", " ", text)
    # JRA live heading includes the exact measured calendar date:
    # 第4回東京競馬第10日前日(2026年10月30日(金曜))
    heading = re.search(
        rf"第\d+回\s*{JA_NAME[track]}競馬.{{0,80}}?"
        rf"\(?\s*(20\d\d)年\s*(\d{{1,2}})月\s*(\d{{1,2}})日",
        text,
    )
    if not heading:
        raise ValueError("cannot verify official track/date heading")
    source_date = f"{int(heading[1]):04d}-{int(heading[2]):02d}-{int(heading[3]):02d}"
    if source_date != expected_date:
        raise ValueError(f"stale JRA page: page={source_date} expected={expected_date}")
    # Only extract the four numeric moisture readings from the dedicated
    # two-location moisture table, never from the state/threshold table.
    match = re.search(r"ゴール前と4コーナーの含水率(.{0,250}?)含水率表", text)
    if not match:
        raise ValueError("JRA moisture table cannot be isolated")
    table = match.group(1)
    # Table: ゴール前 4コーナー 芝 x.y x.y ダート x.y x.y
    num = r"(\d{1,2}(?:\.\d+)?)"
    turf = re.search(rf"芝\s+{num}\s+{num}", table)
    dirt = re.search(rf"ダート\s+{num}\s+{num}", table)
    if not turf or not dirt:
        raise ValueError("JRA measured goal/corner values absent")
    values = {
        "turf_goal": float(turf[1]), "turf_corner": float(turf[2]),
        "dirt_goal": float(dirt[1]), "dirt_corner": float(dirt[2]),
    }
    if any(not (0 <= v <= 50) for v in values.values()):
        raise ValueError("official moisture values out of range")
    return {
        "schema_version": 1, "status": "captured_live_research_only",
        "track": track, "page_date_jst": source_date,
        "retrieved_at_jst": fetched_at.isoformat(timespec="seconds"),
        "source_url": source_url, "source_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "moisture_percent": values,
        "measurement_time_jst": None,
        "not_a_formal_prerace_snapshot": True,
        "note": "The retrieval timestamp is NOT the measurement timestamp; source page must match today.",
    }


def capture(track: str, *, now: datetime | None = None) -> dict:
    if track not in SOURCES:
        raise ValueError("unsupported track")
    if now is None:
        now = datetime.now(JST)
    if now.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    now = now.astimezone(JST)
    response = requests.get(SOURCES[track], timeout=25, headers={
        "User-Agent": "keiba-notes-StageB-research/1.0"
    })
    response.raise_for_status()
    snapshot = parse_official(response.text, track, expected_date=now.date().isoformat(),
                              retrieved_at_jst=now.isoformat(timespec="seconds"), source_url=SOURCES[track])
    snapshot["http_last_modified"] = response.headers.get("Last-Modified")
    snapshot["http_etag"] = response.headers.get("ETag")
    return snapshot


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    now = datetime.now(JST)
    result = {"schema_version": 1, "target_date_jst": now.date().isoformat(),
              "captured_at_jst": now.isoformat(timespec="seconds"),
              "scope": "research_only", "production_routing": False, "tracks": {}, "blockers": {}}
    for track in SOURCES:
        try:
            result["tracks"][track] = capture(track, now=now)
        except (requests.RequestException, ValueError) as exc:
            result["blockers"][track] = f"{type(exc).__name__}: {exc}"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"date": result["target_date_jst"], "captured": list(result["tracks"]),
                      "blockers": result["blockers"]}, ensure_ascii=False))
    # Fail if neither page is current. A stale Friday page is not a valid
    # Saturday snapshot even if the moisture values appear plausible.
    if not result["tracks"]:
        raise SystemExit("No current-day JRA live page verified; snapshot withheld")


if __name__ == "__main__":
    main()
