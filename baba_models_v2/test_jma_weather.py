from datetime import date

from jma_weather import parse_hourly_html, station_url


HTML = """
<html><body><table id="tablefix1">
<tr><th>時</th><th>降水</th><th>気温</th><th>露点</th><th>蒸気圧</th><th>湿度</th><th>風速</th><th>風向</th><th>日照</th><th>降雪</th><th>積雪</th></tr>
<tr><td>1</td><td>0.0</td><td>24.0</td><td>20.7</td><td>24.5</td><td>82</td><td>1.7</td><td>南</td><td></td><td>///</td><td>///</td></tr>
<tr><td>2</td><td>1.5 )</td><td>23.3</td><td>21.0</td><td>24.9</td><td>87</td><td>1.5</td><td>南南東</td><td>0.0</td><td>///</td><td>///</td></tr>
<tr><td>3</td><td>///</td><td>///</td><td>///</td><td>///</td><td>///</td><td>///</td><td>///</td><td>///</td><td>///</td><td>///</td></tr>
<tr><td>24</td><td>0.5</td><td>20.0</td><td>18.0</td><td>20.0</td><td>90</td><td>0.8</td><td>北</td><td></td><td>///</td><td>///</td></tr>
</table></body></html>
"""


def test_parse_hourly_a1_rows_and_missing_values():
    rows = parse_hourly_html(HTML, station="fuchu", d=date(2026, 7, 11))
    assert len(rows) == 4
    assert rows[0].precipitation_mm == 0.0
    assert rows[0].temperature_c == 24.0
    assert rows[0].humidity_pct == 82.0
    assert rows[0].wind_mps == 1.7
    assert rows[0].sunshine_hours is None
    assert rows[1].precipitation_mm == 1.5
    assert rows[1].sunshine_hours == 0.0
    assert rows[2].precipitation_mm is None
    assert rows[2].temperature_c is None
    assert rows[-1].end_at == "2026-07-12T00:00"


def test_station_urls_pin_official_jma_ids():
    fuchu = station_url("fuchu", date(2026, 5, 1))
    assert "prec_no=44" in fuchu and "block_no=1133" in fuchu
    nagaoka = station_url("nagaokakyo", date(2026, 5, 1))
    assert "prec_no=61" in nagaoka and "block_no=1025" in nagaoka
    tanabe = station_url("kyotanabe", date(2026, 5, 1))
    assert "prec_no=61" in tanabe and "block_no=0598" in tanabe
