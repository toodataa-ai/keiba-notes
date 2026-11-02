import unittest
import jra_course_overview as c

HTML = '''<h2>芝コース</h2><h3>（1）使用コース</h3><table class="basic"><caption>x</caption><thead><tr><th>開催日</th></tr></thead><tbody>
<tr><td>第2回東京 前6日</td><td>A</td><td> 2,083.1<span>メートル</span></td><td>525.9<span>メートル</span></td><td>31から41<span>メートル</span></td><td class="left">内柵を最内に設置</td></tr>
<tr><td>第2回東京 第7日から第10日</td><td>B</td><td>2,101.9</td><td>525.9</td><td>28から38</td><td class="left">Aコースから3メートル外に内柵を設置</td></tr>
<tr><td>第2回東京 第11日・第12日<br>第3回東京 前4日</td><td>C</td><td>2,120.8</td><td>525.9</td><td>25から35</td><td></td></tr>
<tr><td>第3回東京 後4日</td><td>D</td><td>2,139.7</td><td>525.9</td><td>22から32</td><td></td></tr></tbody></table><h2>ダートコース</h2>'''


class T(unittest.TestCase):
    def test_parse_and_expand(self):
        rows, probs = c.parse_overview(HTML, '東京')
        self.assertEqual(probs, [])
        self.assertEqual([(r['kai'], r['spec'], r['course']) for r in rows],
                         [(2, '前6日', 'A'), (2, '第7日から第10日', 'B'), (2, '第11日・第12日', 'C'), (3, '前4日', 'C'), (3, '後4日', 'D')])
        self.assertEqual(rows[0]['lap'], '2083.1')
        self.assertEqual(c.expand('前6日', 12), [1, 2, 3, 4, 5, 6])
        self.assertEqual(c.expand('第7日から第10日', 12), [7, 8, 9, 10])
        self.assertEqual(c.expand('第11日・第12日', 12), [11, 12])
        self.assertEqual(c.expand('後4日', 8), [5, 6, 7, 8])
        self.assertIsNone(c.expand('よく分からない', 8))

    def test_urls(self):
        u = [x[1] for x in c.candidate_urls('2024', '東京', {1, 2, 3, 4, 5})]
        self.assertIn(c.BASE + '2024_2-3_tokyo.html', u)
        self.assertIn(c.BASE + '2024_4-5_tokyo.html', u)
        self.assertIn(c.BASE + '2024_1_tokyo.html', u)
        self.assertIn(c.BASE + '2024_3-4-5_tokyo.html'.replace('3-4-5', '3-5'), u)
        self.assertEqual(c.expand('全4日', None), [1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
