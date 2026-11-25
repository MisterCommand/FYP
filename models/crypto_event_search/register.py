"""Generate the outcome-blind registry from the committed feasibility screen."""

from datetime import datetime, timezone
import json
import math

from audit import FOLDER, prior

IDS = ('a_smart_pm', 'b_contrarian_pm', 'c_momentum_pm', 'd_calibration_pm',
       'e_late_whale_pm', 'g_spot_pm', 'h_placebo_pm')


def split_events(rows):
    ordered = sorted(rows, key=lambda r: (int(r['expiry']), int(r['event_id'])))
    n = math.ceil(len(ordered) / 3)
    if len(ordered) < 60:
        raise ValueError('Family has fewer than 60 usable events')
    return {'development': [r['event_id'] for r in ordered[:-n]],
        'holdout': [r['event_id'] for r in ordered[-n:]]}


def generate():
    rows = prior.read_csv(FOLDER / 'event_coverage.csv')
    families = [r['family'] for r in prior.read_csv(FOLDER / 'family_coverage.csv') if r['included'] == 'True']
    if not families:
        raise ValueError('No family qualifies; stop after feasibility')
    usable = [r for r in rows if r['usable'] == 'True' and r['family'] in families]
    spec = {'version': 1, 'search_round': 4, 'strategies': IDS,
        'families': {f: split_events([r for r in usable if r['family'] == f]) for f in families},
        'events': {r['family'] + ':' + r['event_id']: {'cutoff': int(r['cutoff']),
            'expiry': int(r['expiry']), 'eligible_contracts': int(r['eligible_contracts']),
            'cluster': datetime.fromtimestamp(int(r['expiry']), timezone.utc).date().isoformat()} for r in usable},
        'cutoff': {'daily_hours_before_observation': 12, 'hourly_minutes_before_observation': 30,
            'weekly_fraction_before_observation': 0.5},
        'flow_lookback_seconds': 7 * 86400, 'momentum_lookback': 'equal to time between cutoff and observation',
        'late_whale_lookback_seconds': 86400, 'large_trade_notional': 1000,
        'pm_cost': 0.02, 'minimum_fit_meetings': 3, 'calibration_l2': 1,
        'favorite_threshold': 0.5, 'longshot_threshold': 0.1,
        'spot_threshold': 0.05, 'spot_vol_days': 30, 'spot_hourly_closes': 720,
        'development_alpha': 0.1, 'holdout_alpha': 0.01, 'seed': 42,
        'monte_carlo_permutations': 65536, 'exact_max_clusters': 16,
        'pooled_strategy': 'a_smart_pm', 'cluster': 'UTC resolution observation date',
        'primary': 'equal-weight resolution-date after-cost ROI, including cash as zero',
        'coverage_sha256': prior.digest(FOLDER / 'event_coverage.csv'),
        'family_coverage_sha256': prior.digest(FOLDER / 'family_coverage.csv'),
        'resolution_sha256': prior.digest(FOLDER / 'contract_resolution.csv')}
    path = FOLDER / 'registration.json'
    with path.open('x') as handle:
        json.dump(spec, handle, indent=2)
        handle.write('\n')
    print('Registered:', {f: {k: len(v) for k, v in split.items()} for f, split in spec['families'].items()})


if __name__ == '__main__':
    generate()
