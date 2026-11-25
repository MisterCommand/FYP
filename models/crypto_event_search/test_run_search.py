import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import run_search as search
from register import IDS, split_events
from signals import (cluster_returns, digital, direction, fit_calibration, metrics,
                     realized_vol, spot_probability)


def spec():
    return {'families': {'btc': {'development': ['1'], 'holdout': ['2']}},
        'events': {'btc:2': {'cutoff': 400}}, 'strategies': IDS,
        'pooled_strategy': 'a_smart_pm', 'development_alpha': .1,
        'holdout_alpha': .01, 'search_round': 4, 'seed': 42,
        'exact_max_clusters': 16, 'monte_carlo_permutations': 64,
        'spot_vol_days': 30, 'spot_hourly_closes': 720, 'spot_threshold': .05,
        'minimum_fit_meetings': 3, 'calibration_l2': 1, 'pm_cost': .02}


def candle(start, duration=3600, price=100):
    return [start*1000, price, price, price, price, 1,
        (start+duration)*1000-1, 1, 1, 1, 1, 1]


def hourly(cutoff):
    return [candle(cutoff-(720-i)*3600, price=100*math.exp(.01*math.sin(i))) for i in range(720)]


def development(protocol):
    results = {key: {'n_clusters': 1, 'n_events': 1, 'n_contracts': 1,
        'n_trades': 0, 'metric': 0., 'p': 1.} for key in search.hypotheses(protocol)}
    results['btc/a_smart_pm'].update(metric=.1, p=.01)
    return {'input_hashes': {'source': 'old'}, 'results': results,
        'advanced': ['btc/a_smart_pm'], 'ranks': {key: i+1 for i, key in enumerate(results)}, 'frozen': {}}


class SearchTests(unittest.TestCase):
    def test_split_is_chronological_latest_third(self):
        rows = [{'event_id': str(i), 'expiry': str(1000+i)} for i in range(61)]
        result = split_events(list(reversed(rows)))
        self.assertEqual(result['development'], [str(i) for i in range(40)])
        self.assertEqual(result['holdout'], [str(i) for i in range(40, 61)])
        with self.assertRaisesRegex(ValueError, '60'):
            split_events(rows[:59])

    def test_volatility_excludes_future_boundary_and_old_candles(self):
        cutoff = 40*86400
        rows = hourly(cutoff)
        expected = realized_vol(rows, cutoff, spec())
        future = candle(cutoff, price=1e100)
        boundary = candle(cutoff-3600, price=1e100)
        boundary[6] = cutoff*1000
        old = candle(cutoff-31*86400, price=1e100)
        self.assertEqual(realized_vol([old]+rows+[boundary, future], cutoff, spec()), expected)
        self.assertGreater(expected, 0)

    def test_spot_model_ignores_future_snapshots_and_uses_known_open(self):
        cutoff = 40*86400
        info = {'cutoff': cutoff, 'expiry': cutoff+1800, 'model_compatible': True,
            'threshold': None, 'strike_ts': cutoff-1800, 'strike_kind': 'open'}
        strike = candle(cutoff-1800, 60, 100)
        snap = {'cutoff': [candle(cutoff-60, 60, 101)], 'strike': [strike]}
        expected = spot_probability(info, snap, hourly(cutoff), spec())
        snap['cutoff'].append(candle(cutoff, 60, 1e100))
        strike[4] = 1e100
        self.assertEqual(spot_probability(info, snap, hourly(cutoff)+[candle(cutoff, price=1e100)], spec()), expected)
        self.assertTrue(0 <= expected <= 1)
        with self.assertRaisesRegex(ValueError, 'Strike not available'):
            spot_probability({**info, 'strike_ts': cutoff}, snap, hourly(cutoff), spec())

    def test_spot_errors_and_missing_data_fail_closed(self):
        cutoff = 40*86400
        info = {'cutoff': cutoff, 'expiry': cutoff+3600, 'model_compatible': True, 'threshold': 100}
        with self.assertRaisesRegex(ValueError, 'Missing cutoff'):
            spot_probability(info, {}, hourly(cutoff), spec())
        with self.assertRaisesRegex(ValueError, 'Insufficient'):
            realized_vol([], cutoff, spec())
        rows = hourly(cutoff)
        rows[-1][0] += 1000
        with self.assertRaisesRegex(ValueError, 'Noncontiguous'):
            realized_vol(rows, cutoff, spec())
        for price in (0, -1, float('nan')):
            with self.assertRaises(ValueError):
                digital(price, 100, .5, 3600)
        with self.assertRaises(ValueError):
            digital(100, 100, .5, 0)
        self.assertEqual(digital(100, 100, 0, 3600), .5)
        self.assertEqual(digital(101, 100, 0, 3600), 1)

    def test_spot_direction_has_strict_fixed_threshold(self):
        protocol = {**spec(), 'spot_threshold': .25}
        self.assertEqual(direction('g_spot_pm', {'p_model': .75, 'p_trade': .5}, None, False, protocol), 0)
        self.assertGreater(direction('g_spot_pm', {'p_model': .8, 'p_trade': .5}, None, False, protocol), 0)
        self.assertLess(direction('g_spot_pm', {'p_model': .2, 'p_trade': .5}, None, False, protocol), 0)

    def test_calibration_has_no_label_or_id_order_lookahead(self):
        history = [{'meeting': f'btc:{9000-i}', 'expiry': 100+i*50, 'resolved': 120+i*50,
            'cutoff': 80+i*50, 'p_trade': .2+i*.2, 'realized': i % 2} for i in range(3)]
        theta, fitted = fit_calibration(history, 'btc:1', 400, spec())
        self.assertTrue(fitted)
        future = {'meeting': 'btc:0', 'expiry': 300, 'resolved': 400,
            'cutoff': 250, 'p_trade': .9, 'realized': 1}
        current = {**future, 'meeting': 'btc:1', 'resolved': 300}
        self.assertEqual(fit_calibration(history+[future, current], 'btc:1', 400, spec())[0], theta)
        future['realized'] = 0
        self.assertEqual(fit_calibration(history+[future], 'btc:1', 400, spec())[0], theta)
        self.assertFalse(fit_calibration([], 'btc:1', 400, spec())[1])

    def test_entry_and_market_probability_are_strictly_point_in_time(self):
        with sqlite3.connect(':memory:') as db:
            search.prior.create_tables(db, {})
            for i, (stamp, price) in enumerate([(99, .2), (100, .3), (101, .4), (200, .5)]):
                db.execute('INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (str(i).encode(), 'm', 'wallet', stamp, 'tx', 'YES', 'BUY', 1, price, 1, price, price, price))
            self.assertEqual(search.prior.prior_price(db, 'm', 100), .2)
            self.assertEqual(search.prior.first_trade(db, 'm', 'YES', 100, 200), (101, .4))
            self.assertIsNone(search.prior.first_trade(db, 'm', 'YES', 101, 200))
        market = {'entries': {'YES': (101, .5), 'NO': (102, .4)}, 'realized': 1}
        self.assertAlmostEqual(search.prior.pm_return(1, market, .02)[0], 1/.52-1)
        self.assertEqual(search.prior.pm_return(-1, market, .02), (-1., True))
        self.assertEqual(search.prior.pm_return(0, market, .02), (0., False))
        market['entries']['YES'] = (101, .98)
        self.assertEqual(search.prior.pm_return(1, market, .02), (0., False))

    def test_date_clusters_balance_contracts_events_and_families(self):
        rows = [{'family': 'btc', 'rid': 'btc:1', 'cluster': 'd1', 'net_return': x} for x in (1, 1)]
        rows += [{'family': 'btc', 'rid': 'btc:2', 'cluster': 'd1', 'net_return': -1},
                 {'family': 'eth', 'rid': 'eth:1', 'cluster': 'd1', 'net_return': 1}]
        np.testing.assert_allclose(cluster_returns(rows), [.5])
        self.assertEqual(metrics([], spec())['metric'], None)
        self.assertEqual(metrics([], spec())['p'], 1.)

    def test_exclusive_lock_rejects_unknown_and_unadvanced_hypotheses(self):
        protocol = spec()
        dev = development(protocol)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lock.json'
            for requested in (['unknown'], ['btc/b_contrarian_pm']):
                with self.assertRaises(ValueError):
                    search.claim_holdout(path, protocol, dev['results'], requested, {})
                self.assertFalse(path.exists())
            search.claim_holdout(path, protocol, dev['results'], dev['advanced'], {})
            with self.assertRaises(FileExistsError):
                search.claim_holdout(path, protocol, dev['results'], dev['advanced'], {})

    def test_changed_inputs_rejected_before_holdout_reads_or_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'development.json').write_text(json.dumps(development(spec())))
            with patch.object(search, 'validate_frozen_commit'), patch.object(search, 'inputs', return_value={'source': 'new'}), patch.object(search, 'prepare') as prepare:
                with self.assertRaisesRegex(ValueError, 'Frozen inputs changed'):
                    search.holdout(root, spec(), root)
                prepare.assert_not_called()
            self.assertFalse((root / 'holdout_lock.json').exists())

    def test_stale_cache_rejected_before_preparation_and_input_hashes(self):
        with patch.object(search, 'validate_cache', side_effect=ValueError('stale cache')), patch.object(search, 'metadata') as metadata:
            for operation in (lambda: search.prepare(Path('/unused'), spec(), 'development'),
                              lambda: search.inputs(Path('/unused'))):
                with self.assertRaisesRegex(ValueError, 'stale cache'):
                    operation()
            metadata.assert_not_called()

    def test_committed_development_hash_prevents_manifest_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'development.json'
            path.write_text('{"frozen": true}\n')
            search.write_csv(root / 'development_manifest.csv', [{'key': 'development_sha256', 'value': search.prior.digest(path)}])
            committed = (root / 'development_manifest.csv').read_bytes()
            with patch.object(search, 'FOLDER', root), patch.object(search, 'committed_text', return_value=committed):
                search.validate_frozen_commit(root)
                path.write_text('{"frozen": false}\n')
                with self.assertRaisesRegex(ValueError, 'freeze changed'):
                    search.validate_frozen_commit(root)

    def test_holdout_only_evaluates_advanced_registered_strategy_once(self):
        protocol = spec()
        row = {'family': 'btc', 'rid': 'btc:2', 'cluster': 'd', 'market_id': 'm', 'net_return': .1, 'traded': 1}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'development.json').write_text(json.dumps(development(protocol)))
            with patch.object(search, 'FOLDER', root), patch.object(search, 'validate_frozen_commit'), patch.object(search, 'inputs', return_value={'source': 'old'}), patch.object(search, 'prepare', return_value=([{'family': 'btc'}], [])), patch.object(search, 'evaluate', return_value=[row]) as evaluate:
                search.holdout(root, protocol, root)
                self.assertEqual(evaluate.call_args.args[0], 'a_smart_pm')
                self.assertEqual(evaluate.call_count, 1)
                with self.assertRaises(FileExistsError):
                    search.holdout(root, protocol, root)
                self.assertEqual(evaluate.call_count, 1)

    def test_crlf_registration_passes_and_content_change_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            canonical = {name: b'locked\n' for name in search.REGISTERED_FILES}
            canonical['registration.json'] = (json.dumps(spec())+'\n').encode()
            for name, content in canonical.items():
                (root / name).write_bytes(content.replace(b'\n', b'\r\n'))
            with patch.object(search, 'FOLDER', root), patch.object(search, 'committed_text', side_effect=lambda name, _: canonical[name]):
                self.assertEqual(search.registration()['search_round'], 4)
                (root / 'registration.json').write_bytes(canonical['registration.json']+b' ')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    search.registration()

    def test_text_hash_normalizes_crlf_but_binary_is_exact(self):
        with tempfile.TemporaryDirectory() as folder:
            for suffix, equal in (('.json', True), ('.sqlite3', False)):
                path = Path(folder) / ('file'+suffix)
                path.write_bytes(b'line\n')
                original = search.prior.digest(path)
                path.write_bytes(b'line\r\n')
                self.assertEqual(search.prior.digest(path) == original, equal)

    def test_development_prepares_all_caches_before_hashing(self):
        protocol = spec()
        row = {'family': 'btc', 'rid': 'btc:1', 'cluster': 'd', 'market_id': 'm', 'net_return': 0., 'traded': 0}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def prepare(*args):
                (root / 'fresh.sqlite3').touch()
                return [], [{'audit': 1}]
            def hashes(*args):
                self.assertTrue((root / 'fresh.sqlite3').exists())
                return {'fresh': search.prior.digest(root / 'fresh.sqlite3')}
            with patch.object(search, 'FOLDER', root), patch.object(search, 'prepare', side_effect=prepare), patch.object(search, 'inputs', side_effect=hashes), patch.object(search, 'evaluate', return_value=[row]):
                search.develop(root, protocol, root)
            frozen = json.loads((root / 'development.json').read_text())
            self.assertIn('fresh', frozen['input_hashes'])


if __name__ == '__main__':
    unittest.main()
