"""Release mapping and feasibility checks without strategy performance."""

from pathlib import Path
import gzip
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from coverage import bucket_family, build_cache, qualifying_counts, skill
from releases import bls_releases, mapped_release, reference, release_utc


class ReleaseTests(unittest.TestCase):
    def test_eastern_daylight_saving(self):
        self.assertEqual(release_utc('2026-01-13').isoformat(), '2026-01-13T13:30:00+00:00')
        self.assertEqual(release_utc('2026-07-14').isoformat(), '2026-07-14T12:30:00+00:00')
        with self.assertRaises(ValueError):
            release_utc('2026-02-30')

    def test_bls_calendar_mapping_and_missing_release(self):
        text = ('## Page 1:\nURL: https://www.bls.gov/schedule/2026/01_sched.htm\n'
                '| 28 Consumer Price Index December 2025 08:30 AM | 29 | 30 | 31 | 1 | 2 | 3 |\n'
                '| 4 | 5 | 6 | 7 | 8 | 9 Employment Situation December 2025 08:30 AM | 10 |\n'
                '| 11 | 12 | 13 Consumer Price Index December 2025 08:30 AM | 14 | 15 | 16 | 17 |\n')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'schedule.md'
            path.write_text(text)
            official = bls_releases([path])
        self.assertEqual(official['cpi', '2025-12']['release_utc'], '2026-01-13T13:30:00+00:00')
        self.assertEqual(official['employment', '2025-12']['release_utc'], '2026-01-09T13:30:00+00:00')
        event = {'title': 'October Inflation - Monthly', 'endDate': '2025-11-01T00:00:00Z'}
        self.assertIsNone(mapped_release(event, 'cpi', official))

    def test_reference_period_not_gamma_end_month(self):
        event = {'title': 'December Inflation - Monthly', 'endDate': '2026-01-16T00:00:00Z'}
        self.assertEqual(reference(event, 'cpi'), '2025-12')
        event = {'title': 'US inflation >0% from Oct to Nov 2023?',
                 'description': 'BLS November 2023 Consumer Price Index report',
                 'endDate': '2023-12-15T00:00:00Z'}
        self.assertEqual(reference(event, 'cpi'), '2023-11')
        with self.assertRaises(ValueError):
            reference({'title': 'Unknown release', 'endDate': '2026-01-01T00:00:00Z'}, 'cpi')

    def test_separate_cpi_bucket_families_and_legacy_thresholds(self):
        for title, series, expected in [
                ('November Inflation', '10008', 'cpi_headline_mom'),
                ('November Inflation - Annual', '10007', 'cpi_headline_yoy'),
                ('Core CPI MoM - July 2026', '12054', 'cpi_core_mom'),
                ('Core CPI YoY - July 2026', '11905', 'cpi_core_yoy'),
                ('US inflation >0.1% from July to August 2024?', None, 'cpi_threshold')]:
            event = {'title': title, 'series': [{'id': series}] if series else []}
            self.assertEqual(bucket_family(event, 'cpi'), expected)


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute("ATTACH DATABASE ':memory:' AS fomc")
        for schema in ('main', 'fomc'):
            self.db.execute(f'CREATE TABLE {schema}.markets (market_id TEXT, event_id TEXT, resolved_ts INTEGER, realized INTEGER)')
            self.db.execute(f'CREATE TABLE {schema}.trades (market_id TEXT, wallet TEXT, ts INTEGER, signed_yes_shares REAL, price REAL, notional REAL)')
        self.db.executemany('INSERT INTO main.markets VALUES (?,?,?,?)', [
            ('same', 'payrolls:old', 90, 1), ('other', 'unemployment:old', 90, 1),
            ('future', 'payrolls:future', 100, 1)])
        self.db.execute("INSERT INTO fomc.markets VALUES ('f','fomc:old',80,1)")
        self.db.executemany('INSERT INTO main.trades VALUES (?,?,?,?,?,?)',
            [('same', 'eligible', 70, 1, .4, .4)] * 3 +
            [('same', 'late', 100, 1, .4, .4)] * 5 +
            [('other', 'foreign', 70, 1, .4, .4)] * 5 +
            [('future', 'unresolved', 70, 1, .4, .4)] * 5)
        self.db.executemany('INSERT INTO fomc.trades VALUES (?,?,?,?,?,?)',
            [('f', 'eligible', 70, 1, .4, .4)] * 2)

    def tearDown(self):
        self.db.close()

    def test_skill_excludes_other_families_unresolved_and_cutoff_trades(self):
        scores = skill(self.db, 'payrolls', 100)
        self.assertEqual(set(scores), {'eligible'})
        self.assertEqual(scores['eligible']['n_trades'], 5)
        self.assertAlmostEqual(scores['eligible']['score'], .3)

    def test_sweep_counts_match_point_in_time_query_including_boundaries(self):
        requests = [(f, c) for f in ('payrolls', 'unemployment') for c in (70, 80, 90, 100, 101)]
        swept = qualifying_counts(self.db, requests)
        for family, cutoff in requests:
            self.assertEqual(swept[family, cutoff], len(skill(self.db, family, cutoff)))

    def test_empty_skill(self):
        self.assertEqual(skill(self.db, 'payrolls', 1), {})
        self.assertEqual(qualifying_counts(self.db, []), {})


class CollectionTests(unittest.TestCase):
    def test_partial_and_broken_cursor_histories_fail_closed(self):
        for status, cursor, message in [('budget_limit', None, 'Partial collection'),
                                         ('exhausted', 'unexpected', 'Broken trade cursor')]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                raw = root / 'trades' / '1'
                raw.mkdir(parents=True)
                (root / 'discovery.json').write_text(json.dumps({'selected': [
                    {'event': {'id': '1', 'markets': []}}]}))
                (raw / 'summary.json').write_text(json.dumps({'status': status, 'pages': 1}))
                (raw / 'page_00001.json.gz').write_bytes(gzip.compress(json.dumps({
                    'request_cursor': cursor, 'response': {'data': [], 'pagination': {'next_cursor': None}}
                }).encode()))
                event = {'event_id': '1', 'family': 'payrolls', 'reference': '2026-01'}
                with patch('coverage.raw_fingerprint', return_value='fixture'):
                    with self.assertRaisesRegex(ValueError, message):
                        build_cache(root, {}, [event])
                self.assertFalse((root / 'trades.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
