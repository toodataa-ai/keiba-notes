from jra_observations import parse_pdf_text


MODERN = """
2026年 1回東京競馬
1月30日 金曜日 D 09:00 9.5 08:30 14.0 11.4 1.6 1.3
第 1日 1月31日 土曜日 D 07:00 9.6 05:00 14.1 12.3 1.2 1.7
第 2日 2月1日 日曜日 D 07:00 9.5 05:00 13.9 12.4 1.4 1.6
"""


GROUPED = """
第１日・第２日（2023年4月21日～23日）
金曜日 土曜日 日曜日
9.3 9.1 9.5
場所 金曜日 土曜日 日曜日
芝コース含水率 ゴール前 10.1 10.0 9.4
（パーセント） ４コーナー 7.9 8.8 8.3
ダートコース含水率 ゴール前 8.3 6.8 3.9
（パーセント） ４コーナー 8.5 6.0 5.4
第３日・第４日（2023年4月28日～30日）
金曜日 土曜日 日曜日
9.2 9.5 8.1
場所 金曜日 土曜日 日曜日
芝コース含水率 ゴール前 10.2 10.8 12.3
（パーセント） ４コーナー 10.8 8.7 11.5
ダートコース含水率 ゴール前 8.3 8.8 16.1
（パーセント） ４コーナー 9.4 8.7 17.1
"""


LEGACY = """
2019年5月31日から6月2日の気象状況
場所 金曜日 土曜日 日曜日
芝コース含水率 ゴール前 12.9 12.0 12.3
（パーセント） ４コーナー 13.0 12.8 12.3
ダートコース含水率 ゴール前 3.0 3.2 2.9
（パーセント） ４コーナー 2.7 3.7 3.9
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


def test_grouped_parser_keeps_cushion_values_and_day_numbers():
    rows = parse_pdf_text(GROUPED, year=2023, track="kyoto", meeting=1)
    assert len(rows) == 6
    assert [r.observed_date for r in rows[:3]] == ["2023-04-21", "2023-04-22", "2023-04-23"]
    assert [r.day_number for r in rows[:3]] == [None, 1, 2]
    assert [r.cushion_value for r in rows[:3]] == [9.3, 9.1, 9.5]
    assert rows[0].race_day is False and rows[1].race_day is True
    assert rows[2].turf_goal == 9.4 and rows[2].dirt_corner == 5.4
    assert [r.day_number for r in rows[3:]] == [None, 3, 4]
    assert all(r.source_format == "grouped" for r in rows)


def test_legacy_weather_status_heading_maps_weekdays_and_values():
    rows = parse_pdf_text(LEGACY, year=2019, track="tokyo", meeting=3)
    assert [r.observed_date for r in rows] == ["2019-05-31", "2019-06-01", "2019-06-02"]
    assert [r.weekday for r in rows] == ["金", "土", "日"]
    assert rows[0].race_day is False
    assert all(r.race_day for r in rows[1:])
    assert rows[0].race_day_inferred is True
    assert [r.turf_goal for r in rows] == [12.9, 12.0, 12.3]
    assert [r.turf_corner for r in rows] == [13.0, 12.8, 12.3]
    assert [r.dirt_goal for r in rows] == [3.0, 3.2, 2.9]
    assert [r.dirt_corner for r in rows] == [2.7, 3.7, 3.9]
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
