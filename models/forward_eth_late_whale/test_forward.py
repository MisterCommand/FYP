"""Network-free freeze, execution, power and retained single-look checks."""

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import io
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from statistics import NormalDist
import tempfile
import unittest
from unittest.mock import Mock, patch

import rule
import register_forward
import score_forward


def spec():
    return {'N': 2, 'alpha': .01, 'pm_cost': .02, 'late_whale_lookback_seconds': 86400,
        'large_trade_notional': 1000, 'seed': 42, 'exact_max_clusters': 16, 'monte_carlo_permutations': 65536}


def event():
    return {'id': '1', 'title': 'Ethereum Up or Down on November 26, 2026?',
        'endDate': '2026-11-26T17:00:00Z', 'closed': True, 'series': [{'id': '40'}],
        'markets': [{'id': '2', 'question': 'Ethereum Up or Down?', 'closed': True,
            'conditionId': '0xabc', 'outcomes': '["Up","Down"]', 'outcomePrices': '["1","0"]',
            'clobTokenIds': '["10","11"]', 'closedTime': '2026-11-26T17:05:00Z',
            'description': 'Binance ETHUSDT daily candle at 12:00 PM ET.'}]}


def described():
    now = int(datetime(2026, 11, 27, tzinfo=timezone.utc).timestamp())
    info, market = rule.describe(event(), 0, now)
    return info, market, now


def insert(db, key, stamp, side, price, signed=0., notional=1.):
    db.execute('INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (key, '2', 'wallet', stamp, key, side, 'BUY', 1., price, 1., price, notional, signed))


def observations():
    info, market, _ = described()
    result = []
    for index in range(3):
        result.append({**info, 'cutoff': info['cutoff']+index*86400, 'expiry': info['expiry']+index*86400,
            'cluster': f'2026-11-{26+index}', 'rid': f'eth_updown_daily:{index}', 'market_id': str(index),
            'entries': {'YES': (info['cutoff']+index*86400+1, .6), 'NO': (info['cutoff']+index*86400+2, .4)},
            'late_whale': 1. if index != 1 else 0., 'realized': market.realized})
    return result


def collecting_fixture(root, status='exhausted', records=None):
    for name in ('events', 'trades', 'cache'):
        (root/name).mkdir()
    info, market, _ = described()
    trade = {'condition_id': '0xabc', 'token_id': '10', 'side': 'BUY', 'size': 2000,
        'price': .5, 'proxy_wallet': '0x'+'1'*40, 'transaction_hash': '0x'+'2'*64, 'timestamp': info['cutoff']-1}
    records = [trade, trade] if records is None else records
    def collect(eid):
        folder = root/'trades'/eid
        folder.mkdir()
        rule.atomic_json(folder/'summary.json', {'status': status, 'pages': 1, 'next_cursor': None, 'participant_rows': len(records)})
        rule.atomic_json(folder/'config.json', {})
        with gzip.open(folder/'page_00001.json.gz', 'wt') as handle:
            json.dump({'request_cursor': None, 'response': {'data': records, 'pagination': {'next_cursor': None}}}, handle)
    collector = Mock()
    collector.collect.side_effect = collect
    return market, collector


class ForwardTests(unittest.TestCase):
    def test_streamed_text_hash_matches_original_across_crlf_boundaries(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(rule, 'HASH_CHUNK_BYTES', 4):
            for suffix in ('.py', '.json', '.md', '.csv'):
                path = Path(folder)/('synthetic'+suffix)
                for payload in (b'', b'\r', b'abc\r\nx', b'abc\r\r\nend\r', b'a\nb\r\nc\r\n'*5):
                    with self.subTest(suffix=suffix, payload=payload):
                        path.write_bytes(payload)
                        expected = hashlib.sha256(payload.replace(b'\r\n', b'\n')).hexdigest()
                        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Whole-file read')):
                            self.assertEqual(rule.digest(path), expected)

    def test_streamed_binary_hash_is_byte_exact_and_reads_bounded_chunks(self):
        payload = b'\x00\xff\r\n'*(rule.HASH_CHUNK_BYTES+3)
        sizes = []
        parent = self
        class Reader(io.BytesIO):
            def read(self, size=-1):
                parent.assertEqual(size, rule.HASH_CHUNK_BYTES)
                sizes.append(size)
                return super().read(size)
        with patch.object(Path, 'open', return_value=Reader(payload)), patch.object(Path, 'read_bytes', side_effect=AssertionError('Whole-file read')):
            self.assertEqual(rule.digest(Path('synthetic.sqlite3')), hashlib.sha256(payload).hexdigest())
        self.assertGreater(len(sizes), 2)
        with patch.object(Path, 'open', return_value=Reader(b'')):
            self.assertEqual(rule.digest(Path('empty.sqlite3')), hashlib.sha256(b'').hexdigest())

    def test_streamed_hash_propagates_read_errors(self):
        class Reader(io.BytesIO):
            def read(self, size=-1):
                raise OSError('Synthetic read failure')
        with patch.object(Path, 'open', return_value=Reader()), self.assertRaisesRegex(OSError, 'Synthetic read failure'):
            rule.digest(Path('synthetic.sqlite3'))

    def test_missing_or_future_settlement_timestamp_is_pending(self):
        _, _, now = described()
        for values in ({}, {'closedTime': None, 'umaEndDate': ''}, {'closedTime': '2026-11-28T17:05:00Z'}):
            with self.subTest(values=values):
                raw = event()
                raw['markets'][0].pop('closedTime')
                raw['markets'][0].update(values)
                with self.assertRaises(rule.Pending):
                    rule.describe(raw, 0, now)

    def test_uma_timestamp_is_sufficient_and_malformed_timestamp_still_fails(self):
        _, market, now = described()
        raw = event()
        raw['markets'][0]['umaEndDate'] = raw['markets'][0].pop('closedTime')
        self.assertEqual(rule.describe(raw, 0, now)[1].resolved_ts, market.resolved_ts)
        raw['markets'][0]['umaEndDate'] = 'not-a-timestamp'
        with self.assertRaises(ValueError) as caught:
            rule.describe(raw, 0, now)
        self.assertNotIsInstance(caught.exception, rule.Pending)

    def test_pending_market_does_not_abort_batch_or_count_toward_n(self):
        _, _, now = described()
        pending = event()
        pending['markets'][0].pop('closedTime')
        ready = event()
        ready['id'] = 'ready'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root/'synthetic.sqlite3'
            with sqlite3.connect(cache):
                pass
            output = io.StringIO()
            collector = Mock()
            with patch.object(score_forward, 'discover', return_value=[pending, ready]), patch.object(score_forward, 'cache_event', return_value=(cache, 'synthetic')), patch.object(score_forward, 'spot_eligible', return_value={}), patch.object(rule, 'features', return_value=observations()[0]), patch.object(rule.signals, 'metrics') as metrics, redirect_stdout(output):
                status = score_forward.run(root, {**spec(), 'training_hashes': {}}, {'timestamp': 0}, collector, now)
            self.assertEqual(status['n_eligible_dates'], 1)
            self.assertEqual(status['n_pending_markets'], 1)
            self.assertEqual(status['pending'][0]['event_id'], '1')
            self.assertIn('Pending: 1;', output.getvalue())
            self.assertEqual(json.loads((root/'progress.json').read_text())['pending'], status['pending'])
            self.assertFalse((root/'single_look.json').exists())
            collector.collect.assert_not_called()
            metrics.assert_not_called()

    def test_committed_amendment_preserves_original_freeze_and_protocol(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            local = repo/'models/forward_eth_late_whale'
            local.mkdir(parents=True)
            paths = ('models/forward_eth_late_whale/rule.py', 'models/forward_eth_late_whale/score_forward.py')
            hashes = {}
            for path in paths:
                (repo/path).write_bytes(b'synthetic amended source\n')
                hashes[path] = hashlib.sha256(b'synthetic amended source\n').hexdigest()
            original = {'N': 762, 'code_hashes': dict.fromkeys(paths, 'old'), 'collector_hashes': {}, 'wallet_eligibility_proof': {'cutoff': 1}}
            amended = {**original, 'code_hashes': hashes, 'amendments': [{'freeze_commit': 'freeze', 'before_post_freeze_scoring': True, 'rule_sha256': hashes[paths[0]], 'scorer_sha256': hashes[paths[1]]}]}
            encoded = json.dumps(amended).encode()
            (local/'registration.json').write_bytes(encoded)
            (local/'FORWARD_PREREGISTRATION.md').write_bytes(b'Original protocol\n')
            (local/'AMENDMENTS.md').write_bytes(b'Approved before scoring\n')
            blobs = [json.dumps(original).encode(), encoded, b'Approved before scoring\n', b'Original protocol\n']
            with patch.object(rule, 'FOLDER', local), patch.object(rule, 'REPO', repo), patch.object(score_forward, 'git', side_effect=['false', 'freeze', '2']), patch.object(score_forward.subprocess, 'check_output', side_effect=blobs), patch.object(score_forward.time, 'time', return_value=3):
                registered, freeze = score_forward.registration()
            self.assertEqual(freeze, {'commit': 'freeze', 'timestamp': 2})
            self.assertEqual(registered['N'], 762)
            for changed in ({**amended, 'N': 763}, {**amended, 'amendments': []}, {**amended, 'code_hashes': {}}):
                with self.assertRaises(ValueError):
                    score_forward.validate_amendment(changed, original, 'freeze')
            (local/'AMENDMENTS.md').write_bytes(b'Uncommitted change\n')
            with patch.object(rule, 'FOLDER', local), patch.object(rule, 'REPO', repo), patch.object(score_forward, 'git', side_effect=['false', 'freeze']), patch.object(score_forward.subprocess, 'check_output', side_effect=blobs):
                with self.assertRaisesRegex(ValueError, 'Amendment is not committed'):
                    score_forward.registration()

    def test_registration_refuses_an_uncommitted_freeze(self):
        with patch.object(score_forward, 'git', side_effect=['false', '']):
            with self.assertRaisesRegex(ValueError, 'committed forward registration'):
                score_forward.registration()

    def test_registration_detects_content_changes_and_pinned_code_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = json.dumps({'code_hashes': {'models/forward_eth_late_whale/rule.py': 'wrong'}}).encode()+b'\n'
            (root/'registration.json').write_bytes(registry.replace(b'\n', b'\r\n'))
            (root/'FORWARD_PREREGISTRATION.md').write_bytes(b'Frozen\r\n')
            with patch.object(rule, 'FOLDER', root), patch.object(score_forward, 'git', side_effect=['false', 'commit']), patch.object(score_forward.subprocess, 'check_output', side_effect=[registry, b'Frozen\n']):
                with self.assertRaisesRegex(ValueError, 'Pinned rule/collector code changed'):
                    score_forward.registration()
            (root/'registration.json').write_bytes(registry+b'changed')
            with patch.object(rule, 'FOLDER', root), patch.object(score_forward, 'git', side_effect=['false', 'commit']), patch.object(score_forward.subprocess, 'check_output', return_value=registry):
                with self.assertRaisesRegex(ValueError, 'Frozen registration changed'):
                    score_forward.registration()

    def test_complete_cache_deduplicates_and_reuses_without_recollection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            market, collector = collecting_fixture(root)
            cache, source = score_forward.cache_event(root, event(), market, collector, spec())
            with sqlite3.connect(cache) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM trades').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT raw_rows,deduplicated_rows FROM build').fetchone(), (2, 1))
            self.assertEqual(score_forward.cache_event(root, event(), market, collector, spec()), (cache, source))
            collector.collect.assert_called_once()
            rule.atomic_json(root/'trades/1/config.json', {'changed': True})
            with self.assertRaisesRegex(ValueError, 'cache/source mismatch'):
                score_forward.cache_event(root, event(), market, collector, spec())

    def test_empty_exhausted_history_is_not_a_fabricated_cash_date(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            market, collector = collecting_fixture(root, records=[])
            cache, _ = score_forward.cache_event(root, event(), market, collector, spec())
            info, _, _ = described()
            with sqlite3.connect(cache) as db, self.assertRaises(rule.Ineligible):
                rule.features(db, market, info, 0, spec())

    def test_incomplete_history_stops_instead_of_skipping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            market, collector = collecting_fixture(root, status='budget_limit')
            with self.assertRaisesRegex(ValueError, 'history incomplete'):
                score_forward.cache_event(root, event(), market, collector, spec())

    def test_missing_spot_coverage_stops_instead_of_skipping(self):
        info, _, _ = described()
        with tempfile.TemporaryDirectory() as folder, patch.object(score_forward, 'candles', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'spot coverage'):
                score_forward.spot_eligible(Path(folder), '1', info, Mock())

    def test_cutoff_equal_to_or_before_freeze_is_refused(self):
        info, _, now = described()
        for freeze in (info['cutoff'], info['cutoff']+1):
            with self.subTest(freeze=freeze), self.assertRaises(rule.PreFreeze):
                rule.describe(event(), freeze, now)

    def test_wrong_horizon_and_unregistered_source_fail(self):
        info, _, now = described()
        with self.assertRaisesRegex(ValueError, 't-12h'):
            rule.require_forward({**info, 'cutoff': info['cutoff']+1}, 0)
        raw = event()
        raw['markets'][0]['description'] = 'Chainlink daily 12:00 PM ET.'
        with self.assertRaisesRegex(rule.Ineligible, 'Oracle'):
            rule.describe(raw, 0, now)

    def test_forward_guard_precedes_feature_queries(self):
        info, market, _ = described()
        db = Mock()
        with self.assertRaises(rule.PreFreeze):
            rule.features(db, market, info, info['cutoff'], spec())
        db.execute.assert_not_called()

    def test_late_window_threshold_and_post_cutoff_entry_are_identical(self):
        info, market, _ = described()
        cutoff = info['cutoff']
        with sqlite3.connect(':memory:') as db:
            rule.create_tables(db, {'2': market})
            insert(db, 'prior', cutoff-10, 'YES', .5)
            insert(db, 'left', cutoff-86400, 'YES', .5, 1000., 1000.)
            insert(db, 'too-old', cutoff-86401, 'YES', .5, -10000., 10000.)
            insert(db, 'at-cutoff', cutoff, 'YES', .01, -10000., 10000.)
            insert(db, 'small', cutoff-1, 'NO', .5, -999., 999.)
            insert(db, 'yes-z', cutoff+1, 'YES', .7)
            insert(db, 'yes-a', cutoff+1, 'YES', .6)
            insert(db, 'no', cutoff+2, 'NO', .4)
            row = rule.features(db, market, info, cutoff-1, spec())
        self.assertEqual(row['late_whale'], 1.)
        self.assertEqual(row['entries']['YES'], (cutoff+1, .6))
        value, traded = rule.audit.prior.pm_return(row['late_whale'], row, .02)
        self.assertTrue(traded)
        self.assertAlmostEqual(value, 1/.62-1)

    def test_entry_at_expiry_does_not_qualify(self):
        info, market, _ = described()
        with sqlite3.connect(':memory:') as db:
            rule.create_tables(db, {'2': market})
            insert(db, 'prior', info['cutoff']-1, 'YES', .5)
            insert(db, 'yes', info['cutoff']+1, 'YES', .6)
            insert(db, 'no-expiry', info['expiry'], 'NO', .4)
            with self.assertRaises(rule.Ineligible):
                rule.features(db, market, info, info['cutoff']-1, spec())

    def test_no_whales_means_cash_and_cost_cap_means_cash(self):
        row = observations()[0]
        self.assertFalse(rule.would_trade({**row, 'late_whale': 0.}, spec()))
        row['entries']['YES'] = (row['cutoff']+1, .98)
        self.assertFalse(rule.would_trade(row, spec()))

    def test_empty_and_sub_n_progress_never_calls_roi_or_test(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(rule.audit.prior, 'pm_return') as roi, patch.object(rule.signals, 'metrics') as metrics:
                for rows in ([], observations()[:1]):
                    status = rule.terminal_look(rows, spec(), {'timestamp': 0}, root, root/'report.md')
                    self.assertLess(status['n_eligible_dates'], 2)
                roi.assert_not_called()
                metrics.assert_not_called()
            self.assertFalse((root/'single_look.json').exists())
            self.assertFalse((root/'report.md').exists())

    def test_one_look_claims_before_roi_and_uses_first_n_dates_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = rule.audit.prior.pm_return
            def checked(*args):
                self.assertEqual(json.loads((root/'single_look.json').read_text())['status'], 'claimed')
                return original(*args)
            with patch.object(rule.audit.prior, 'pm_return', side_effect=checked) as roi:
                status = rule.terminal_look(observations(), spec(), {'timestamp': 0, 'commit': 'frozen'}, root, root/'report.md')
                self.assertTrue(status['tested'])
                self.assertEqual(roi.call_count, 2)
            saved = json.loads((root/'single_look.json').read_text())
            self.assertEqual(saved['dates'], ['2026-11-26', '2026-11-27'])
            self.assertEqual(saved['status'], 'complete')
            self.assertEqual(saved['result']['n_clusters'], 2)
            self.assertAlmostEqual(saved['result']['metric'], (1/.62-1)/2)
            with self.assertRaisesRegex(ValueError, 'already'):
                rule.terminal_look(observations(), spec(), {'timestamp': 0}, root, root/'report.md')

    def test_error_during_test_retains_claim_and_blocks_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(rule.signals, 'metrics', side_effect=RuntimeError('interrupted')) as metrics:
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    rule.terminal_look(observations(), spec(), {'timestamp': 0}, root, root/'report.md')
                with self.assertRaisesRegex(ValueError, 'Single look already claimed'):
                    rule.terminal_look(observations(), spec(), {'timestamp': 0}, root, root/'report.md')
                metrics.assert_called_once()
            self.assertEqual(json.loads((root/'single_look.json').read_text())['status'], 'claimed')

    def test_prefreeze_market_is_not_collected_or_scored(self):
        info, _, now = described()
        with tempfile.TemporaryDirectory() as folder, patch.object(score_forward, 'discover', return_value=[event()]):
            collector = Mock()
            with redirect_stdout(io.StringIO()):
                status = score_forward.run(Path(folder), spec(), {'timestamp': info['cutoff']}, collector, now)
            self.assertEqual(status['n_eligible_dates'], 0)
            collector.collect.assert_not_called()

    def test_completed_run_does_not_collect_or_test_again(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rule.atomic_json(root/'single_look.json', {'status': 'complete'})
            with patch.object(score_forward, 'discover') as discover, redirect_stdout(io.StringIO()):
                score_forward.run(root, spec(), {}, Mock(), 0)
            discover.assert_not_called()

    def test_progress_counts_dates_not_contracts_and_includes_cash(self):
        rows = observations()
        rows.append(deepcopy(rows[0]))
        self.assertEqual(rule.progress(rows, spec()), {'n_eligible_dates': 3, 'n_traded_dates': 2, 'target_dates': 2})

    def test_power_includes_cash_dates_and_uses_unbiased_variance(self):
        rows = [{**r, 'net_return': v, 'traded': int(v != 0)} for r, v in zip(observations(), [1., 0., -.1])]
        stats = register_forward.summary(rows)
        self.assertEqual(stats['dates'], 3)
        self.assertAlmostEqual(stats['trade_rate'], 2/3)
        self.assertAlmostEqual(stats['variance_ddof1'], sum((v-.3)**2 for v in [1., 0., -.1])/2)
        plan = register_forward.power(stats, .5)
        z = NormalDist().inv_cdf(.99)+NormalDist().inv_cdf(.8)
        self.assertEqual(plan['N'], math.ceil(z*z*stats['variance_ddof1']/.15**2))
        with self.assertRaises(ValueError):
            register_forward.summary([])
        with self.assertRaises(ValueError):
            register_forward.power({**stats, 'mean_roi': 0}, .5)

    def test_gamma_cycle_and_no_progress_fail_closed(self):
        for responses in ([{'events': [event()], 'next_cursor': 'a'}, {'events': [event()], 'next_cursor': 'a'}],
                          [{'events': [], 'next_cursor': 'a'}]):
            with tempfile.TemporaryDirectory() as folder:
                collector = Mock()
                collector.fetch.side_effect = responses
                with self.assertRaises(ValueError):
                    score_forward.discover(Path(folder), collector, {})

    def test_text_hash_normalizes_crlf_and_content_changes_are_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'rule.py'
            path.write_bytes(b'x=1\n')
            expected = rule.digest(path)
            path.write_bytes(b'x=1\r\n')
            self.assertEqual(rule.digest(path), expected)
            path.write_bytes(b'x=2\r\n')
            self.assertNotEqual(rule.digest(path), expected)


if __name__ == '__main__':
    unittest.main()
