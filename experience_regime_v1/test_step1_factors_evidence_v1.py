"""Non-synthetic regression checks for JRA official prereace factor parser."""
import unittest
from datetime import date
from bs4 import BeautifulSoup
from experience_regime_v1.step1_factors_evidence_v1 import parse_past


class TestFactorEvidence(unittest.TestCase):
    def test_extract_prior_going_and_actual_corner_positions(self):
        cell = BeautifulSoup(
            '<td class="past">2026年10月17日 京都 未勝利 3着 12頭4番3番人気'
            ' 田中 55.0 kg 1600芝 1:35.1 稍重 478 kg 2 3 3F 34.6 敵馬(0.6)</td>',
            'html.parser').td
        actual = parse_past(cell, date(2026, 11, 1))
        self.assertEqual(actual['passing_positions'], [2, 3])
        self.assertEqual(actual['going'], '稍重')
        self.assertEqual(actual['surface'], '芝')
        self.assertEqual(actual['course'], '京都')
        self.assertEqual(actual['finish'], 3)

    def test_excluded_history_does_not_create_fake_start(self):
        cell = BeautifulSoup(
            '<td class="past">2026年10月17日 京都 新馬 出走除外 10頭3番</td>',
            'html.parser').td
        self.assertIsNone(parse_past(cell, date(2026, 11, 1)))

    def test_future_and_same_day_performance_rejected(self):
        cell = BeautifulSoup(
            '<td class="past">2026年11月1日 東京 未勝利 1着 12頭4番</td>',
            'html.parser').td
        with self.assertRaisesRegex(ValueError, 'future_or_today_past_race'):
            parse_past(cell, date(2026, 11, 1))

    def test_missing_corner_data_is_null_not_invented(self):
        cell = BeautifulSoup(
            '<td class="past">2026年10月17日 新潟 新馬 4着 13頭6番 '
            '55.0 kg 1200芝 1:11.8 良 470 kg 3F 36.1</td>',
            'html.parser').td
        self.assertIsNone(parse_past(cell, date(2026, 11, 1))['passing_positions'])


if __name__ == '__main__':
    unittest.main()
