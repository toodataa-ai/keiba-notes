from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from jra_live_baba_snapshot_v1 import parse_official, SOURCES

JST = ZoneInfo("Asia/Tokyo")


def fixture(track: str, day: str):
    name = "東京" if track == "tokyo" else "京都"
    year, month, d = day.split("-")
    return (f"<html><body><h1>第4回{name}競馬第10日前日"
            f"（{year}年{int(month)}月{int(d)}日（金曜））</h1>"
            "<section>含水率 ゴール前と4コーナーの含水率"
            "ゴール前 4コーナー 芝 17.5 16.9 ダート 7.4 7.9 "
            "含水率表 芝コース 良 稍重 重 不良</section></body></html>")


@pytest.mark.parametrize("track", ["tokyo", "kyoto"])
def test_current_day_live_capture_only(track):
    d = "2026-10-30"
    x = parse_official(fixture(track, d), track, expected_date=d,
                       retrieved_at_jst="2026-10-30T12:03:00+09:00", source_url=SOURCES[track])
    assert x["moisture_percent"]["turf_goal"] == 17.5
    assert x["moisture_percent"]["dirt_corner"] == 7.9
    assert x["page_date_jst"] == d
    assert x["measurement_time_jst"] is None
    assert x["not_a_formal_prerace_snapshot"] is True
    assert len(x["source_sha256"]) == 64


def test_stale_friday_page_is_rejected_saturday():
    with pytest.raises(ValueError, match="stale JRA page"):
        parse_official(fixture("tokyo", "2026-10-30"), "tokyo",
                       expected_date="2026-10-31",
                       retrieved_at_jst="2026-10-31T08:20:00+09:00", source_url=SOURCES["tokyo"])


def test_untrusted_url_or_mismatched_date_rejected():
    with pytest.raises(ValueError):
        parse_official(fixture("kyoto", "2026-10-30"), "kyoto",
                       expected_date="2026-10-30",
                       retrieved_at_jst="2026-10-30T08:00:00+09:00", source_url="https://evil.test")
    with pytest.raises(ValueError):
        parse_official(fixture("kyoto", "2026-10-30"), "kyoto",
                       expected_date="2026-10-31",
                       retrieved_at_jst="2026-10-30T08:00:00+09:00", source_url=SOURCES["kyoto"])


def test_no_implicit_measurement_from_missing_table():
    html = fixture("tokyo", "2026-10-30").replace("芝 17.5 16.9 ダート 7.4 7.9", "芝 良 ダート 稍重")
    with pytest.raises(ValueError, match="values absent"):
        parse_official(html, "tokyo", expected_date="2026-10-30",
                       retrieved_at_jst="2026-10-30T08:10:00+09:00", source_url=SOURCES["tokyo"])
