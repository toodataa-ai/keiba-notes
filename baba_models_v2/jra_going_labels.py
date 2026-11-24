"""JRA official race-result pages -> per-race going labels (research only).

Walks the public "past race results" pages the way the site does (POST a cname):
  month page (lists every meeting day) -> day page (race list) -> day result page
  (one page with every race's start time, weather, surface going and course).
Low request rate (default 2.5 s), robots.txt of www.jra.go.jp allows everything.
Only fields shown on the page are copied. Nothing is guessed.
"""
import argparse, csv, json, re, sys, time
import requests
from bs4 import BeautifulSoup

BASE = 'https://www.jra.go.jp'
PATH = '/JRADB/accessS.html'
UA = 'keiba-notes track-condition research/1.0 (low rate, research only)'
TRACKS = {'01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京',
          '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉'}
SEED_MONTH = ('202511', 'pw01skl10202511/EC')
DAY_RE = re.compile(r"pw01srl10(\d{2})(\d{4})(\d{2})(\d{2})(\d{8})/[0-9A-F]{2}")
MONTH_RE = re.compile(r"pw01skl10(\d{6})/[0-9A-F]{2}")
SES_RE = re.compile(r"pw01ses\d+/[0-9A-F]{2}")
FIELDS = ['date', 'track', 'kai', 'nichime', 'race_no', 'start_time', 'surface', 'going',
          'weather', 'distance_m', 'course_detail', 'race_name', 'class', 'category', 'source_cname']


class Client:
    def __init__(self, delay=2.5):
        self.s = requests.Session()
        self.s.headers['User-Agent'] = UA
        self.delay = delay
        self.n = 0

    def post(self, cname):
        last = None
        for attempt in range(3):
            time.sleep(self.delay * (attempt + 1))
            try:
                r = self.s.post(BASE + PATH, data={'cname': cname}, timeout=60)
                self.n += 1
                if r.status_code == 200 and len(r.text) > 20000:
                    r.encoding = r.apparent_encoding
                    return r.text
                last = 'HTTP %s len %s' % (r.status_code, len(r.text))
            except requests.RequestException as e:
                last = repr(e)
        raise RuntimeError('fetch failed %s: %s' % (cname, last))


def parse_month(html):
    """-> (neighbour months {YYYYMM: cname}, meeting days [dict])."""
    months, days, seen = {}, [], set()
    for m in re.finditer(r"pw01skl10(\d{6})/[0-9A-F]{2}", html):
        months.setdefault(m.group(1), m.group(0))
    for m in DAY_RE.finditer(html):
        if m.group(0) in seen:
            continue
        seen.add(m.group(0))
        code, year, kai, nichi, ymd = m.groups()
        days.append({'cname': m.group(0), 'track_code': code, 'track': TRACKS[code],
                     'kai': int(kai), 'nichime': int(nichi),
                     'date': '%s-%s-%s' % (ymd[:4], ymd[4:6], ymd[6:])})
    return months, days


def parse_day(html):
    m = SES_RE.search(html)
    return m.group(0) if m else None


def _txt(node):
    return node.get_text(' ', strip=True) if node else ''


def parse_results(html, meta):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for unit in soup.select('div.race_result_unit'):
        mid = re.search(r'race_result_(\d+)R', unit.get('id', ''))
        if not mid:
            continue
        weather = _txt(unit.select_one('li.weather .txt'))
        surface = going = ''
        for li in unit.select('div.cell.baba li'):
            if 'weather' in (li.get('class') or []):
                continue
            surface, going = _txt(li.select_one('.cap')), _txt(li.select_one('.txt'))
        t = re.search(r'(\d+)時(\d+)分', _txt(unit.select_one('div.cell.time')))
        course = unit.select_one('div.cell.course')
        dist = re.search(r'([\d,]+)\s*メートル', _txt(course))
        rows.append({
            'date': meta['date'], 'track': meta['track'], 'kai': meta['kai'], 'nichime': meta['nichime'],
            'race_no': int(mid.group(1)),
            'start_time': '%02d:%02d' % (int(t.group(1)), int(t.group(2))) if t else '',
            'surface': surface, 'going': going, 'weather': weather,
            'distance_m': int(dist.group(1).replace(',', '')) if dist else '',
            'course_detail': _txt(course.select_one('.detail')) if course else '',
            'race_name': _txt(unit.select_one('.race_name')),
            'class': _txt(unit.select_one('div.cell.class')),
            'category': _txt(unit.select_one('div.cell.category')),
            'source_cname': meta['cname'],
        })
    return rows


def cmd_index(a):
    cl = Client(a.delay)
    lo, hi = a.start, a.end
    known = {SEED_MONTH[0]: SEED_MONTH[1]}
    done, days = {}, {}
    def step(ym):
        html = cl.post(known[ym])
        months, ds = parse_month(html)
        for k, v in months.items():
            known.setdefault(k, v)
        done[ym] = len(ds)
        for d in ds:
            days[d['cname']] = d
    def prev(ym):
        y, m = int(ym[:4]), int(ym[4:])
        return '%04d%02d' % ((y - 1, 12) if m == 1 else (y, m - 1))
    def nxt(ym):
        y, m = int(ym[:4]), int(ym[4:])
        return '%04d%02d' % ((y + 1, 1) if m == 12 else (y, m + 1))
    step(SEED_MONTH[0])
    ym = SEED_MONTH[0]
    while prev(ym) >= lo and prev(ym) in known:
        ym = prev(ym); step(ym)
    ym = SEED_MONTH[0]
    while nxt(ym) <= hi and nxt(ym) in known:
        ym = nxt(ym); step(ym)
    out = {'months': done, 'days': sorted(days.values(), key=lambda d: (d['date'], d['track_code']))}
    missing = [m for m in sorted(known) if lo <= m <= hi and m not in done]
    out['unreached_months'] = missing
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('months', len(done), 'days', len(out['days']), 'requests', cl.n, 'unreached', missing)


def cmd_collect(a):
    days = [d for d in json.load(open(a.days, encoding='utf-8'))['days'] if d['date'].startswith(a.year)]
    cl = Client(a.delay)
    rows, failed = [], []
    for d in days:
        try:
            ses = parse_day(cl.post(d['cname']))
            if not ses:
                raise RuntimeError('no result-list link on day page')
            got = parse_results(cl.post(ses), d)
            if not got:
                raise RuntimeError('no races parsed')
            rows.extend(got)
        except Exception as e:
            failed.append({'date': d['date'], 'track': d['track'], 'error': str(e)[:200]})
    with open(a.out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    json.dump({'year': a.year, 'days': len(days), 'races': len(rows), 'failed': failed},
              open(a.out + '.summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('year', a.year, 'days', len(days), 'races', len(rows), 'failed', len(failed), 'requests', cl.n)


def last_known_date(dirpath):
    """既存の年ごとのCSVのうち一番新しい日付（無ければ空）"""
    import os
    best = ''
    for fn in os.listdir(dirpath):
        m = re.fullmatch(r'jra_going_(\d{4})\.csv', fn)
        if not m:
            continue
        with open(os.path.join(dirpath, fn), encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r['date'] > best:
                    best = r['date']
    return best


def cmd_update(a):
    """前回の続きから、まだ載っていない開催日（今日より前）だけを取り、年ごとのCSVの末尾に足す。
    取れなかった日は足さない（次回また試す）。既にある日は足さない。"""
    import os, datetime
    today = a.today or (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime('%Y-%m-%d')
    last = last_known_date(a.dir)
    lo = (last[:7] if last else '2018-01').replace('-', '')
    hi = today[:7].replace('-', '')
    idx = os.path.join(a.work, 'days_update.json')
    class A: pass
    ia = A(); ia.start, ia.end, ia.out, ia.delay = lo, hi, idx, a.delay
    cmd_index(ia)
    days = json.load(open(idx, encoding='utf-8'))['days']
    have = set()
    for fn in os.listdir(a.dir):
        if re.fullmatch(r'jra_going_\d{4}\.csv', fn):
            with open(os.path.join(a.dir, fn), encoding='utf-8') as f:
                have |= {(r['date'], r['track']) for r in csv.DictReader(f)}
    print('index: days', len(days), 'latest', [(d['date'], d['track']) for d in days[-6:]], 'by month', {m: n for m, n in json.load(open(idx, encoding='utf-8')).get('months', {}).items()})
    todo = [d for d in days if d['date'] < today and (d['date'], d['track']) not in have]
    cl = Client(a.delay)
    added, failed = {}, []
    for d in todo:
        try:
            ses = parse_day(cl.post(d['cname']))
            if not ses:
                raise RuntimeError('no result-list link on day page')
            got = parse_results(cl.post(ses), d)
            if not got:
                raise RuntimeError('no races parsed')
            added.setdefault(d['date'][:4], []).extend(got)
        except Exception as e:
            failed.append({'date': d['date'], 'track': d['track'], 'error': str(e)[:200]})
    for y, rows in added.items():
        p = os.path.join(a.dir, 'jra_going_%s.csv' % y)
        new_file = not os.path.exists(p)
        with open(p, 'a', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new_file:
                w.writeheader()
            w.writerows(rows)
        with open(p, encoding='utf-8') as f:
            all_rows = list(csv.DictReader(f))
        json.dump({'year': y, 'days': len({(r['date'], r['track']) for r in all_rows}), 'races': len(all_rows), 'failed': []},
                  open(p.replace('.csv', '.summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = sum(len(v) for v in added.values())
    print('update: last', last, 'today', today, 'new days', len(todo) - len(failed), 'new races', n, 'failed', len(failed), failed)
    return {'new_races': n, 'failed': failed}


def cmd_probe(a):
    cl = Client(a.delay)
    if a.cname == 'LAST':          # 種の月から次の月へたどれるところまで行き、最後の月のページの中身を見る
        known = {SEED_MONTH[0]: SEED_MONTH[1]}; ym = SEED_MONTH[0]; html = ''
        while True:
            html = cl.post(known[ym])
            months, _ = parse_month(html)
            for k, v in months.items():
                known.setdefault(k, v)
            nx = '%04d%02d' % ((int(ym[:4]) + 1, 1) if ym[4:] == '12' else (int(ym[:4]), int(ym[4:]) + 1))
            if nx not in known:
                break
            ym = nx
        print('last reachable month', ym, 'known months', sorted(known))
        a.cname = known[ym]
    else:
        html = cl.post(a.cname)
    names = sorted(set(re.findall(r"accessS\.html['\"]\s*,\s*['\"]([^'\"]+)['\"]", html)))
    print('cname', a.cname, 'len', len(html), 'links', len(names))
    byp = {}
    for n in names:
        byp.setdefault(re.sub(r'\d', '#', n.split('/')[0]), []).append(n)
    for k, v in byp.items():
        print(k, len(v), v[:3], v[-2:])
    for m in re.finditer(r'(次|翌|前)の?月[^<]{0,40}', html):
        print('NAV', m.group(0)[:60])


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    i = sub.add_parser('index'); i.add_argument('--start', default='201801'); i.add_argument('--end', default='202611')
    i.add_argument('--out', required=True); i.add_argument('--delay', type=float, default=2.5)
    c = sub.add_parser('collect'); c.add_argument('--days', required=True); c.add_argument('--year', required=True)
    c.add_argument('--out', required=True); c.add_argument('--delay', type=float, default=2.5)
    u = sub.add_parser('update'); u.add_argument('--dir', required=True); u.add_argument('--work', default='/tmp')
    u.add_argument('--today', default=''); u.add_argument('--delay', type=float, default=2.5)
    pr = sub.add_parser('probe'); pr.add_argument('--cname', required=True); pr.add_argument('--delay', type=float, default=2.5)
    a = p.parse_args(argv)
    {'probe': cmd_probe, 'index': cmd_index, 'collect': cmd_collect, 'update': cmd_update}[a.cmd](a)


if __name__ == '__main__':
    main()
