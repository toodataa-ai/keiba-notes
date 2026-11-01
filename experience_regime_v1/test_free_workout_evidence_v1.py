"""Realistic fictional HTML fixture tests. Never copy a publisher's article or scores."""
import unittest
from datetime import date
from experience_regime_v1.free_workout_evidence_v1 import (
    workbook_from_html, parse_time, parse_course, capture, validate_source_url)

ROSTER = {"試験馬A": 1, "試験馬B": 2, "出走馬データ未掲載": 3}
HTML = """
<html><head><meta property="article:published_time" content="2026-11-11T14:00:00+09:00"></head>
<body><main><article>
<h3>試験馬A</h3><p>試験馬A 11月11日（水）</p>
<figure><table>
<tr><th>時期</th><th>場所</th><th>6F</th><th>5F</th><th>4F</th><th>3F</th><th>1F</th><th>脚色</th></tr>
<tr><td>最終追切</td><td>栗東CW(良)</td><td>81.7</td><td>65.6</td><td>50.3</td><td>35.9</td><td>11.6</td><td>馬なり</td></tr>
<tr><td>1週前</td><td>栗東CW(稍重)</td><td>⑦98.0</td><td>66.8</td><td>52.4</td><td>36.8</td><td>11.2</td><td>強め</td></tr>
<tr><td>前走最終</td><td>栗東CW(重)</td><td>83.2</td><td>68.1</td><td>52.5</td><td>36.2</td><td>11.4</td><td>馬なり</td></tr>
</table></figure>
<p>サイト独自の調教ランキング・記事本文を取り込んではいけない。</p>
<h3>試験馬B</h3><p>試験馬B 11月12日（木）</p>
<table><tr><th>時期</th><th>場所</th><th>6F</th><th>5F</th><th>4F</th><th>3F</th><th>1F</th><th>脚色</th></tr>
<tr><td>最終追切</td><td>美浦坂路(良)</td><td> </td><td></td><td>55.2</td><td>40.0</td><td>12.4</td><td>馬なり</td></tr>
</table>
<h3>別馬</h3><table><tr><td>最終追切</td></tr></table>
</article></main></body></html>""".encode()


class TestWorkoutSource(unittest.TestCase):
    def test_extract_only_numeric_facts_and_frozen_horse_names(self):
        r=workbook_from_html(HTML,ROSTER,date(2026,11,15))
        self.assertEqual(set(r),{"試験馬A","試験馬B"})
        self.assertEqual(len(r["試験馬A"]["workouts"]),3)
        a=r["試験馬A"]["workouts"][0]
        self.assertEqual(a["split_seconds"]["6F"],81.7)
        self.assertEqual(a["split_seconds"]["1F"],11.6)
        self.assertEqual(a["workout_date"],"2026-11-11")
        week=r["試験馬A"]["workouts"][1]
        self.assertIsNone(week["split_seconds"]["6F"])
        self.assertEqual(week["split_seconds"]["5F"],66.8)
        self.assertNotIn("rating",str(r))
        self.assertNotIn("commentary",str(r))

    def test_factual_json_without_retroactive_results_or_grades(self):
        doc=capture(
            "2026-11-14","2026-11-15-tokyo-11","2026-11-15T15:40:00+09:00",
            "https://umasiru.com/archives/12345",HTML,"2026-11-13T10:00:00+09:00",
            frozen_roster=ROSTER,roster_proof={"commit_sha":"a"*40},is_formal=True)
        self.assertEqual(doc["verified_horses"],2)
        self.assertEqual(doc["roster_horses"],3)
        self.assertEqual(doc["unavailable_horses"],["出走馬データ未掲載"])
        self.assertIsNone(doc["workout_factor_grades"])
        self.assertFalse(doc["workout_score_calibrated"])
        self.assertTrue(doc["no_odds_or_results_used"])
        self.assertFalse(doc["production_effect"])
        self.assertNotIn("記事本文",str(doc))
        self.assertNotIn("ランキング",str(doc))

    def test_reject_poststart_observation_even_if_publication_older(self):
        with self.assertRaisesRegex(ValueError,"observation_was_not_prestart"):
            capture("2026-11-14","2026-11-15-tokyo-11","2026-11-15T15:40:00+09:00",
                "https://umasiru.com/archives/12345",HTML,"2026-11-15T15:41:00+09:00",
                frozen_roster=ROSTER,roster_proof={"commit_sha":"a"*40},is_formal=True)

    def test_reject_after_start_publication(self):
        late=HTML.replace(b"2026-11-11T14:00:00+09:00",b"2026-11-15T16:00:00+09:00")
        with self.assertRaisesRegex(ValueError,"article_was_published_after_race_start"):
            capture("2026-11-14","2026-11-15-tokyo-11","2026-11-15T15:40:00+09:00",
                "https://umasiru.com/archives/12345",late,"2026-11-14T10:00:00+09:00",
                frozen_roster=ROSTER,roster_proof={"commit_sha":"a"*40},is_formal=True)

    def test_reject_non_allowlisted_url_and_non_public_endpoints(self):
        for url in ["http://umasiru.com/archives/123","https://evil.example/archives/123",
                    "https://umasiru.com/wp-admin/","https://umasiru.com/archives/123?x=1"]:
            with self.assertRaises(ValueError):
                validate_source_url(url)

    def test_duplicate_heading_and_impossible_splits_block(self):
        duplicate=HTML.replace(b"</article>", b"<h3>\xe8\xa9\xa6\xe9\xa8\x93\xe9\xa6\xacaA</h3></article>")
        # Reinsert an actual duplicate numeric heading+table.
        duplicate=HTML.replace(b"</article>", HTML.split(b"<h3>")[1].split(b"<h3>")[0].join([b"<h3>",b""])+b"</article>")
        with self.assertRaisesRegex(ValueError,"duplicate_horse_heading"):
            workbook_from_html(duplicate,ROSTER,date(2026,11,15))
        bad=HTML.replace(b">81.7<",b">35.0<")
        with self.assertRaisesRegex(ValueError,"impossible_workout_split_order"):
            workbook_from_html(bad,ROSTER,date(2026,11,15))

    def test_time_range_and_circled_seven(self):
        self.assertIsNone(parse_time("⑦98.0","6F"))
        self.assertIsNone(parse_time("1.0","1F"))
        self.assertIsNone(parse_time("13.23","1F"))
        self.assertEqual(parse_time("11.2","1F"),11.2)
        self.assertEqual(parse_course("栗東CW(良)")["course"],"ウッド")


if __name__=="__main__":
    unittest.main()
