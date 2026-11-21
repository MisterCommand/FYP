"""Tests of fixed macro adaptation, timestamp clusters and the holdout firewall."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import run_search as study


def spec():
    return json.loads((study.FOLDER / 'registration.json').read_text())


class ExecutionTests(unittest.TestCase):
    def test_release_close_and_strict_post_cutoff_entry(self):
        release = int(datetime.fromisoformat('2026-07-10T12:30:00+00:00').timestamp())
        prices = [(release-2*86400, 100.), (release-86400, 101.), (release+3*3600, 102.)]
        window = study.spy_window(prices, release, prices[0][0])
        self.assertEqual(window['entry'], prices[1][0])
        self.assertEqual(window['exit'], prices[2][0])
        self.assertAlmostEqual(window['return'], 102/101-1)
        self.assertIsNone(study.spy_window(prices[:-1], release, prices[0][0]))
        self.assertIsNone(study.spy_window(prices, release, prices[1][0]))

    def test_binary_entropy_never_normalizes_overlapping_contracts(self):
        self.assertEqual(study.binary_entropy([0., 1.]), 0.)
        self.assertEqual(study.binary_entropy([.5, .5, .5]), 1.)
        self.assertAlmostEqual(study.binary_entropy([.9, .9]), .46899559358928117)
        with self.assertRaises(ValueError):
            study.binary_entropy([])

    def test_first_trade_and_pre_cutoff_price_boundaries(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute('CREATE TABLE trades (market_id, token_outcome, ts, raw_price, dedup_key)')
        db.executemany('INSERT INTO trades VALUES (?,?,?,?,?)', [
            ('m', 'YES', 9, .2, b'a'), ('m', 'YES', 10, .8, b'b'),
            ('m', 'YES', 11, .4, b'c'), ('m', 'NO', 12, .6, b'd'),
            ('m', 'NO', 20, .1, b'e')])
        self.assertEqual(study.prior.prior_price(db, 'm', 10), .2)
        self.assertEqual(study.prior.first_trade(db, 'm', 'YES', 10, 20), (11, .4))
        self.assertIsNone(study.prior.first_trade(db, 'm', 'NO', 12, 20))

    def test_f_missing_window_is_not_zero_observation(self):
        state = {'family': 'payrolls', 'rid': 'payrolls:2025-01', 'days': 3,
                 'cutoff': 1, 'cluster': 'release', 'window': None, 'markets': []}
        self.assertEqual(study.evaluate('f_uncertainty_spy', [state], spec()), [])
        self.assertIsNone(study.metrics('f_uncertainty_spy', [], spec())['metric'])

    def test_f_binary_uncertainty_reduces_exposure_after_cost(self):
        market = {'meeting': 'payrolls:2025-01', 'resolved': 20, 'cutoff': 1,
                  'realized': 1, 'p_trade': .5, 'smart': 1., 'all': 1.}
        state = {'family': 'payrolls', 'rid': 'payrolls:2025-01', 'days': 3,
                 'cutoff': 1, 'cluster': 'release', 'window': {'return': .1}, 'markets': [market]}
        row = study.evaluate('f_uncertainty_spy', [state], spec())[0]
        self.assertAlmostEqual(row['net_return'], .049)
        self.assertAlmostEqual(row['benchmark_return'], .098)


class SkillAndCalibrationTests(unittest.TestCase):
    def test_stream_excludes_holdout_sources_other_family_and_cutoff_boundaries(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute("ATTACH DATABASE ':memory:' AS fomc")
        for schema in ('main', 'fomc'):
            db.execute(f'CREATE TABLE {schema}.markets (market_id, event_id, resolved_ts, realized)')
            db.execute(f'CREATE TABLE {schema}.trades (market_id, wallet, ts, signed_yes_shares, price, notional)')
        db.executemany('INSERT INTO main.markets VALUES (?,?,?,?)', [
            ('old', 'payrolls:old', 90, 1), ('held', 'payrolls:held', 80, 1),
            ('other', 'unemployment:old', 80, 1), ('future', 'payrolls:future', 100, 1)])
        db.execute("INSERT INTO fomc.markets VALUES ('f','fomc:old',80,1)")
        db.executemany('INSERT INTO main.trades VALUES (?,?,?,?,?,?)',
            [('old', 'eligible', 70, 1, .4, .4)]*3 + [('held', 'held', 70, 1, .4, .4)]*5 +
            [('other', 'foreign', 70, 1, .4, .4)]*5 + [('old', 'late', 100, 1, .4, .4)]*5 +
            [('future', 'unresolved', 70, 1, .4, .4)]*5)
        db.executemany('INSERT INTO fomc.trades VALUES (?,?,?,?,?,?)', [('f', 'eligible', 70, 1, .4, .4)]*2)
        req = [{'family': 'payrolls', 'cutoff': c, 'rid': str(c), 'days': 3} for c in (80, 100, 101)]
        results = list(study.skill_stream(db, req, {'payrolls:old', 'payrolls:future', 'unemployment:old'}))
        self.assertEqual(results[0][1], {})
        self.assertEqual(set(results[1][1]), {'eligible'})
        self.assertAlmostEqual(results[1][1]['eligible']['score'], .3)
        self.assertEqual(set(results[2][1]), {'eligible', 'late', 'unresolved'})

    def test_prior_calibration_rejects_future_current_and_unresolved(self):
        history = [{'meeting': f'payrolls:2025-0{i}', 'cutoff': i, 'resolved': 10,
                    'realized': i % 2, 'p_trade': .2 + i*.1} for i in (1, 2, 3)]
        original = study.prior.fit_calibration(history, 'payrolls:2025-04', 20)
        extra = [dict(history[0], meeting='payrolls:2025-04'),
                 dict(history[0], resolved=20), dict(history[0], cutoff=20),
                 dict(history[0], meeting='payrolls:2025-09')]
        self.assertEqual(original, study.prior.fit_calibration(history+extra, 'payrolls:2025-04', 20))
        self.assertTrue(original[1])

    def test_holdout_calibration_never_refits(self):
        state = {'family': 'payrolls', 'rid': 'payrolls:2026-04', 'days': 3,
                 'cutoff': 1, 'cluster': 'release', 'window': None, 'markets': []}
        with patch.object(study.prior, 'fit_calibration', side_effect=AssertionError('holdout refit')):
            self.assertEqual(study.evaluate('d_calibration_pm', [state], spec(),
                {'payrolls/3': {'theta': [0., 1.], 'fitted': True}}), [])


class InferenceAndLockTests(unittest.TestCase):
    def test_horizons_contracts_and_co_released_families_have_equal_cluster_weight(self):
        def row(family, cluster, days, value):
            return {'family': family, 'release_id': family+cluster, 'cluster': cluster,
                    'days': days, 'net_return': value, 'benchmark_return': 0., 'traded': 1}
        rows = [row('a', 'one', 3, 1.)]*10 + [row('a', 'one', 1, 3.),
                row('b', 'one', 3, 4.), row('a', 'two', 3, -1.)]
        np.testing.assert_allclose(study.cluster_pairs(rows), [[3., 0.], [-1., 0.]])
        self.assertEqual(study.metrics('a_smart_pm', rows, spec())['n_clusters'], 2)

    def test_exact_and_monte_carlo_permutation(self):
        self.assertEqual(study.permutation('a_smart_pm', np.array([[1., 0.]]*5), spec()), 1/32)
        self.assertEqual(study.permutation('a_smart_pm', np.zeros((5, 2)), spec()), 1.)
        self.assertEqual(study.permutation('f_uncertainty_spy', np.array([[1., 1.], [2., 2.]]), spec()), 1.)
        s = spec() | {'exact_max_clusters': 0, 'monte_carlo_permutations': 100}
        p = study.permutation('a_smart_pm', np.array([[1., 0.]]*10), s)
        self.assertGreaterEqual(p, 1/101)
        self.assertEqual(p, study.permutation('a_smart_pm', np.array([[1., 0.]]*10), s))

    def test_lock_registered_gate_and_single_use(self):
        s = spec()
        results = {key: {'metric': -1., 'p': 1.} for key in study.hypotheses(s)}
        good = next(iter(results))
        results[good] = {'metric': .1, 'p': .05}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lock.json'
            for requested in (['unknown/a'], [], [good, 'pooled/a_smart_pm']):
                with self.assertRaises(ValueError):
                    study.claim_holdout(path, s, results, requested, {})
                self.assertFalse(path.exists())
            study.claim_holdout(path, s, results, [good], {})
            with self.assertRaises(FileExistsError):
                study.claim_holdout(path, s, results, [good], {})
        self.assertEqual(len(study.hypotheses(s)), 29)

    def test_registration_and_text_hashes_allow_crlf_not_content_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('registration.json', 'PREREGISTRATION.md', 'release_coverage.csv'):
                data = (study.FOLDER / name).read_bytes().replace(b'\r\n', b'\n')
                (root / name).write_bytes(data.replace(b'\n', b'\r\n'))
                self.assertEqual(study.prior.digest(root / name), study.prior.digest(study.FOLDER / name))
            with patch.object(study, 'FOLDER', root):
                self.assertEqual(study.registration()['version'], 1)
                path = root / 'registration.json'
                path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaises(ValueError):
                    study.registration()

    def test_changed_frozen_inputs_rejected_before_lock_or_holdout_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'development.json').write_text(json.dumps({'input_hashes': {'old': 'hash'}}))
            with patch.object(study, 'inputs', return_value={'new': 'hash'}), \
                    patch.object(study, 'prepare', side_effect=AssertionError('holdout read')):
                with self.assertRaisesRegex(ValueError, 'Frozen inputs changed'):
                    study.holdout(root, spec(), root)
            self.assertFalse((root / 'holdout_lock.json').exists())


if __name__ == '__main__':
    unittest.main()
