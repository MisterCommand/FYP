"""Generate the registration from already observed round-four dates only."""

import csv
import json
import math
from pathlib import Path
from statistics import NormalDist
import subprocess

import rule


def summary(rows):
    values = rule.signals.cluster_returns(rows)
    if len(values) < 2:
        raise ValueError('At least two historical dates are required')
    traded = {r['cluster'] for r in rows if int(r['traded'])}
    return {'dates': len(values), 'traded_dates': len(traded), 'trade_rate': len(traded)/len(values),
        'mean_roi': float(values.mean()), 'variance_ddof1': float(values.var(ddof=1))}


def power(stats, fraction):
    effect = stats['mean_roi']*fraction
    if effect <= 0 or stats['variance_ddof1'] <= 0:
        raise ValueError('Positive planning effect and variance are required')
    z = NormalDist().inv_cdf(.99)+NormalDist().inv_cdf(.8)
    n = math.ceil(z*z*stats['variance_ddof1']/effect**2)
    return {'effect': effect, 'N': n, 'expected_traded_dates': n*stats['trade_rate']}


def main():
    relative = 'models/forward_eth_late_whale/registration.json'
    exists = subprocess.run(['git', 'cat-file', '-e', 'HEAD:'+relative], cwd=rule.REPO, capture_output=True)
    if exists.returncode == 0:
        raise ValueError('Registration already committed; never resize or regenerate this study')
    data = Path.home()/'data/polymarket'
    root = data/'crypto/study'
    groups, sources = {}, {}
    for phase, name in [('development', 'development_observations.csv'), ('holdout', 'holdout_observations.csv')]:
        path = root/name
        rows = []
        with path.open() as handle:
            for row in csv.DictReader(handle):
                strategy = row.get('strategy', row.get('hypothesis', '').split('/')[-1])
                if row['family'] == rule.FAMILY and strategy == 'e_late_whale_pm':
                    rows.append({**row, 'net_return': float(row['net_return'])})
        groups[phase] = rows
        sources[str(path.relative_to(data))] = rule.digest(path)
    pooled = summary(groups['development']+groups['holdout'])
    planning, observed = power(pooled, .5), power(pooled, 1.)
    with (rule.FOLDER.parent/'crypto_event_search/event_coverage.csv').open() as handle:
        proof = max((r for r in csv.DictReader(handle) if r['family'] == rule.FAMILY and r['usable'] == 'True'),
                    key=lambda r: int(r['cutoff']))
    original = json.loads((data/'crypto/study/development.json').read_text())
    training = {str(Path(p).relative_to(data)): h for p, h in original['input_hashes'].items()
        if str(p).startswith(str(data)) and ('sqlite3' in p or '/strategy_search/fresh/' in p)}
    training.update(sources)
    code = [str(p.relative_to(rule.REPO)) for p in (rule.FOLDER/'rule.py', rule.FOLDER/'score_forward.py',
        rule.FOLDER/'register_forward.py', rule.FOLDER/'FORWARD_PREREGISTRATION.md')]
    code += ['models/crypto_event_search/'+n for n in ('audit.py', 'markets.py', 'feasibility.py', 'spots.py', 'signals.py', 'event_coverage.csv')]
    code += ['models/strategy_search/search.py', 'models/wallet_backtest/build_panel.py',
        'models/wallet_backtest/backtest.py', 'models/macro_event_search/feasibility.py']
    collectors = ['feasibility/collect_meetings.py', 'feasibility/scripts/scripts/polymarket/collect_pilot.py']
    spec = {'schema': 1, 'search_round': 5, 'strategy': 'e_late_whale_pm', 'family': rule.FAMILY,
        'series_id': '40', 'alpha': .01, 'power': .8, 'N': planning['N'], 'interim_looks': [],
        'freeze_definition': 'committer Unix timestamp of the unique Git commit first adding this registration.json; cutoff strictly greater',
        'data_root': 'data/polymarket/forward_eth_late_whale',
        'late_whale_lookback_seconds': 86400, 'large_trade_notional': 1000, 'pm_cost': .02,
        'cutoff_seconds_before_observation': 43200, 'seed': 42, 'exact_max_clusters': 16, 'monte_carlo_permutations': 65536,
        'test': 'one-sided date-cluster sign-flip, mean ROI > 0, p < .01; first N eligible dates only',
        'cash_dates_in_primary_metric': True,
        'wallet_skill': {'minimum_records': 5, 'shrinkage_records': 20, 'smart_fraction': .1,
            'minimum_smart': 20, 'minimum_qualified': 200, 'score': 'prior settlement PnL/gross*n/(n+20)',
            'sources': 'existing FOMC including October, macro and same ETH daily family only; trades and settlements strictly before cutoff',
            'used_by_e': False},
        'wallet_eligibility_proof': {'cutoff': int(proof['cutoff']), 'qualified_wallets': int(proof['qualifying_wallets']),
            'event_id': proof['event_id'], 'argument': 'Minimum-five/positive-gross qualification is monotone as prior observations accumulate; e never uses scores or ranks.'},
        'historical': {k: summary(v) for k, v in groups.items()} | {'pooled': pooled},
        'planning_half_effect': planning, 'observed_full_effect': observed,
        'power_method': 'Normal approximation: ceil((z_.99+z_.80)^2 * unbiased per-date variance / effect^2); cash dates retained, no extra trade-rate division',
        'historical_eligible_rate': 119/120,
        'training_hashes': training, 'code_hashes': {p: rule.digest(rule.REPO/p) for p in code},
        'collector_hashes': {p: rule.digest(data/p) for p in collectors}}
    if spec['wallet_eligibility_proof']['qualified_wallets'] < 200:
        raise ValueError('Historical wallet universe does not prove common eligibility')
    rule.atomic_json(rule.FOLDER/'registration.json', spec)
    print(json.dumps({k: spec[k] for k in ('N', 'historical', 'planning_half_effect', 'observed_full_effect')}, indent=2))


if __name__ == '__main__':
    main()
