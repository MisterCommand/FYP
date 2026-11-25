import gzip
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import audit
from feasibility import even_sample
from markets import rule, timestamp


class FeasibilityTests(unittest.TestCase):
    def test_sampling_is_chronological_deterministic_and_includes_endpoints(self):
        rows = [{'id': str(i), 'endDate': f'2025-01-{i+1:02d}'} for i in range(20)]
        selected = even_sample(list(reversed(rows)), 6)
        self.assertEqual([e['id'] for e in selected], ['0', '3', '7', '11', '15', '19'])
        self.assertEqual(even_sample([], 6), [])
        self.assertEqual(even_sample(rows[:2], 6), rows[:2])
        with self.assertRaises(ValueError):
            even_sample(rows, 1)

    def test_noon_is_from_rules_not_gamma_end_and_dst_is_respected(self):
        for month, end, expected in [('January', '2025-01-10T12:00:00Z', '2025-01-10T17:01:00Z'),
                                     ('July', '2025-07-10T12:00:00Z', '2025-07-10T16:01:00Z')]:
            e = {'title': f'Bitcoin above $94,000 on {month} 10?', 'endDate': end}
            m = {'description': 'Binance 1 minute candle at 12:00 in the ET timezone (noon)', 'question': e['title']}
            result = rule(e, m, 'btc_above_daily')
            self.assertEqual(result['expiry'], timestamp(expected))
            self.assertEqual(result['threshold'], 94000)
            self.assertEqual(result['cutoff'], result['expiry'] - 43200)

    def test_candle_closing_at_noon_differs_from_noon_candle(self):
        e = {'title': 'Ethereum above ___ on July 10?', 'endDate': '2026-07-10T16:00:00Z'}
        m = {'question': 'Ethereum above $2,000?', 'description': 'Binance 1 minute candle closing at 12:00 in ET (noon)'}
        self.assertEqual(rule(e, m, 'eth_above_daily')['expiry'], timestamp('2026-07-10T16:00:00Z'))

    def test_abbreviated_threshold_is_scaled(self):
        e = {'title': 'Bitcoin strikes on May 23?', 'endDate': '2025-05-23T12:00:00Z'}
        m = {'question': 'Will BTC close above $106K on May 23?', 'description': 'Binance 1 minute candle at 12:00 ET (noon)'}
        self.assertEqual(rule(e, m, 'btc_above_daily')['threshold'], 106000)

    def test_hourly_time_title_is_start_not_end(self):
        e = {'title': 'Bitcoin Up or Down - July 10, 3PM ET', 'endDate': '2026-07-10T20:00:00Z'}
        m = {'description': 'Binance 1 hour candle', 'eventStartTime': '2026-07-10T19:00:00Z'}
        info = rule(e, m, 'btc_updown_hourly')
        self.assertEqual(info['strike_ts'], timestamp('2026-07-10T19:00:00Z'))
        self.assertEqual(info['expiry'], timestamp('2026-07-10T20:00:00Z'))
        m['eventStartTime'] = '2026-07-10T18:00:00Z'
        with self.assertRaisesRegex(ValueError, 'disagree'):
            rule(e, m, 'btc_updown_hourly')

    def test_chainlink_range_is_recorded_but_not_claimed_as_binance(self):
        e = {'title': 'Bitcoin Up or Down - November 25, 5:00AM-6:00AM ET', 'endDate': '2026-11-25T11:00:00Z'}
        m = {'description': 'Chainlink TWAP of the time range specified in the title',
             'eventStartTime': '2026-11-25T10:00:00Z'}
        info = rule(e, m, 'btc_updown_hourly')
        self.assertEqual(info['expiry'], timestamp('2026-11-25T11:00:00Z'))
        self.assertFalse(info['model_compatible'])
        self.assertFalse(audit.spot_coverage(info, {}, []))

    def test_unknown_resolution_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'source'):
            rule({'title': 'unknown'}, {'description': ''}, 'btc_updown_daily')

    def test_misassigned_weekly_object_is_not_a_weekly_observation(self):
        e = {'title': 'Bitcoin Up or Down - June 4, 8 PM ET', 'endDate': '2025-06-04T21:00:00Z'}
        info = rule(e, {'description': 'Binance 1 hour candle'}, 'btc_updown_weekly')
        self.assertFalse(info['model_compatible'])
        self.assertIn('weekly Gamma series', info['exclusion'])

    def test_spot_coverage_missing_or_gapped_candles_fail_closed(self):
        cutoff = 40 * 86400
        info = {'cutoff': cutoff, 'strike_ts': None, 'model_compatible': True}
        hourly = [[(cutoff - (720-i)*3600)*1000, 1, 1, 1, 1, 1,
                   (cutoff - (719-i)*3600)*1000-1, 1, 1, 1, 1, 1] for i in range(720)]
        minute = [[(cutoff-60)*1000, 1, 1, 1, 1, 1, cutoff*1000-1, 1, 1, 1, 1, 1]]
        self.assertTrue(audit.spot_coverage(info, {'cutoff': minute}, hourly))
        self.assertFalse(audit.spot_coverage(info, {}, hourly))
        self.assertFalse(audit.spot_coverage(info, {'cutoff': minute}, hourly[:-1]))

    def test_stale_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with sqlite3.connect(root / 'trades.sqlite3') as db:
                db.execute('CREATE TABLE build (fingerprint TEXT)')
                db.execute("INSERT INTO build VALUES ('old')")
            with patch.object(audit, 'fingerprint', return_value='new'):
                with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
                    audit.validate_cache(root)

    def test_skill_uses_prior_resolution_and_prior_trades_in_allowed_sources(self):
        with sqlite3.connect(':memory:') as db:
            audit.create_tables(db, {})
            db.execute('INSERT INTO markets VALUES (?,?,?,?,?)', ('own', 'btc_updown_hourly:1', 'Up', 90, 1))
            db.execute('INSERT INTO markets VALUES (?,?,?,?,?)', ('future', 'btc_updown_hourly:2', 'Up', 100, 1))
            db.execute('INSERT INTO markets VALUES (?,?,?,?,?)', ('other', 'eth_updown_hourly:1', 'Up', 90, 1))
            rows = []
            for mid, wallet, stamp in [('own', 'good', 80), ('future', 'future-resolution', 80),
                                       ('own', 'future-trade', 100), ('other', 'wrong-family', 80)]:
                for i in range(5):
                    rows.append((f'{wallet}{i}'.encode(), mid, wallet, stamp, 'tx', 'YES', 'BUY', 1, .5, 1, .5, .5, .5))
            db.executemany('INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
            request = {'rid': 'btc_updown_hourly:3', 'family': 'btc_updown_hourly', 'cutoff': 100}
            results = list(audit.skill_stream(db, [request, {**request, 'cutoff': 200}], with_pnl=True))
            _, scores = results[0]
            self.assertEqual(set(scores), {'good'})
            self.assertGreater(scores['good']['score'], 0)
            self.assertEqual(set(results[1][1]), {'good', 'future-resolution', 'future-trade'})

    def test_partial_history_cannot_build_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'discovery.json').write_text(json.dumps({'selected': [{'event': {'id': '1', 'markets': []}}]}))
            out = root / 'trades/1'
            out.mkdir(parents=True)
            (out / 'summary.json').write_text(json.dumps({'status': 'budget_limit', 'next_cursor': 'next', 'pages': 0}))
            with patch.object(audit, 'fingerprint', return_value='source'):
                with self.assertRaisesRegex(ValueError, 'not exhausted'):
                    audit.build_cache(root, {}, [{'family': 'btc_updown_hourly', 'event_id': '1'}])

    def test_empty_exhausted_history_is_valid_but_has_zero_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'discovery.json').write_text(json.dumps({'selected': [{'event': {'id': '1', 'markets': []}}]}))
            out = root / 'trades/1'
            out.mkdir(parents=True)
            (out / 'summary.json').write_text(json.dumps({'status': 'exhausted', 'next_cursor': None, 'pages': 1, 'participant_rows': 0}))
            with gzip.open(out / 'page_00001.json.gz', 'wt') as handle:
                json.dump({'request_cursor': None, 'response': {'data': [], 'pagination': {'next_cursor': None}}}, handle)
            with patch.object(audit, 'fingerprint', return_value='source'):
                path = audit.build_cache(root, {}, [{'family': 'btc_updown_hourly', 'event_id': '1'}])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT raw_rows FROM build').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
