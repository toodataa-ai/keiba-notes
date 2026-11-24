import unittest
import jra_going_labels as g

UNIT = '''<div id="race_result" class="mt20"><div class="race_result_unit" id="race_result_%(n)sR"><table><caption><div class="race_header"><div class="left"><div class="date_line"><div class="inner">
<div class="cell date">2026年11月1日（日曜） 4回東京11日</div><div class="cell time"> 発走時刻：<strong>%(t)s</strong> </div>
<div class="cell baba"><ul><li class="weather"><span class="inner"><span class="cap">天候</span><span class="txt">晴</span></span></li><li class="%(cls)s"><span class="inner"><span class="cap">%(surf)s</span><span class="txt">%(go)s</span></span></li></ul></div></div></div>
<div class="race_title"><div class="inner"><div class="txt"><h2><span class="main"><span class="race_name">2歳未勝利</span></span></h2><div class="type"><div class="cell category">2歳</div><div class="cell class">未勝利</div>
<div class="cell course"><span class="cap">コース：</span>1,400<span class="unit">メートル</span><span class="detail">（%(surf)s・左）</span></div></div></div></div></div></div></div></caption></table></div></div>'''


class T(unittest.TestCase):
    def test_parse_results(self):
        html = UNIT % dict(n=1, t='10時00分', cls='turf', surf='芝', go='良') + UNIT % dict(n=2, t='10時35分', cls='durt', surf='ダート', go='稍重')
        meta = {'date': '2026-11-01', 'track': '東京', 'kai': 4, 'nichime': 11, 'cname': 'x'}
        rows = g.parse_results(html, meta)
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]['surface'], rows[0]['going'], rows[0]['weather'], rows[0]['start_time']), ('芝', '良', '晴', '10:00'))
        self.assertEqual((rows[1]['surface'], rows[1]['going'], rows[1]['race_no']), ('ダート', '稍重', 2))
        self.assertEqual(rows[0]['distance_m'], 1400)
        self.assertEqual(rows[0]['course_detail'], '（芝・左）')

    def test_parse_month_and_day(self):
        html = ("doAction('/JRADB/accessS.html','pw01skl10202510/1E') doAction('/JRADB/accessS.html','pw01skl10202512/BA') "
                "doAction('/JRADB/accessS.html','pw01srl10052025041120251102/98') doAction('/JRADB/accessS.html','pw01srl10052025041120251102/98') "
                "doAction('/JRADB/accessS.html','pw01srl10082025031120251102/45')")
        months, days = g.parse_month(html)
        self.assertEqual(set(months), {'202510', '202512'})
        self.assertEqual(len(days), 2)
        self.assertEqual((days[0]['track'], days[0]['date'], days[0]['kai'], days[0]['nichime']), ('東京', '2025-11-02', 4, 11))
        self.assertEqual(days[1]['track'], '京都')
        self.assertEqual(g.parse_day("x 'pw01ses10052026041120261101/EB' y"), 'pw01ses10052026041120261101/EB')
        self.assertIsNone(g.parse_day('nothing'))


if __name__ == '__main__':
    unittest.main()


class TestUpdate(unittest.TestCase):
    def test_update_appends_only_new_days(self):
        import tempfile, os, json, csv
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'jra_going_2026.csv'), 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=g.FIELDS); w.writeheader()
            w.writerow({k: '' for k in g.FIELDS} | {'date': '2026-11-01', 'track': '東京', 'race_no': '1'})
        days = [{'cname': 'old', 'date': '2026-11-01', 'track': '東京', 'track_code': '05', 'kai': 4, 'nichime': 11},
                {'cname': 'new', 'date': '2026-11-07', 'track': '東京', 'track_code': '05', 'kai': 5, 'nichime': 1},
                {'cname': 'fut', 'date': '2026-11-30', 'track': '中山', 'track_code': '06', 'kai': 5, 'nichime': 1}]
        def fake_index(ia):
            json.dump({'days': days}, open(ia.out, 'w'))
        class FakeClient:
            n = 0
            def __init__(self, delay): pass
            def post(self, c): return c
        orig = (g.cmd_index, g.Client, g.parse_day, g.parse_results)
        g.cmd_index = fake_index; g.Client = FakeClient
        g.parse_day = lambda html: 'ses-' + html
        g.parse_results = lambda html, meta: [{k: '' for k in g.FIELDS} | {'date': meta['date'], 'track': meta['track'], 'race_no': str(i)} for i in (1, 2)]
        try:
            A = type('A', (), dict(dir=d, work=d, today='2026-11-10', delay=0))
            r = g.cmd_update(A)
            r2 = g.cmd_update(A)
        finally:
            g.cmd_index, g.Client, g.parse_day, g.parse_results = orig
        self.assertEqual(r['new_races'], 2)          # 11/7 だけ（既にある日と未来の日は足さない）
        rows = list(csv.DictReader(open(os.path.join(d, 'jra_going_2026.csv'), encoding='utf-8')))
        self.assertEqual([x['date'] for x in rows], ['2026-11-01', '2026-11-07', '2026-11-07'])
        self.assertEqual(json.load(open(os.path.join(d, 'jra_going_2026.summary.json')))['races'], 3)
        self.assertEqual(r2['new_races'], 0)   # 2回目は何も足さない
