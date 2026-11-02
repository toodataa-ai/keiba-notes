"""JRA 馬場概要 pages -> turf course letter (A-D) for every meeting day (research only).

Page: https://www.jra.go.jp/keiba/baba/overview/<year>_<kai>[-<kai>]_<track>.html
It has a turf "使用コース" table that maps meeting days (e.g. "第2回東京 前6日") to A/B/C/D.
We expand that to (year, track, kai, nichime) using the meeting lengths seen in the
official result labels (going_labels/*.csv). Anything we cannot read is reported, not guessed.
Low request rate; the pages that do not exist answer 403/404 and are just recorded.
"""
import argparse, csv, glob, json, re, time
from collections import defaultdict
import requests
from bs4 import BeautifulSoup

BASE = 'https://www.jra.go.jp/keiba/baba/overview/'
UA = 'keiba-notes track-condition research/1.0 (low rate, research only)'
ROMAJI = {'札幌': 'sapporo', '函館': 'hakodate', '福島': 'fukushima', '新潟': 'niigata', '東京': 'tokyo',
          '中山': 'nakayama', '中京': 'chukyo', '京都': 'kyoto', '阪神': 'hanshin', '小倉': 'kokura'}
FIELDS = ['year', 'track', 'kai', 'nichime', 'turf_course', 'lap_m', 'straight_m', 'width_m', 'note', 'source_url']
Z2H = str.maketrans('０１２３４５６７８９', '0123456789')


def parse_overview(html, track_ja):
    """-> (rows [{kai, spec, course, lap, straight, width, note}], problems [str])."""
    soup = BeautifulSoup(html, 'html.parser')
    h2 = next((h for h in soup.find_all('h2') if '芝コース' in h.get_text()), None)
    table = h2.find_next('table') if h2 else None
    if table is None:
        return [], ['no turf table']
    rows, problems, last_kai = [], [], None
    for tr in table.select('tbody tr'):
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        course = tds[1].get_text(strip=True)
        if course not in ('A', 'B', 'C', 'D'):
            problems.append('course cell %r' % course); continue
        lines = [x.strip() for x in tds[0].get_text('\n').replace('　', ' ').split('\n') if x.strip()]
        nums = [re.search(r'([\d,.]+)', td.get_text(' ', strip=True)) for td in tds[2:5]]
        lap, stra, wid = [(n.group(1).replace(',', '') if n else '') for n in nums] + [''] * (3 - len(nums))
        note = tds[5].get_text(' ', strip=True) if len(tds) > 5 else ''
        for ln in lines:
            ln = ln.translate(Z2H)
            m = re.match(r'第(\d+)回' + re.escape(track_ja) + r'\s*(.*)$', ln)
            if m:
                last_kai, spec = int(m.group(1)), m.group(2).strip()
            else:
                spec = ln
            rows.append({'kai': last_kai, 'spec': spec, 'course': course, 'lap': lap, 'straight': stra, 'width': wid, 'note': note})
    return rows, problems


def expand(spec, total):
    """spec like '前6日' '後4日' '第7日から第10日' '第11日・第12日' '第3日' '全日' -> list of nichime."""
    s = spec.replace(' ', '')
    m = re.fullmatch(r'前半?(\d+)日', s)
    if m: return list(range(1, int(m.group(1)) + 1))
    m = re.fullmatch(r'後半?(\d+)日', s)
    if m and total: return list(range(total - int(m.group(1)) + 1, total + 1))
    m = re.fullmatch(r'第(\d+)日(?:から|～|〜|-|－)第?(\d+)日', s)
    if m: return list(range(int(m.group(1)), int(m.group(2)) + 1))
    if re.fullmatch(r'第\d+日(?:[・,、]第?\d+日)*', s):
        return [int(x) for x in re.findall(r'(\d+)', s)]
    if s in ('全日', '全開催日') and total: return list(range(1, total + 1))
    return None


def load_meetings(labels_dir):
    """(year, track_ja) -> {kai: total days}"""
    seen = defaultdict(lambda: defaultdict(set))
    for f in sorted(glob.glob(labels_dir + '/jra_going_20*.csv')):
        for r in csv.DictReader(open(f, encoding='utf-8')):
            seen[(r['date'][:4], r['track'])][int(r['kai'])].add(int(r['nichime']))
    return {k: {kai: max(v) for kai, v in d.items()} for k, d in seen.items()}


def candidate_urls(year, track_ja, kais):
    t = ROMAJI[track_ja]
    ks = sorted(kais)
    urls = ['%s%s_%d_%s.html' % (BASE, year, k, t) for k in ks]
    urls += ['%s%s_%d-%d_%s.html' % (BASE, year, a, b, t) for a, b in zip(ks, ks[1:]) if b == a + 1]
    return urls


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--labels-dir', default='going_labels')
    p.add_argument('--out', required=True)
    p.add_argument('--delay', type=float, default=2.0)
    p.add_argument('--years', default='')
    a = p.parse_args(argv)
    meetings = load_meetings(a.labels_dir)
    want = set(a.years.split(',')) if a.years else None
    s = requests.Session(); s.headers['User-Agent'] = UA
    out, report = [], {'pages': [], 'unresolved': []}
    covered = set()
    for (year, track), kais in sorted(meetings.items()):
        if want and year not in want:
            continue
        for url in candidate_urls(year, track, kais):
            time.sleep(a.delay)
            try:
                r = s.get(url, timeout=60)
            except requests.RequestException as e:
                report['pages'].append({'url': url, 'status': repr(e)}); continue
            if r.status_code != 200:
                report['pages'].append({'url': url, 'status': r.status_code}); continue
            r.encoding = r.apparent_encoding
            rows, problems = parse_overview(r.text, track)
            rec = {'url': url, 'status': 200, 'rows': len(rows), 'problems': problems}
            report['pages'].append(rec)
            for x in rows:
                days = expand(x['spec'], kais.get(x['kai']))
                if days is None or x['kai'] not in kais:
                    report['unresolved'].append({'url': url, 'spec': x['spec'], 'kai': x['kai']}); continue
                for d in days:
                    key = (year, track, x['kai'], d)
                    if key in covered: continue
                    covered.add(key)
                    out.append({'year': year, 'track': track, 'kai': x['kai'], 'nichime': d, 'turf_course': x['course'],
                                'lap_m': x['lap'], 'straight_m': x['straight'], 'width_m': x['width'], 'note': x['note'], 'source_url': url})
    out.sort(key=lambda r: (r['year'], r['track'], r['kai'], r['nichime']))
    with open(a.out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(out)
    json.dump(report, open(a.out + '.report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = sum(1 for q in report['pages'] if q['status'] == 200)
    print('pages ok', ok, 'of', len(report['pages']), 'day rows', len(out), 'unresolved', len(report['unresolved']))


if __name__ == '__main__':
    main()
