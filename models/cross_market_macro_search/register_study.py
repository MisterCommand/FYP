"""Freeze round-eight hypotheses and inputs before any performance."""

import json

import inputs


def preregister():
    path = inputs.FOLDER / 'registration.json'
    if any(p.exists() for p in (path, inputs.ROOT / 'development.json', inputs.ROOT / 'holdout_lock.json')):
        raise ValueError('Registration or performance already exists')
    meta = json.loads((inputs.ROOT / 'feasibility.json').read_text())
    if not meta['proceed']:
        raise ValueError('Insufficient feasibility')
    code = [inputs.FOLDER / name for name in ('audit.py', 'test_audit.py', 'inputs.py', 'study.py',
        'register_study.py', 'test_study.py', 'PREREGISTRATION.md', 'FEASIBILITY.md',
        'feasibility.csv', 'asset_coverage.csv', 'source_cutoffs.csv', 'audit.json')]
    inherited = json.loads((inputs.FOLDER / 'audit.json').read_text())['code_hashes']
    code += [inputs.REPO / name for name in inherited if not name.startswith('models/cross_market_macro_search/')]
    spec = {'round': 8, 'registered_hypotheses': 12, 'families': meta['splits'],
        'assets': list(inputs.ASSETS), 'hypotheses': ['H1', 'H2', 'H3'],
        'groups': {'combined': list(inputs.FEATURES), 'commodities': ['oil', 'gold', 'copper']},
        'feature_scales': {name: .01 for name in inputs.FEATURES},
        'L2': 1., 'pm_cost': .02, 'minimum_train_events': 3, 'minimum_test_events': 5,
        'development_alpha': .10, 'holdout_alpha': .01, 'seed': 42,
        'exact_max_events': 16, 'permutations': 10000, 'bootstraps': 10000,
        'inventory': meta['inventory'], 'selected_sources': meta['selected_sources'],
        'asset_coverage': meta['assets'],
        'code_hashes': {str(p.relative_to(inputs.REPO)): inputs.digest(p) for p in code},
        'data_hashes': inputs.sources(inputs.ROOT)}
    inputs.save(path, spec)
    print('Preregistered 12 hypotheses; no performance computed.')


if __name__ == '__main__':
    preregister()
