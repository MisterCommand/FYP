"""Fixed point-in-time signals and date-cluster inference."""

from collections import defaultdict
import math

import numpy as np

from audit import prior


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Nonpositive or nonfinite spot price')
    return value


def realized_vol(hourly, cutoff, spec):
    rows = [r for r in hourly if (cutoff-spec['spot_vol_days']*86400)*1000 <= int(r[6]) < cutoff*1000]
    n = spec['spot_hourly_closes']
    if len(rows) < n:
        raise ValueError('Insufficient trailing volatility history')
    rows = rows[-n:]
    if any(int(b[0])-int(a[0]) != 3600000 for a, b in zip(rows, rows[1:])):
        raise ValueError('Noncontiguous trailing volatility history')
    return float(np.std(np.diff(np.log([positive(r[4]) for r in rows])), ddof=1) * math.sqrt(24*365))


def digital(spot, strike, sigma, seconds):
    spot, strike = positive(spot), positive(strike)
    if not math.isfinite(sigma) or sigma < 0 or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Invalid digital model horizon or volatility')
    if sigma == 0:
        return 1. if spot > strike else 0. if spot < strike else .5
    t = seconds / (365*86400)
    z = (math.log(spot/strike) - .5*sigma*sigma*t) / (sigma*math.sqrt(t))
    return .5 * (1 + math.erf(z / math.sqrt(2)))


def spot_probability(info, snapshot, hourly, spec):
    cutoff = info['cutoff']
    if not info['model_compatible']:
        raise ValueError('Incompatible resolution oracle')
    available = [r for r in snapshot.get('cutoff', []) if int(r[6]) < cutoff*1000]
    if not available:
        raise ValueError('Missing cutoff spot snapshot')
    latest = max(available, key=lambda r: int(r[6]))
    if cutoff*1000-int(latest[6]) > 61000:
        raise ValueError('Stale cutoff spot snapshot')
    strike = info['threshold']
    if strike is None:
        stamp = info['strike_ts']
        if stamp >= cutoff:
            raise ValueError('Strike not available before cutoff')
        if info['strike_kind'] == 'open':
            rows = [r for r in snapshot.get('strike', []) if int(r[0]) == stamp*1000]
            strike = positive(rows[0][1]) if len(rows) == 1 else None
        else:
            rows = [r for r in snapshot.get('strike', []) if stamp*1000-61000 <= int(r[6]) < stamp*1000]
            strike = positive(max(rows, key=lambda r: int(r[6]))[4]) if rows else None
        if strike is None:
            raise ValueError('Missing prior strike snapshot')
    sigma = realized_vol(hourly, cutoff, spec)
    return digital(latest[4], strike, sigma, info['expiry']-cutoff)


def fit_calibration(history, rid, cutoff, spec):
    rows = [{**r, 'meeting': f"{r['expiry']:012d}:{r['meeting']}"} for r in history if r['meeting'] != rid]
    return prior.fit_calibration(rows, f'{cutoff:012d}', cutoff,
        spec['minimum_fit_meetings'], spec['calibration_l2'])


def direction(strategy, market, theta, fitted, spec):
    if strategy == 'g_spot_pm':
        delta = market['p_model'] - market['p_trade']
        return delta if abs(delta) > spec['spot_threshold'] else 0.
    return prior.direction(strategy, market, theta, fitted, spec)


def cluster_returns(records):
    events, families, dates = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in records:
        events[(r['family'], r['rid'], r['cluster'])].append(r['net_return'])
    for (family, _, cluster), values in events.items():
        families[(family, cluster)].append(float(np.mean(values)))
    for (_, cluster), values in families.items():
        dates[cluster].append(float(np.mean(values)))
    return np.array([np.mean(values) for _, values in sorted(dates.items())], dtype=float)


def permutation(values, spec):
    n = len(values)
    if not n:
        return 1.
    observed = float(values.mean())
    exact = n <= spec['exact_max_clusters']
    total = 2**n if exact else spec['monte_carlo_permutations']
    rng, count = np.random.default_rng(spec['seed']), 0
    for start in range(0, total, 4096):
        size = min(4096, total-start)
        signs = (((np.arange(start, start+size, dtype=np.uint64)[:, None] >>
            np.arange(n, dtype=np.uint64)) & 1) * 2).astype(float)-1 if exact else rng.choice([-1., 1.], (size, n))
        null = (signs * values).mean(axis=1)
        count += int(np.sum(null >= observed-1e-12))
    return count/total if exact else (count+1)/(total+1)


def metrics(records, spec):
    values = cluster_returns(records)
    return {'n_clusters': len(values), 'n_events': len({r['rid'] for r in records}),
        'n_contracts': len(records), 'n_trades': sum(r['traded'] for r in records),
        'metric': float(values.mean()) if len(values) else None, 'p': permutation(values, spec)}
