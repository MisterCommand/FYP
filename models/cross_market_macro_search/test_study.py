"""Synthetic regression tests for input construction, vector fitting and locks."""

from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

import inputs
import register_study
import study


def specification():
    return {'families': {family: {'development': ['d0', 'd1', 'd2', 'd3', 'future'],
        'holdout': ['h0', 'h1']} for family in inputs.FAMILIES},
        'assets': ['combined', 'commodities'], 'hypotheses': ['H1', 'H2', 'H3'],
        'groups': {'combined': list(inputs.FEATURES), 'commodities': ['oil', 'gold', 'copper']},
        'feature_scales': {name: .01 for name in inputs.FEATURES},
        'minimum_train_events': 3, 'minimum_test_events': 5, 'seed': 42,
        'exact_max_events': 16, 'permutations': 10000, 'bootstraps': 10000,
        'L2': 1., 'pm_cost': .02, 'development_alpha': .1, 'holdout_alpha': .01,
        'code_hashes': {}, 'data_hashes': {}}


def row(event='h0', cutoff=100, **kwargs):
    return {'event': event, 'family': 'payrolls', 'cutoff': cutoff, 'next_close': cutoff + 10,
        'release': cutoff + 20, 'resolved': cutoff + 30, 'outcome_key': 'above100',
        'p0': .4, 'p1': .6, 'moves': {name: .01 for name in inputs.FEATURES},
        'placebo': {name: -.01 for name in inputs.FEATURES}, 'realized': 1,
        'entries': {'YES': [cutoff + 1, .4], 'NO': [cutoff + 2, .6]}, **kwargs}


class StudyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / 'output'
        self.output.mkdir()
        for module, name, value in ((inputs, 'ROOT', self.root), (inputs, 'DATA', self.root),
                (inputs, 'FOLDER', self.output), (study, 'FOLDER', self.output)):
            mock = patch.object(module, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.network = patch('urllib.request.urlopen', side_effect=AssertionError('Synthetic only')).start()
        self.addCleanup(patch.stopall)
        self.spec = specification()

    def training(self):
        return [row('d' + str(i), 10 + 20 * i, resolved=25 + 20 * i,
            moves={name: (.01 * (i + 1) if name != 'gold' else -.01 * (i + 1)) for name in inputs.FEATURES},
            p1=.45 + .1 * i) for i in range(3)]

    def test_vector_fit_estimates_separate_coefficients_and_gradient(self):
        x = np.array([[1, 0, 0, 0, 0], [0, 1, 0, 0, 0], [2, -1, 0, 0, 0]], dtype=float)
        beta = study.offset_fit([.5] * 3, x, [1, 0, 1])
        self.assertEqual(beta.shape, (5,))
        self.assertGreater(beta[0], 0)
        self.assertLess(beta[1], 0)
        fitted = np.exp(-np.logaddexp(0, -(x @ beta)))
        np.testing.assert_allclose(x.T @ (fitted - [1, 0, 1]) + beta, 0, atol=1e-8)
        np.testing.assert_allclose(beta[2:], 0)

    def test_local_modules_are_not_shadowed_by_reused_round_six_imports(self):
        expected = Path(__file__).resolve().parent
        self.assertEqual(Path(study.__file__).parent, expected)
        self.assertEqual(Path(register_study.__file__).parent, expected)

    def test_H2_uses_full_vector_even_when_scalar_signal_cancels(self):
        model = MagicMock()
        model.signal.return_value = 0
        model.vector.return_value = np.array([1, -1, 0, 0, 0])
        model.beta_at.return_value = np.array([2, -1, 0, 0, 0])
        with patch.object(study, 'Model', return_value=model):
            result = study.evaluate({'accuracy': [row()]}, self.spec, 'payrolls', 'combined', 'H2', 'holdout')
        adjusted = 1 / (1 + np.exp(-(study.logit(.4) + 3)))
        self.assertAlmostEqual(result['metric'], .6 ** 2 - (adjusted - 1) ** 2)

    def test_vector_fit_empty_invalid_dimensions_labels_and_penalty(self):
        for p, x, y, penalty in (([], [], [], 1), ([.5], [1], [1], 1),
                ([.5], [[1]], [2], 1), ([.5], [[np.nan]], [1], 1),
                ([.5], [[1]], [1], 0), ([.5], [[1]], [1], np.nan)):
            with self.assertRaises(ValueError):
                study.offset_fit(p, x, y, penalty)
        for probability in (-.1, 1.1, np.nan):
            with self.assertRaises(ValueError):
                study.logit(probability)

    def test_development_only_signs_are_causal_and_feature_specific(self):
        training = self.training()
        held = row('h1', 1, resolved=2, p1=.01)
        future = row('future', 1, resolved=200, p1=.01)
        model = study.Model({'daily': training + [held, future], 'accuracy': []}, self.spec, 'payrolls', 'combined')
        signs = model.signs_at(100, 'h0')['above100']
        np.testing.assert_array_equal(signs, [1, 1, 1, -1, 1])
        self.assertEqual(model.signs_at(100, 'd2'), {})
        self.assertEqual(model.signs_at(65, 'h0'), {})

    def test_ablation_has_only_commodity_dimensions_and_own_placebo(self):
        data = {'daily': self.training(), 'accuracy': []}
        model = study.Model(data, self.spec, 'payrolls', 'commodities')
        self.assertEqual(model.move(row()).shape, (3,))
        self.assertEqual(model.vector(row()).shape, (3,))
        control = study.Model(data, self.spec, 'payrolls', 'combined', True)
        np.testing.assert_array_equal(control.move(row()), [-1] * 5)

    def test_beta_uses_only_prior_resolved_events_including_earlier_holdout(self):
        history = [row('d' + str(i), 10 + i, resolved=20 + i) for i in range(3)]
        history += [row('h0', 30, resolved=40), row('future', 90, resolved=200)]
        model = study.Model({'daily': [], 'accuracy': history}, self.spec, 'payrolls', 'combined')
        model.vector = MagicMock(return_value=np.ones(5))
        with patch.object(study, 'offset_fit', return_value=np.ones(5)) as fit:
            model.beta_at(row('h1', 100))
        self.assertEqual(len(fit.call_args.args[0]), 4)
        self.assertEqual(model.vector.call_count, 4)

    def test_unknown_signs_preserve_exact_market_and_cash(self):
        data = {'daily': [], 'accuracy': [row(p0=1, realized=1)], 'trading': [row()]}
        result = study.evaluate(data, self.spec, 'payrolls', 'combined', 'H2', 'holdout')
        self.assertEqual(result['metric'], 0)
        self.assertEqual(result['p'], 1)
        result = study.evaluate(data, self.spec, 'payrolls', 'combined', 'H3', 'holdout')
        self.assertEqual(result['roi'], 0)

    def test_trading_selected_side_cost_and_strict_entry_boundaries(self):
        model = MagicMock()
        model.signal.return_value = 1
        for entry, expected in (([101, .4], 1 / .42 - 1), ([100, .4], 0),
                ([120, .4], 0), ([101, .98], 0), (None, 0)):
            data = {'trading': [row(entries={'YES': entry, 'NO': None})]}
            with patch.object(study, 'Model', return_value=model):
                result = study.evaluate(data, self.spec, 'payrolls', 'combined', 'H3', 'holdout')
            self.assertAlmostEqual(result['roi'], expected)
        model.signal.return_value = -1
        with patch.object(study, 'Model', return_value=model):
            result = study.evaluate({'trading': [row(realized=0)]}, self.spec, 'payrolls', 'combined', 'H3', 'holdout')
        self.assertAlmostEqual(result['roi'], 1 / .62 - 1)

    def test_fixed_effect_regression_cluster_flip_and_empty(self):
        records = [row('event' + str(i), signal=float(i), trained=True,
            p0=.5, p1=float(1 / (1 + np.exp(-.1 * i)))) for i in range(6)]
        result = study.regression(records, self.spec)
        self.assertAlmostEqual(result['metric'], .1)
        self.assertAlmostEqual(result['p'], 1 / 64)
        self.assertIsNotNone(result['cluster_se'])
        self.assertEqual(study.regression([], self.spec)['p'], 1)

    def test_bootstrap_flip_minimum_and_holm(self):
        self.assertEqual(study.flip_p([], self.spec), 1)
        self.assertEqual(study.flip_p([1] * 4, self.spec), 1)
        self.assertAlmostEqual(study.flip_p([1] * 6, self.spec), 1 / 64)
        self.assertEqual(study.paired_bootstrap([], self.spec), (1, None, None))
        p, low, high = study.paired_bootstrap([.1] * 6, self.spec)
        self.assertAlmostEqual(p, 1 / 10001)
        self.assertAlmostEqual(low, .1)
        self.assertAlmostEqual(high, .1)
        self.assertEqual(study.holm({'a': .001, 'b': .02, 'c': .7}), {'a': .003, 'b': .04, 'c': .7})

    def freeze(self, advance=False):
        (self.output / 'registration.json').write_text('{}')
        results = {name: {'metric': None, 'p': 1, 'n_events': 0} for name, *_ in study.names(self.spec)}
        name = 'payrolls/combined/H3'
        if advance:
            results[name] = {'metric': .1, 'p': .01, 'n_events': 6}
        development = {'registration_sha256': inputs.digest(self.output / 'registration.json'),
            'data_hashes': {}, 'code_hashes': {}, 'preregistration_commit': 'freeze',
            'development': results, 'placebo': results, 'advanced': [name] if advance else []}
        inputs.save(self.root / 'development.json', development)
        inputs.save(self.root / 'panel.json', {'daily': [], 'accuracy': [], 'trading': []})
        return development

    def test_exclusive_lock_and_tampered_advancement(self):
        development = self.freeze(True)
        lock = self.root / 'holdout_lock.json'
        with self.assertRaisesRegex(ValueError, 'advancement'):
            study.claim(lock, {**development, 'advanced': []}, self.spec)
        self.assertFalse(lock.exists())
        study.claim(lock, development, self.spec)
        with self.assertRaises(FileExistsError):
            study.claim(lock, development, self.spec)

    def test_empty_advancement_never_calls_holdout_evaluator(self):
        self.freeze()
        with patch.object(study.subprocess, 'check_output', return_value=(self.root / 'development.json').read_bytes()), patch.object(study, 'evaluate') as evaluate:
            study.holdout(self.spec, 'freeze')
        evaluate.assert_not_called()
        held = json.loads((self.output / 'holdout.json').read_text())
        self.assertEqual(held['results'], {})
        self.assertEqual(held['placebo'], {})
        self.assertEqual(held['holm'], {})
        with patch.object(study.subprocess, 'check_output', return_value=(self.root / 'development.json').read_bytes()):
            with self.assertRaises(FileExistsError):
                study.holdout(self.spec, 'freeze')

    def test_failed_holdout_claim_is_retained_and_only_advanced_dispatched(self):
        self.freeze(True)
        with patch.object(study.subprocess, 'check_output', return_value=(self.root / 'development.json').read_bytes()), patch.object(study, 'evaluate', side_effect=RuntimeError('synthetic failure')) as evaluate:
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                study.holdout(self.spec, 'freeze')
        self.assertEqual(evaluate.call_count, 1)
        self.assertEqual(evaluate.call_args.args[2:6], ('payrolls', 'combined', 'H3', 'holdout'))
        self.assertEqual(json.loads((self.root / 'holdout_lock.json').read_text())['status'], 'claimed')

    def test_successful_holdout_dispatches_only_advanced_and_holm_is_joint(self):
        development = self.freeze(True)
        second = 'unemployment/commodities/H3'
        development['development'][second] = {'metric': .1, 'p': .02, 'n_events': 6}
        development['advanced'] = sorted(development['advanced'] + [second])
        inputs.save(self.root / 'development.json', development)

        def evaluate(data, spec, family, asset, hypothesis, phase, placebo=False):
            self.assertIn(family + '/' + asset + '/' + hypothesis, development['advanced'])
            self.assertEqual(phase, 'holdout')
            return {'metric': .1, 'p': .001 if family == 'payrolls' else .02, 'n_events': 6}

        with patch.object(study.subprocess, 'check_output', return_value=(self.root / 'development.json').read_bytes()), patch.object(study, 'evaluate', side_effect=evaluate) as dispatch:
            study.holdout(self.spec, 'freeze')
        self.assertEqual(dispatch.call_count, 4)
        held = json.loads((self.output / 'holdout.json').read_text())
        self.assertEqual(held['holm'], {'payrolls/combined/H3': .002, second: .02})
        self.assertEqual(held['passed'], ['payrolls/combined/H3'])

    def test_holdout_requires_committed_unchanged_development(self):
        self.freeze()
        with patch.object(study.subprocess, 'check_output', return_value=b'changed'):
            with self.assertRaisesRegex(ValueError, 'committed'):
                study.holdout(self.spec, 'freeze')
        self.assertFalse((self.root / 'holdout_lock.json').exists())
        with patch.object(study.subprocess, 'check_output', return_value=(self.root / 'development.json').read_bytes()):
            with self.assertRaisesRegex(ValueError, 'Frozen inputs'):
                study.holdout(self.spec, 'different-freeze')

    def test_development_single_freeze_and_twelve_names(self):
        self.assertEqual(len(study.names(self.spec)), 12)
        inputs.save(self.root / 'panel.json', {'daily': [], 'accuracy': [], 'trading': []})
        (self.output / 'registration.json').write_text('{}')
        study.develop(self.spec, 'freeze')
        self.assertEqual(json.loads((self.root / 'development.json').read_text())['advanced'], [])
        with self.assertRaisesRegex(ValueError, 'already frozen'):
            study.develop(self.spec, 'freeze')

    def test_gate_is_strict_and_directional(self):
        values = {'ok': {'metric': .1, 'p': .099}, 'at': {'metric': .1, 'p': .1},
            'negative': {'metric': -.1, 'p': .001}, 'empty': {'metric': None, 'p': 1}}
        self.assertEqual(study.advanced(values, self.spec), ['ok'])

    def test_committed_registration_rejects_changed_code_or_inputs(self):
        implementation = self.root / 'implementation.py'
        implementation.write_text('value = 1\n')
        spec = {**self.spec, 'code_hashes': {'implementation.py': inputs.digest(implementation)}}
        inputs.save(self.output / 'registration.json', spec)
        (self.output / 'PREREGISTRATION.md').write_text('Frozen\n')

        def committed(command, **kwargs):
            return (self.output / command[-1].split('/')[-1]).read_bytes()

        with patch.object(inputs, 'REPO', self.root), patch.object(study, 'git', side_effect=lambda *args: 'false' if args[0] == 'rev-parse' else 'freeze'), patch.object(study.subprocess, 'check_output', side_effect=committed), patch.object(inputs, 'sources', return_value={}):
            self.assertEqual(study.registration()[1], 'freeze')
            implementation.write_text('value = 2\n')
            with self.assertRaisesRegex(ValueError, 'implementation'):
                study.registration()
            implementation.write_text('value = 1\n')
            with patch.object(inputs, 'sources', return_value={'changed': 'hash'}):
                with self.assertRaisesRegex(ValueError, 'source inputs'):
                    study.registration()

    def test_registration_rejects_missing_history_and_repeat_generation(self):
        with patch.object(study, 'git', return_value='true'):
            with self.assertRaisesRegex(ValueError, 'Full Git history'):
                study.registration()
        (self.output / 'registration.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            register_study.preregister()

    def test_source_selection_is_metadata_only_and_no_coverage_fallback(self):
        markets = [row(market_id='1', family='fomc', outcome_key='nochange', outcome='No change', release=100000),
            row(market_id='2', family='cpi', outcome_key='cpi_headline_yoy:>=3%', outcome='≥3%', release=100000),
            row(market_id='3', family='cpi', outcome_key='cpi_headline_yoy:>=4%', outcome='≥4%', release=100000),
            row(market_id='4', family='cpi', outcome_key='cpi_headline_yoy:>=5%', outcome='≥5%', release=200000)]
        selected = inputs.select_sources(markets)
        self.assertEqual([m['market_id'] for m in selected['cpi']], ['3', '4'])
        snapshots = {'1': {1: (1500, .2), 2: (2500, .4)}, '3': {},
            '4': {1: (1500, .2), 2: (2500, .4)}}
        values, provenance = inputs.features_at(selected, snapshots, [1000, 2000, 3000],
            {2: {'oil': 0, 'gold': 0, 'copper': 0}}, 2, 3300)
        self.assertIsNone(values)
        self.assertEqual(provenance['cpi']['market_id'], '3')
        self.assertIsNone(inputs.features_at(selected, snapshots, [1000, 2000, 3000], {}, 2, 3000)[0])

    def test_asset_fetch_creates_parents_and_cached_rerun_makes_no_requests(self):
        target = self.root / 'new' / 'nested'
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"chart": {}}'
        with patch.object(inputs.urllib.request, 'urlopen', return_value=response) as fetch:
            inputs.fetch_assets(target)
        self.assertEqual(fetch.call_count, 3)
        with patch.object(inputs.urllib.request, 'urlopen', side_effect=AssertionError('cached')):
            inputs.fetch_assets(target)
        with patch.object(inputs.urllib.request, 'urlopen', side_effect=OSError('synthetic network')):
            with self.assertRaises(OSError):
                inputs.fetch_assets(self.root / 'failure')

    def test_asset_gaps_are_not_forward_filled_and_bad_closes_fail(self):
        days = [date(2025, 1, 2), date(2025, 1, 3)]
        stamps = [int(inputs.datetime.combine(day, inputs.base.time(10), inputs.base.ET).timestamp()) for day in days]
        data = {'chart': {'result': [{'timestamp': stamps, 'indicators': {'quote': [{'close': [100, None]}]},
            'meta': {'currentTradingPeriod': {'regular': {'end': stamps[1]}}}}]}}
        for symbol in inputs.SYMBOLS.values():
            inputs.save(self.root / (symbol + '.json'), data)
        moves, coverage = inputs.load_assets(self.root, days)
        self.assertEqual(moves, {})
        self.assertTrue(all(row['calendar_missing'] == 1 for row in coverage.values()))
        data['chart']['result'][0]['indicators']['quote'][0]['close'][1] = -1
        inputs.save(self.root / 'USO.json', data)
        with self.assertRaisesRegex(ValueError, 'Invalid/duplicate'):
            inputs.load_assets(self.root, days)

    def test_panel_has_causal_sources_and_same_complete_cases(self):
        ends = [1000, 2000, 3000, 4000, 5000]
        source = [row(market_id='1', family='fomc', event='fed', outcome_key='nochange', outcome='No change', release=100000, resolved=110000),
            row(market_id='2', family='cpi', event='cpi', outcome_key='cpi_headline_yoy:>=3%', outcome='≥3%', release=100000, resolved=110000)]
        markets = [{**m, 'db': 'fixture.sqlite3'} for m in source + [row('d0', market_id='3', outcome='above100', release=90000, resolved=100000)]]
        with sqlite3.connect(self.root / 'fixture.sqlite3') as db:
            db.execute('CREATE TABLE trades(market_id TEXT,ts INTEGER,price REAL,token_outcome TEXT,raw_price REAL,dedup_key TEXT)')
            db.executemany('INSERT INTO trades VALUES (?,?,?,?,?,?)', [(mid, ts, price, 'YES', price, str(ts))
                for mid, quotes in {'1': [(1500, .3), (2500, .4)], '2': [(1500, .2), (2500, .5)], '3': [(2500, .4), (3500, .6)]}.items()
                for ts, price in quotes])
        reference = self.root / 'models/stock_to_event_search'
        reference.mkdir(parents=True)
        inputs.save(reference / 'registration.json', self.spec)
        with patch.object(inputs, 'REPO', self.root), patch.object(inputs, 'calendar', return_value=([], ends)), patch.object(inputs, 'load_assets', return_value=({2: {'oil': .01, 'gold': .02, 'copper': .03}}, {})), patch.object(inputs.base, 'population', return_value=markets), patch('builtins.print'):
            inputs.panel(self.root)
        data = json.loads((self.root / 'panel.json').read_text())
        self.assertEqual([len(data[k]) for k in ('daily', 'trading', 'accuracy')], [1, 1, 1])
        for kind in data:
            item = data[kind][0]
            self.assertLess(item['asset_end'], item['cutoff'])
            self.assertEqual(set(item['moves']), set(inputs.FEATURES))
            self.assertTrue(all(m['release'] > item['cutoff'] and m['current_ts'] <= item['asset_end'] for m in item['sources'].values()))
            self.assertTrue(all(value == 0 for value in item['placebo'].values()))


if __name__ == '__main__':
    unittest.main()
