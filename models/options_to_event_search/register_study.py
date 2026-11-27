"""Generate availability tables and pin round-seven inputs, without evaluating performance."""

import argparse
from datetime import datetime, timezone
import json

import archive


def feasibility():
    meta = json.loads((archive.ROOT/'feasibility.json').read_text())
    reference = json.loads((archive.REPO/'models/stock_to_event_search/registration.json').read_text())
    if meta['splits'] != reference['families']:
        raise ValueError('Round-six event population/split changed')
    archive.csv_write(archive.FOLDER/'feasibility.csv', meta['inventory'])
    sources = json.loads((archive.ROOT/'asset_sources.json').read_text())
    archive.csv_write(archive.FOLDER/'asset_coverage.csv', [{'asset': symbol, 'source': sources[symbol+('.json' if symbol == 'MOVE' else '_History.csv')],
        'start': item['start'], 'end': item['end'], 'observations': item.get('daily_closes', item.get('daily_observations')),
        'used': item['used']} for symbol, item in meta['assets'].items()])
    data = json.loads((archive.ROOT/'panel.json').read_text())
    timestamps = {r['event']: r['release'] for kind in ('daily', 'trading', 'accuracy') for r in data[kind]}
    archive.csv_write(archive.FOLDER/'event_split.csv', [{'family': family, 'event': event, 'phase': phase,
        'release_utc': datetime.fromtimestamp(timestamps[event], timezone.utc).isoformat()}
        for family in archive.FAMILIES for phase in ('development', 'holdout') for event in meta['splits'][family][phase]])
    return meta


def preregister():
    path = archive.FOLDER/'registration.json'
    if path.exists() or (archive.ROOT/'development.json').exists() or (archive.ROOT/'holdout_lock.json').exists():
        raise ValueError('Registration already exists or performance execution has begun')
    meta = feasibility()
    code = ['models/options_to_event_search/'+name for name in ('archive.py', 'study.py', 'register_study.py', 'test_study.py',
        'FEASIBILITY.md', 'feasibility.csv', 'asset_coverage.csv', 'event_split.csv')]
    code += ['models/macro_event_search/'+name for name in ('coverage.py', 'releases.py', 'registration.json')]
    code += ['models/wallet_backtest/'+name for name in ('backtest.py', 'build_panel.py', 'settlements.csv')]
    code += ['models/strategy_search/search.py']
    code += ['models/stock_to_event_search/'+name for name in ('registration.json', 'event_split.csv')]
    spec = {'round': 7, 'assets': list(archive.ASSETS), 'hypotheses': ['H1', 'H2', 'H3'],
        'registered_hypotheses': 24, 'families': meta['splits'], 'inventory': meta['inventory'],
        'asset_coverage': meta['assets'], 'asset_scales': {'vix': .01, 'term': .01},
        'predictors': {'vix': 'log(VIX_d/VIX_previous)', 'term': 'log(VIX9D_d/VIX_d)-log(VIX9D_previous/VIX_previous)'},
        'daily_boundary': '16:15 America/New_York; 13:15 on sample early-close sessions',
        'index_source': 'Official CBOE daily closing values; round-six session dates only',
        'excluded_MOVE': 'Five missing dates in original required feature windows; unclear close timing; no MOVE hypothesis',
        'L2': 1., 'pm_cost': .02, 'minimum_train_events': 3, 'minimum_test_events': 5,
        'development_alpha': .10, 'holdout_alpha': .01, 'seed': 42,
        'exact_max_events': 16, 'permutations': 10000, 'bootstraps': 10000,
        'sign_mapping': 'Per canonical outcome, from strictly prior-resolved development events only; never held-out targets.',
        'H1': 'Next-close logit change on signed scaled asset move and outcome fixed effects; event CR1 SE; one-sided event wild-score sign-flip p.',
        'H2': 'Release minus 24h, latest completed asset window; expanding prior-resolved offset logistic with L2=1; earlier held-out labels permitted only after resolution; paired centered event bootstrap.',
        'H3': 'Fresh current-close baseline only; first strictly post-close, pre-release side trade, $0.02/share cost; equal-event ROI including cash; event sign-flip p.',
        'placebo': {'seed': 42, 'encoding': 'SHA256(UTF8("42|" + family + "|" + str(asset_window_end_epoch))) as hex integer modulo current zero-based asset-window index',
            'dates': 'Strictly earlier asset-window dates, common donor date across both assets and all contracts at that family/close.',
            'scope': 'All development controls; holdout controls only for advanced matching main hypotheses. No gate or Holm membership.'},
        'hashing': 'SHA256; CRLF normalized to LF in text; binary databases streamed unchanged.',
        'code_hashes': {name: archive.digest(archive.REPO/name) for name in code},
        'data_hashes': archive.sources(archive.ROOT)}
    archive.save(path, spec)
    print('Preregistered 24 confirmatory hypotheses; no performance computed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('feasibility', 'preregister'))
    arguments = parser.parse_args()
    (feasibility if arguments.phase == 'feasibility' else preregister)()
