"""Synthetic timing, inference, learning and single-look regression fixtures."""

from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import archive
import study


def specification():
    return {'families': {'fomc': {'development': ['e0', 'e1', 'e2', 'e3', 'future'], 'holdout': ['h0', 'h1']}},
        'assets': ['spy', 'rates'], 'hypotheses': ['H1', 'H2', 'H3'], 'asset_scales': {'spy': .01, 'rates': .001},
        'minimum_train_events': 3, 'minimum_test_events': 5, 'seed': 42, 'exact_max_events': 16,
        'permutations': 10000, 'bootstraps': 10000, 'L2': 1., 'pm_cost': .02,
        'development_alpha': .1, 'holdout_alpha': .01, 'code_hashes': {}, 'data_hashes': {}}


def row(event='h0', cutoff=100, **kwargs):
    return {'event': event, 'family': 'fomc', 'cutoff': cutoff, 'next_close': cutoff+10,
        'release': cutoff+20, 'resolved': cutoff+30, 'outcome_key': 'above100', 'p0': .4, 'p1': .6,
        'moves': {'spy': .01, 'rates': -.001}, 'placebo': {'spy': -.01, 'rates': .001},
        'realized': 1, 'entries': {'YES': [cutoff+1, .4], 'NO': [cutoff+2, .6]}, **kwargs}


class StudyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root/'report'
        self.output.mkdir()
        for target, replacement in ((('archive', 'ROOT'), self.root), (('archive', 'DATA'), self.root),
                (('study', 'FOLDER'), self.output)):
            mock = patch.object(archive if target[0] == 'archive' else study, target[1], replacement)
            mock.start()
            self.addCleanup(mock.stop)
        network = patch('urllib.request.urlopen', side_effect=AssertionError('No network in synthetic tests'))
        network.start()
        self.addCleanup(network.stop)

    def quotes(self, trades):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute('CREATE TABLE trades(market_id TEXT,ts INTEGER,price REAL,token_outcome TEXT,raw_price REAL,dedup_key TEXT)')
        db.executemany('INSERT INTO trades VALUES (?,?,?,?,?,?)', [('m', *t) for t in trades])
        return archive.market_quotes(db, {'market_id': 'm', 'release': 50, 'resolved': 60}, [10, 20, 30, 40])

    def test_close_boundaries_and_strict_entry(self):
        snapshots, entries = self.quotes([(10, .3, 'YES', .3, 'a'), (11, .4, 'YES', .4, 'b'),
            (20, .5, 'NO', .5, 'c'), (20, .6, 'YES', .6, 'd'), (21, .7, 'YES', .7, 'e'), (50, .9, 'YES', .9, 'f')])
        self.assertEqual(snapshots[0], (10, .3))
        self.assertEqual(snapshots[1], (20, .6))
        self.assertEqual(entries[0, 'YES'], (11, .4))
        self.assertEqual(entries[1, 'YES'], (21, .7))
        self.assertIsNone(entries[1, 'NO'])
        self.assertNotIn(3, snapshots)

    def test_no_trade_day_stays_missing_and_delayed_entry_is_first(self):
        snapshots, entries = self.quotes([(9, .3, 'YES', .3, 'a'), (31, .8, 'NO', .2, 'b')])
        self.assertEqual(set(snapshots), {0, 3})
        self.assertEqual(entries[0, 'NO'], (31, .2))
        self.assertEqual(entries[1, 'NO'], (31, .2))
        self.assertIsNone(entries[0, 'YES'])
        empty, absent = self.quotes([])
        self.assertEqual(empty, {})
        self.assertTrue(all(v is None for v in absent.values()))

    def test_bad_quote_fails(self):
        with self.assertRaisesRegex(ValueError, 'Invalid archived quote'):
            self.quotes([(12, 1.1, 'YES', .4, 'a')])

    def test_panel_counts_skips_and_chronological_split(self):
        markets = [{**row('e'+str(i), release=60+i, resolved=70+i), 'market_id': 'm'+str(i),
            'outcome': 'above100', 'db': 'fixture.sqlite3'} for i in range(10)]
        with sqlite3.connect(self.root/'fixture.sqlite3') as db:
            db.execute('CREATE TABLE trades(market_id TEXT,ts INTEGER,price REAL,token_outcome TEXT,raw_price REAL,dedup_key TEXT)')
            db.executemany('INSERT INTO trades VALUES (?,?,?,?,?,?)', [(m['market_id'], ts, .5, 'YES', .5, str(ts))
                for m in markets for ts in (9, 19, 29, 49)])
        moves = [{'start': end-10, 'end': end, 'spy': .01, 'rates': .001} for end in (10, 20, 30, 40, 50)]
        with patch.object(archive, 'FAMILIES', ('fomc',)), patch.object(archive, 'population', return_value=markets), patch.object(archive, 'load_assets', return_value=(moves, {})):
            inventory, splits, _ = archive.panel(self.root)
        self.assertEqual(inventory[0]['candidate_market_days'], 30)
        self.assertEqual(inventory[0]['missing_fresh_PM_day'], 20)
        self.assertEqual(inventory[0]['daily_market_windows'], 10)
        self.assertEqual(inventory[0]['trading_market_days'], 30)
        self.assertEqual(inventory[0]['missing_fresh_trading_day'], 10)
        self.assertEqual(inventory[0]['missing_t1_accuracy_quotes'], 10)
        self.assertEqual(splits['fomc']['holdout'], ['e5', 'e6', 'e7', 'e8', 'e9'])
        panel = json.loads((self.root/'panel.json').read_text())
        self.assertTrue(all(r['p0_ts'] <= r['cutoff'] < r['p1_ts'] <= r['next_close'] for r in panel['daily']))

    def test_new_york_dst_closes_and_outcome_keys(self):
        winter = datetime.fromtimestamp(archive.close_stamp(date(2026, 1, 5)), archive.ET)
        summer = datetime.fromtimestamp(archive.close_stamp(date(2026, 6, 5)), archive.ET)
        self.assertEqual(winter.hour, 16)
        self.assertEqual(summer.hour, 16)
        self.assertNotEqual(winter.utcoffset(), summer.utcoffset())
        for early in (date(2023, 7, 3), date(2024, 11, 29), date(2025, 12, 24)):
            self.assertEqual(datetime.fromtimestamp(archive.close_stamp(early), archive.ET).hour, 13)
        self.assertEqual(datetime.fromtimestamp(archive.close_stamp(date(2024, 7, 1)), archive.ET).hour, 16)
        self.assertEqual(archive.outcome_key('25 BPS Decrease'), archive.outcome_key('25bp decrease'))
        self.assertEqual(archive.outcome_key('≥ 50,000'), '>=50000')

    def test_placebo_deterministic_past_different_date(self):
        moves = [{'end': i} for i in range(20)]
        for index in range(1, len(moves)):
            selected = archive.placebo_move(moves, index, 'fomc|'+str(index))
            self.assertEqual(selected, archive.placebo_move(moves, index, 'fomc|'+str(index)))
            self.assertLess(selected['end'], index)
        self.assertIsNone(archive.placebo_move(moves, 0, 'fomc|0'))

    def training(self):
        daily = []
        for event in ('e0', 'e1', 'e2'):
            daily.extend([row(event, cutoff=10, next_close=20, resolved=30, p0=.5, p1=p,
                moves={'spy': x, 'rates': x}, placebo={'spy': -x, 'rates': -x}) for x, p in ((-.01, .4), (.01, .6))])
        daily += [row('future', cutoff=10, next_close=20, resolved=1000, p1=.000001),
            row('h1', cutoff=10, next_close=20, resolved=30, p1=.000001)]
        return {'daily': daily, 'accuracy': []}

    def test_signs_dev_only_prior_resolved_and_prior_target(self):
        data, spec = self.training(), specification()
        model = study.Model(data, spec, 'fomc', 'spy')
        self.assertEqual(model.signs_at(100, 'h0')['above100'], 1)
        self.assertEqual(model.signs_at(30, 'h0'), {})
        self.assertEqual(model.signs_at(20, 'h0'), {})
        self.assertEqual(model.signs_at(100, 'e0'), {})
        self.assertEqual(model.signs_at(100, 'h0').get('unseen', 0), 0)
        placebo = study.Model(data, spec, 'fomc', 'spy', True)
        self.assertEqual(placebo.signs_at(100, 'h0')['above100'], -1)

    def test_offset_l2_gradient_and_errors(self):
        beta = study.offset_fit([.5, .5, .5], [1., 1., 1.], [1, 1, 0])
        probability = 1/(1+np.exp(-beta))
        self.assertAlmostEqual(3*probability-2+beta, 0., places=8)
        self.assertGreater(beta, 0)
        self.assertEqual(study.offset_fit([.5], [0], [1]), 0)
        with self.assertRaises(ValueError):
            study.offset_fit([], [], [])
        with self.assertRaises(ValueError):
            study.offset_fit([.5], [float('nan')], [1])
        with self.assertRaises(ValueError):
            study.logit(1.1)

    def test_walk_forward_beta_uses_only_prior_resolved_labels(self):
        spec = specification()
        prior = [row('e'+str(i), cutoff=10+i, resolved=30+i, realized=0) for i in range(3)]
        prior += [row('h0', cutoff=60, resolved=80, realized=1), row('future', cutoff=10, resolved=100, realized=1),
            row('e3', cutoff=100, resolved=20, realized=1), row('h1', cutoff=20, resolved=30, realized=1)]
        model = study.Model({'daily': [], 'accuracy': prior}, spec, 'fomc', 'spy')
        with patch.object(model, 'signal', return_value=1.), patch.object(study, 'offset_fit', return_value=.3) as fit:
            self.assertEqual(model.beta_at(row('h1', cutoff=100)), .3)
            self.assertEqual(fit.call_args.args[2], [0, 0, 0, 1])

    def test_accuracy_fallback_is_exact_market_including_endpoints(self):
        spec = specification()
        for probability in (0., .3, 1.):
            result = study.evaluate({'daily': [], 'accuracy': [row(p0=probability)]}, spec, 'fomc', 'spy', 'H2', 'holdout')
            self.assertEqual(result['metric'], 0.)
            self.assertEqual(result['p'], 1.)
        for hypothesis in study.HYPOTHESES:
            result = study.evaluate({'daily': [], 'accuracy': [], 'trading': []}, spec, 'fomc', 'spy', hypothesis, 'holdout')
            self.assertIsNone(result['metric'])
            self.assertEqual(result['p'], 1.)

    def test_trading_side_cost_missing_and_pre_release_entry(self):
        spec = specification()
        data = {'daily': [], 'trading': [row()], 'accuracy': []}
        with patch.object(study.Model, 'signal', return_value=1.):
            result = study.evaluate(data, spec, 'fomc', 'spy', 'H3', 'holdout')
            self.assertAlmostEqual(result['roi'], 1/.42-1)
        with patch.object(study.Model, 'signal', return_value=-1.):
            result = study.evaluate(data, spec, 'fomc', 'spy', 'H3', 'holdout')
            self.assertEqual(result['roi'], -1.)
        for entry in (None, [100, .4], [120, .4], [101, .98]):
            data['trading'][0]['entries']['YES'] = entry
            with patch.object(study.Model, 'signal', return_value=1.):
                result = study.evaluate(data, spec, 'fomc', 'spy', 'H3', 'holdout')
                self.assertEqual(result['roi'], 0.)

    def test_brier_paired_bootstrap_and_event_weights(self):
        spec = specification()
        values = [.1, -.02, .08, .1, .03, -.01]
        p, low, high = study.paired_bootstrap(values, spec)
        rng = np.random.default_rng(42)
        means = np.array(values)[rng.integers(0, 6, size=(10000, 6))].mean(axis=1)
        self.assertEqual(p, (1+np.sum(means-np.mean(values) >= np.mean(values)-1e-12))/10001)
        self.assertLess(low, high)
        self.assertEqual(study.paired_bootstrap([], spec), (1., None, None))
        data = {'daily': [], 'accuracy': [row('h0', p0=.5), row('h0', p0=.5), row('h1', p0=.5, realized=0)]}
        with patch.object(study.Model, 'signal', return_value=1.), patch.object(study.Model, 'beta_at', return_value=np.log(3)):
            result = study.evaluate(data, spec, 'fomc', 'spy', 'H2', 'holdout')
        self.assertAlmostEqual(result['metric'], -.0625)
        self.assertAlmostEqual(result['brier_delta'], .0625)

    def test_regression_cluster_se_and_exact_event_p(self):
        spec, rows = specification(), []
        for i in range(8):
            for sign in (-1, 1):
                z = sign*(.2+i/100)
                rows.append(row('cluster'+str(i), p0=.5, p1=1/(1+np.exp(-z)), signal=sign, trained=True))
        result = study.regression(rows, spec)
        self.assertEqual(result['n_events'], 8)
        self.assertAlmostEqual(result['metric'], .235)
        self.assertGreater(result['cluster_se'], 0)
        self.assertEqual(result['p'], 1/256)
        self.assertEqual(study.regression([], spec)['p'], 1.)
        self.assertEqual(study.flip_p([], spec), 1.)

    def test_exact_flip_holm_and_placebo_not_gated(self):
        spec = specification()
        self.assertEqual(study.flip_p([1]*7, spec), 1/128)
        self.assertEqual(study.flip_p([0]*7, spec), 1.)
        self.assertEqual(study.holm({'a': .01, 'b': .03, 'c': .04}), {'a': .03, 'b': .06, 'c': .06})
        self.assertEqual(study.holm({}), {})
        dev = {'a': {'metric': 1., 'p': .099}, 'b': {'metric': -1., 'p': .001}, 'c': {'metric': 1., 'p': .1}}
        self.assertEqual(study.advanced(dev, spec), ['a'])

    def test_crlf_normalized_text_and_streamed_binary_hash(self):
        a, b = self.root/'a.md', self.root/'b.md'
        a.write_bytes(b'a\r\nb\r\n')
        b.write_bytes(b'a\nb\n')
        self.assertEqual(archive.digest(a), archive.digest(b))
        path = self.root/'db.sqlite3'
        value = b'x'*(1024*1024)+b'\r\n'
        path.write_bytes(value)
        self.assertEqual(archive.digest(path), hashlib.sha256(value).hexdigest())
        with self.assertRaises(FileNotFoundError):
            archive.digest(self.root/'absent')

    def frozen(self):
        spec = specification()
        spec.update({'assets': ['spy'], 'hypotheses': ['H3']})
        result = {'metric': .1, 'p': .01, 'n_events': 7, 'n_rows': 7}
        name = 'fomc/spy/H3'
        archive.save(self.output/'registration.json', spec)
        dev = {'advanced': [name], 'development': {name: result}, 'placebo': {name: result},
            'registration_sha256': archive.digest(self.output/'registration.json'),
            'data_hashes': {}, 'code_hashes': {}, 'preregistration_commit': 'freeze'}
        archive.save(self.root/'development.json', dev)
        archive.save(self.root/'panel.json', {})
        return spec, dev

    def test_holdout_claim_before_score_single_use(self):
        spec, _ = self.frozen()
        def score(*args):
            self.assertEqual(json.loads((self.root/'holdout_lock.json').read_text())['status'], 'claimed')
            return {'metric': .2, 'p': .001, 'n_events': 7, 'n_rows': 7}
        with patch.object(study.subprocess, 'check_output', return_value=(self.root/'development.json').read_bytes()), patch.object(study, 'evaluate', side_effect=score) as evaluate:
            study.holdout(spec, 'freeze')
            self.assertEqual(evaluate.call_count, 2)
            with self.assertRaises(FileExistsError):
                study.holdout(spec, 'freeze')
            self.assertEqual(evaluate.call_count, 2)
        self.assertTrue((self.output/'results.csv').exists())
        self.assertEqual(json.loads((self.root/'holdout_lock.json').read_text())['status'], 'complete')

    def test_failed_holdout_keeps_claim_and_frozen_inputs_fail_closed(self):
        spec, dev = self.frozen()
        committed = (self.root/'development.json').read_bytes()
        with patch.object(study.subprocess, 'check_output', return_value=committed), patch.object(study, 'evaluate', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                study.holdout(spec, 'freeze')
            with self.assertRaises(FileExistsError):
                study.holdout(spec, 'freeze')
        dev['data_hashes'] = {'changed': 'source'}
        archive.save(self.root/'development.json', dev)
        with patch.object(study.subprocess, 'check_output', return_value=(self.root/'development.json').read_bytes()):
            with self.assertRaisesRegex(ValueError, 'Frozen inputs changed'):
                study.holdout(spec, 'freeze')

    def test_uncommitted_registration_or_data_change_rejected(self):
        spec, _ = self.frozen()
        (self.output/'PREREGISTRATION.md').write_text('frozen\n')
        def command(*args):
            return 'false' if args[0] == 'rev-parse' else 'commit'
        def show(args, **kwargs):
            return (self.output/args[-1].split('/')[-1]).read_bytes()
        with patch.object(study, 'git', side_effect=command), patch.object(study.subprocess, 'check_output', side_effect=show), patch.object(archive, 'sources', return_value={}):
            self.assertEqual(study.registration()[0], spec)
        with patch.object(study, 'git', side_effect=command), patch.object(study.subprocess, 'check_output', side_effect=show), patch.object(archive, 'sources', return_value={'changed': 'yes'}):
            with self.assertRaisesRegex(ValueError, 'Frozen source inputs changed'):
                study.registration()
        original = (self.output/'registration.json').read_bytes()
        with patch.object(study, 'git', side_effect=command), patch.object(study.subprocess, 'check_output', return_value=original+b'changed'):
            with self.assertRaisesRegex(ValueError, 'Committed preregistration changed'):
                study.registration()


if __name__ == '__main__':
    unittest.main()
