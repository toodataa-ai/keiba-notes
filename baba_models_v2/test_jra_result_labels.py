from pathlib import Path

from jra_result_labels import parse_srl_cname, parse_sde_cname, parse_result_page


def test_parse_meeting_day_and_race_cnames():
    day = parse_srl_cname("pw01srl10082025040220251109/04")
    assert day == {
        "track_code": "08", "year": 2025, "meeting": 4,
        "day_number": 2, "race_date": "20251109"
    }
    race = parse_sde_cname("pw01sde1008202504020620251109/9A")
    assert race == {
        "track_code": "08", "year": 2025, "meeting": 4,
        "day_number": 2, "race_number": 6, "race_date": "20251109"
    }


def test_parse_finalized_result_header():
    html = """
    <html><body>
    <h1>レース結果2025年11月9日（日曜）4回京都2日 6レース</h1>
    <p>2025年11月9日（日曜） 4回京都2日 発走時刻：13時01分</p>
    <ul><li>天候雨</li><li>ダート重</li></ul>
    <h2>3歳以上1勝クラス</h2>
    </body></html>
    """.encode("utf-8")
    cname = "pw01sde1008202504020620251109/9A"
    row = parse_result_page(html, track="kyoto", cname=cname)
    assert row is not None
    assert row.race_date == "2025-11-09"
    assert row.start_time == "13:01"
    assert row.surface == "dirt"
    assert row.condition == "重"
    assert row.weather == "雨"
    assert row.race_number == 6


def test_unfinalized_result_is_ignored():
    html = "<html><body>指定されたレースは、成績が確定していません。</body></html>".encode()
    cname = "pw01sde1005202604021220261004/36"
    assert parse_result_page(html, track="tokyo", cname=cname) is None
