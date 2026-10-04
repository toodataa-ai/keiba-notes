from jra_observations import parse_pdf_text


MODERN = """
2026年 1回東京競馬
1月30日 金曜日 D 09:00 9.5 08:30 14.0 11.4 1.6 1.3
第 1日 1月31日 土曜日 D 07:00 9.6 05:00 14.1 12.3 1.2 1.7
第 2日 2月1日 日曜日 D 07:00 9.5 05:00 13.9 12.4 1.4 1.6
"""


LEGACY = """
2018年10月5日から10月8日の含水率
場所 金曜日 土曜日 日曜日 月曜日
芝コース含水率 ゴール前 14.8 16.9 16.5 13.7
（パーセント） ４コーナー 15.9 17.7 16.2 16.1
ダートコース含水率 ゴール前 4.2 11.5 8.2 5.6
（パーセント） ４コーナー 5.2 12.0 8.1 5.7
"""


def test_modern_parser_keeps_measurement_metadata_and_race_day():
    rows = parse_pdf_text(MODERN, year=2026, track="tokyo", meeting=1)
    assert len(rows) == 3
    friday, saturday, sunday = rows
    assert friday.observed_date == "2026-01-30"
    assert friday.race_day is False
    assert friday.course == "D"
    assert friday.cushion_value == 9.5
    assert friday.moisture_time == "08:30"
    assert friday.turf_goal == 14.0
    assert friday.turf_corner == 11.4
    assert friday.dirt_goal == 1.6
    assert friday.dirt_corner == 1.3
    assert saturday.day_number == 1 and saturday.race_day is True
    assert sunday.day_number == 2 and sunday.race_day is True
    assert all(r.source_format == "modern" for r in rows)


def test_legacy_parser_maps_header_weekdays_to_dates_and_values():
    rows = parse_pdf_text(LEGACY, year=2018, track="tokyo", meeting=4)
    assert [r.observed_date for r in rows] == [
        "2018-10-05", "2018-10-06", "2018-10-07", "2018-10-08"
    ]
    assert [r.weekday for r in rows] == ["金", "土", "日", "月"]
    assert rows[0].race_day is False
    assert all(r.race_day for r in rows[1:])
    assert rows[0].race_day_inferred is True
    assert [r.turf_goal for r in rows] == [14.8, 16.9, 16.5, 13.7]
    assert [r.turf_corner for r in rows] == [15.9, 17.7, 16.2, 16.1]
    assert [r.dirt_goal for r in rows] == [4.2, 11.5, 8.2, 5.6]
    assert [r.dirt_corner for r in rows] == [5.2, 12.0, 8.1, 5.7]
    assert all(r.cushion_value is None for r in rows)
    assert all(r.source_format == "legacy" for r in rows)


def test_legacy_cross_month_range_is_supported():
    text = """
    2018年9月28日から10月1日の含水率
    場所 金曜日 土曜日 日曜日 月曜日
    芝コース含水率 ゴール前 11.0 12.0 13.0 14.0
    （パーセント） ４コーナー 11.5 12.5 13.5 14.5
    ダートコース含水率 ゴール前 4.0 5.0 6.0 7.0
    （パーセント） ４コーナー 4.5 5.5 6.5 7.5
    """
    rows = parse_pdf_text(text, year=2018, track="tokyo", meeting=4)
    assert [r.observed_date for r in rows] == [
        "2018-09-28", "2018-09-29", "2018-09-30", "2018-10-01"
    ]
