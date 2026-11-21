"""Fixed macro search: committed registration, development freeze, exclusive holdout."""

import argparse
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'models/strategy_search'))
import search as prior
from build_panel import DAY, aggregate_flow, select_cohorts, window_flows, write_csv
from coverage import attach_fomc, load_metadata, raw_fingerprint

PREREG_COMMIT = 'c431fac'
IDS = ('a_smart_pm', 'b_contrarian_pm', 'c_momentum_pm', 'd_calibration_pm',
       'e_late_whale_pm', 'f_uncertainty_spy', 'h_placebo_pm')


def registration():
    for name in ('registration.json', 'PREREGISTRATION.md', 'release_coverage.csv'):
        committed = subprocess.check_output(['git', 'show',
            f'{PREREG_COMMIT}:models/macro_event_search/{name}'], cwd=ROOT)
        if committed.replace(b'\r\n', b'\n') != (FOLDER / name).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError('Committed macro preregistration changed')
    spec = json.loads((FOLDER / 'registration.json').read_text())
    if tuple(spec['strategies']) != IDS:
        raise ValueError('Unregistered strategy registry')
    return spec


def hypotheses(spec):
    return {f'{family}/{strategy}': (family, strategy)
        for family in spec['families'] for strategy in IDS
        if not (strategy == 'f_uncertainty_spy' and family in spec['spy_pooled_only_families'])} | {
        'pooled/' + spec['pooled_strategy']: ('pooled', spec['pooled_strategy'])}


def spy_window(prices, release, cutoff):
    times = [t for t, _ in prices]
    i = bisect_right(times, cutoff)
    day = datetime.fromtimestamp(release, timezone.utc).date()
    exits = [(t, p) for t, p in prices if datetime.fromtimestamp(t, timezone.utc).date() == day]
    if i >= len(prices) or not exits:
        return None
    entry, price = prices[i]
    exit_ts, exit_price = exits[0]
    if entry >= exit_ts or entry >= release:
        return None
    return {'entry': entry, 'exit': exit_ts, 'return': exit_price / price - 1}


def binary_entropy(probabilities):
    if not probabilities:
        raise ValueError('No probabilities for entropy')
    return float(np.mean([-(p * math.log(p) if p else 0.) -
        ((1-p) * math.log(1-p) if p < 1 else 0.) for p in probabilities]) / math.log(2))


def skill_stream(db, requests, allowed):
    if not requests:
        return
    placeholders = ','.join('?' for _ in allowed)
    schemas = {r[1] for r in db.execute('PRAGMA database_list')}
    fomc_sources = ['fomc'] + (['fresh'] if 'fresh' in schemas else [])
    fomc_sql = ' UNION ALL '.join(f"""SELECT t.wallet, MAX(m.resolved_ts,t.ts) eligible,
            t.signed_yes_shares*(m.realized-t.price) pnl, t.notional, 'fomc' family
        FROM {schema}.trades t JOIN {schema}.markets m USING(market_id)""" for schema in fomc_sources)
    query = f"""SELECT wallet, eligible, pnl, notional, family FROM (
        {fomc_sql} UNION ALL
        SELECT t.wallet, MAX(m.resolved_ts,t.ts),
            t.signed_yes_shares*(m.realized-t.price), t.notional,
            SUBSTR(m.event_id,1,INSTR(m.event_id,':')-1)
        FROM main.trades t JOIN main.markets m USING(market_id)
        WHERE m.event_id IN ({placeholders})
        ) WHERE eligible<? ORDER BY eligible"""
    stream = iter(db.execute(query, tuple(sorted(allowed)) + (max(r['cutoff'] for r in requests),)))
    current = next(stream, None)
    history = defaultdict(lambda: defaultdict(lambda: [0, 0., 0.]))
    for request in sorted(requests, key=lambda r: (r['cutoff'], r['rid'], r['days'])):
        while current is not None and current[1] < request['cutoff']:
            wallet, _, pnl, gross, family = current
            values = history[family][wallet]
            values[0] += 1
            values[1] += pnl
            values[2] += gross
            current = next(stream, None)
        base, own = history['fomc'], history[request['family']]
        scores = {}
        for wallet in base.keys() | own.keys():
            a, b = base.get(wallet, (0, 0., 0.)), own.get(wallet, (0, 0., 0.))
            n, pnl, gross = (a[i] + b[i] for i in range(3))
            if n >= 5 and gross > 0:
                scores[wallet] = {'score': pnl / gross * n / (n + 20), 'n_trades': n}
        yield request, scores


def validate_macro_cache(root):
    fingerprint = raw_fingerprint(root)
    with prior.readonly(root / 'trades.sqlite3') as db:
        recorded = db.execute('SELECT fingerprint FROM build').fetchone()
    if recorded is None or recorded[0] != fingerprint:
        raise ValueError('Macro cache source fingerprint changed')
    return fingerprint


def prepare(root, spec, phase, needed=None):
    validate_macro_cache(root)
    markets, releases, _ = load_metadata(root)
    registered = {f'{f}:{ref}' for f, split in spec['families'].items()
        for ref in split['development'] + (split['holdout'] if phase == 'holdout' else [])}
    selected = {f'{f}:{ref}' for f, split in spec['families'].items()
        for ref in split[phase] if needed is None or f in needed}
    coverage = {r['release_id']: r for r in prior.read_csv(FOLDER / 'release_coverage.csv')}
    prices = prior.load_prices(ROOT / 'datasets/index_daily.csv')
    requests = []
    for rid in selected:
        info, row = releases[rid], coverage[rid]
        for days in spec['cutoff_days']:
            if not int(row[f'eligible_markets_t{days}']) or int(row[f'n_smart_t{days}']) < 20:
                continue
            requests.append({'rid': rid, 'family': info['family'], 'days': days,
                'cluster': info['release_utc'], 'release': info['release_ts'],
                'cutoff': info['release_ts'] - days * DAY})
    states, audit = [], []
    with prior.readonly(root / 'trades.sqlite3') as db:
        attach_fomc(db, root)
        fresh, _, _ = prior.fresh_cache(root.parent)
        if fresh:
            db.execute('ATTACH DATABASE ? AS fresh', (fresh.resolve().as_uri() + '?mode=ro',))
        for request, scores in skill_stream(db, requests, registered):
            rid, cutoff = request['rid'], request['cutoff']
            window = spy_window(prices, request['release'], cutoff)
            smart, placebo = select_cohorts(scores, rid, cutoff, spec['seed'])
            if smart is None:
                raise ValueError('Registered horizon lost its smart set')
            contracts = []
            for market in sorted((m for m in markets.values() if m.event_id == rid), key=lambda m: m.market_id):
                mid = market.market_id
                p = prior.prior_price(db, mid, cutoff)
                entries = {side: prior.first_trade(db, mid, side, cutoff, request['release']) for side in ('YES', 'NO')}
                if p is None or not all(entries.values()):
                    continue
                flows = window_flows(db, mid, cutoff)
                late = db.execute('''SELECT SUM(signed_yes_notional), SUM(notional) FROM trades
                    WHERE market_id=? AND ts>=? AND ts<? AND notional>=?''',
                    (mid, cutoff-DAY, cutoff, spec['large_trade_notional'])).fetchone()
                contracts.append({'meeting': rid, 'market_id': mid, 'cutoff': cutoff,
                    'resolved': market.resolved_ts, 'realized': market.realized, 'p_trade': p,
                    'p_previous': prior.prior_price(db, mid, cutoff-7*DAY), 'entries': entries,
                    'late_whale': late[0]/late[1] if late[1] else 0.,
                    **{name: aggregate_flow(flows, members)['signal'] for name, members in
                        (('smart', smart), ('placebo', placebo), ('all', None))}})
                audit.append({'family': request['family'], 'release_id': rid, 'days': request['days'],
                    'market_id': mid, 'cutoff': cutoff, 'release': request['release'],
                    'yes_entry': entries['YES'][0], 'no_entry': entries['NO'][0],
                    'yes_price': entries['YES'][1], 'no_price': entries['NO'][1],
                    'p_trade': p, 'smart': contracts[-1]['smart'], 'placebo': contracts[-1]['placebo'],
                    'all': contracts[-1]['all'], 'n_smart': len(smart),
                    'spy_entry': window['entry'] if window else '',
                    'spy_exit': window['exit'] if window else ''})
            if not contracts:
                raise ValueError('Registered horizon lost all contracts')
            states.append({**request, 'markets': contracts,
                'window': window})
            print(phase, rid, f't-{request["days"]}', len(contracts), 'contracts;', len(smart), 'smart', flush=True)
    return states, audit


def evaluate(strategy, states, spec, frozen=None):
    if strategy not in IDS:
        raise ValueError('Unregistered strategy')
    records, history = [], defaultdict(list)
    for state in sorted(states, key=lambda s: (s['cutoff'], s['rid'])):
        family, rid = state['family'], state['rid']
        if frozen is None:
            theta, fitted = prior.fit_calibration(history[family], rid, state['cutoff'],
                spec['minimum_fit_meetings'], spec['calibration_l2'])
        else:
            fit = frozen[f'{family}/{state["days"]}']
            theta, fitted = fit['theta'], fit['fitted']
        common = {'family': family, 'release_id': rid, 'days': state['days'], 'cluster': state['cluster']}
        if strategy.endswith('_pm'):
            for market in state['markets']:
                sign = prior.direction(strategy, market, theta, fitted, spec)
                value, traded = prior.pm_return(sign, market, spec['pm_cost'])
                records.append({**common, 'market_id': market['market_id'], 'net_return': value,
                    'benchmark_return': 0., 'traded': int(traded)})
        elif state['window']:
            entropy = binary_entropy([m['p_trade'] for m in state['markets']])
            disagreement = float(np.mean([m['smart'] * m['all'] < 0 for m in state['markets']]))
            exposure = spec['reduced_exposure'] if entropy >= spec['entropy_threshold'] or disagreement >= spec['disagreement_threshold'] else 1.
            net = state['window']['return'] - 2 * spec['spy_cost_per_side']
            records.append({**common, 'market_id': 'SPY', 'net_return': exposure * net,
                'benchmark_return': net, 'traded': int(exposure > 0)})
        history[family].extend(state['markets'])
    return records


def cluster_pairs(records):
    horizons = defaultdict(list)
    for r in records:
        horizons[(r['family'], r['release_id'], r['cluster'], r['days'])].append(r)
    events = defaultdict(list)
    for (family, rid, cluster, _), rows in horizons.items():
        events[(family, rid, cluster)].append((np.mean([r['net_return'] for r in rows]),
            np.mean([r['benchmark_return'] for r in rows])))
    clusters = defaultdict(list)
    for (_, _, cluster), pairs in events.items():
        clusters[cluster].append(np.mean(pairs, axis=0))
    return np.array([np.mean(pairs, axis=0) for _, pairs in sorted(clusters.items())]).reshape(-1, 2)


def permutation(strategy, pairs, spec):
    n = len(pairs)
    if not n:
        return 1.
    observed = prior.statistic(strategy, pairs[:, 0], pairs[:, 1])
    exact = n <= spec['exact_max_clusters']
    total = 2**n if exact else spec['monte_carlo_permutations']
    rng, count = np.random.default_rng(spec['seed']), 0
    for start in range(0, total, 4096):
        size = min(4096, total-start)
        signs = (((np.arange(start, start+size, dtype=np.uint64)[:, None] >>
            np.arange(n, dtype=np.uint64)) & 1) * 2).astype(float) - 1 if exact else rng.choice([-1., 1.], (size, n))
        if strategy == 'f_uncertainty_spy':
            a = np.where(signs > 0, pairs[:, 0], pairs[:, 1])
            b = np.where(signs > 0, pairs[:, 1], pairs[:, 0])
            def sharpes(x):
                std = x.std(axis=1, ddof=1) if n > 1 else np.zeros(size)
                return np.divide(x.mean(axis=1), std, out=np.zeros(size), where=std > 1e-15)
            null = sharpes(a) - sharpes(b)
        else:
            null = (signs * (pairs[:, 0]-pairs[:, 1])).mean(axis=1)
        count += int(np.sum(null >= observed-1e-12))
    return count / total if exact else (count+1)/(total+1)


def metrics(strategy, rows, spec):
    pairs = cluster_pairs(rows)
    return {'n_clusters': len(pairs), 'n_family_events': len({r['release_id'] for r in rows}),
        'metric': prior.statistic(strategy, pairs[:, 0], pairs[:, 1]) if len(pairs) else None,
        'p': permutation(strategy, pairs, spec), 'net_mean': float(pairs[:, 0].mean()) if len(pairs) else None,
        'benchmark_mean': float(pairs[:, 1].mean()) if len(pairs) else None,
        'volatility': float(pairs[:, 0].std(ddof=1)) if len(pairs)>1 else None,
        'benchmark_volatility': float(pairs[:, 1].std(ddof=1)) if len(pairs)>1 else None,
        'n_trades': sum(r['traded'] for r in rows)}


def advanced(spec, results):
    return [key for key in hypotheses(spec) if results[key]['metric'] is not None
        and results[key]['metric'] > 0 and results[key]['p'] < spec['development_alpha']]


def claim_holdout(path, spec, development, requested, manifest):
    if not set(requested) <= set(hypotheses(spec)):
        raise ValueError('Unregistered holdout hypothesis')
    if list(requested) != advanced(spec, development):
        raise ValueError('Holdout differs from development gate')
    with Path(path).open('x') as handle:
        json.dump({**manifest, 'advanced': requested, 'status': 'claimed'}, handle, indent=2)


def inputs(root):
    fingerprint = validate_macro_cache(root)
    files = [FOLDER / name for name in ('registration.json', 'PREREGISTRATION.md', 'release_coverage.csv',
        'run_search.py', 'coverage.py', 'releases.py')]
    files += [ROOT / p for p in ('models/strategy_search/search.py', 'models/wallet_backtest/build_panel.py',
        'models/wallet_backtest/backtest.py', 'datasets/index_daily.csv')]
    files += [root / 'trades.sqlite3', root.parent / 'wallet_backtest_cache/trades.sqlite3']
    files += [p for p in (root.parent / 'strategy_search/fresh/trades.sqlite3',
        root.parent / 'strategy_search/fresh/event.json',
        root.parent / 'strategy_search/fresh/606422/summary.json') if p.exists()]
    result = {str(p): prior.digest(p) for p in files}
    result['raw_macro_fingerprint'] = fingerprint
    return result


def develop(root, spec, work):
    if (work / 'development.json').exists():
        raise ValueError('Development is frozen')
    hashes = inputs(root)
    states, audit = prepare(root, spec, 'development')
    by_strategy = {s: evaluate(s, states, spec) for s in IDS}
    results = {key: metrics(s, [r for r in by_strategy[s] if f == 'pooled' or r['family'] == f], spec)
        for key, (f, s) in hypotheses(spec).items()}
    _, releases, _ = load_metadata(root)
    frozen = {}
    for family, split in spec['families'].items():
        history = [m for s in states if s['family'] == family for m in s['markets']]
        for days in spec['cutoff_days']:
            cutoff = min(releases[f'{family}:{ref}']['release_ts'] - days * DAY for ref in split['holdout'])
            theta, fitted = prior.fit_calibration(history, family+':9999', cutoff,
                spec['minimum_fit_meetings'], spec['calibration_l2'])
            frozen[f'{family}/{days}'] = {'theta': theta, 'fitted': fitted, 'before_cutoff': cutoff}
    ranks = {}
    for spy in (False, True):
        keys = [k for k, (_, s) in hypotheses(spec).items() if (s == 'f_uncertainty_spy') == spy]
        keys.sort(key=lambda k: -(results[k]['metric'] if results[k]['metric'] is not None else -math.inf))
        ranks.update({k: i+1 for i, k in enumerate(keys)})
    manifest = {'prereg_commit': PREREG_COMMIT, 'input_hashes': hashes, 'results': results,
        'advanced': advanced(spec, results), 'frozen': frozen, 'ranks': ranks}
    with (work / 'development.json').open('x') as handle:
        json.dump(manifest, handle, indent=2)
    write_csv(FOLDER / 'development_execution.csv', audit)
    write_csv(work / 'development_observations.csv', [dict(strategy=s, **r) for s, rows in by_strategy.items() for r in rows])
    print('Development frozen; advanced hypotheses: ' + (', '.join(manifest['advanced']) or 'none'), flush=True)


def holdout(root, spec, work):
    manifest_path = work / 'development.json'
    dev = json.loads(manifest_path.read_text())
    if dev['input_hashes'] != inputs(root):
        raise ValueError('Frozen inputs changed')
    claim_holdout(work / 'holdout_lock.json', spec, dev['results'], dev['advanced'],
        {'prereg_commit': PREREG_COMMIT, 'development_sha256': prior.digest(manifest_path)})
    registry = hypotheses(spec)
    needed = {registry[k][0] for k in dev['advanced']}
    if 'pooled' in needed:
        needed = set(spec['families'])
    states, audit = prepare(root, spec, 'holdout', needed) if needed else ([], [])
    evaluated, records = {}, []
    for key in dev['advanced']:
        family, strategy = registry[key]
        rows = evaluate(strategy, [s for s in states if family == 'pooled' or s['family'] == family], spec, dev['frozen'])
        evaluated[key] = metrics(strategy, rows, spec)
        records.extend(dict(hypothesis=key, **r) for r in rows)
    adjusted = prior.holm({k: v['p'] for k, v in evaluated.items()})
    summary = []
    for key, (family, strategy) in registry.items():
        d, h = dev['results'][key], evaluated.get(key)
        passed = bool(h and h['metric'] is not None and h['metric'] > 0
            and h['net_mean'] > 0 and adjusted[key] < spec['holdout_alpha'])
        row = {'hypothesis': key, 'family': family, 'strategy': strategy, 'dev_rank': dev['ranks'][key],
            'advanced': key in dev['advanced'], 'status': 'negative-control pass' if passed and strategy == 'h_placebo_pm'
            else 'pass' if passed else 'fail' if h else 'not advanced', 'holm_p': adjusted.get(key, '')}
        for prefix, stats in (('dev', d), ('holdout', h)):
            for name in d:
                row[prefix+'_'+name] = stats[name] if stats else ''
        summary.append(row)
    with (work / 'holdout_results.json').open('x') as handle:
        json.dump({'summary': summary, 'advanced': dev['advanced']}, handle, indent=2)
    write_csv(FOLDER / 'results.csv', summary)
    if audit:
        write_csv(FOLDER / 'holdout_execution.csv', audit)
    if records:
        write_csv(work / 'holdout_observations.csv', records)
    write_csv(FOLDER / 'study_manifest.csv', [{'key': k, 'value': v} for k, v in {
        'prereg_commit': PREREG_COMMIT, 'development_sha256': prior.digest(manifest_path),
        'holdout_lock_sha256': prior.digest(work / 'holdout_lock.json'),
        'code_sha256': prior.digest(__file__), 'advanced': ','.join(dev['advanced'])}.items()])
    report(summary)
    print('Holdout evaluated once; lock retained. Passes: ' +
        (', '.join(r['hypothesis'] for r in summary if r['status'] == 'pass') or 'none'), flush=True)


def report(rows):
    passed = [r for r in rows if r['status'] == 'pass']
    verdict = 'No preregistered strategy established a holdout edge.' if not passed else 'Preregistered holdout passes: ' + ', '.join(r['hypothesis'] for r in passed) + '.'
    lines = ['# Macro event search results', '', '**Verdict: ' + verdict + '**', '',
        'Preregistration commit: `' + PREREG_COMMIT + '`. Macro holdouts were untouched before registration. '
        'No tuning or additional strategies were introduced. The exclusive holdout lock is retained outside git.', '',
        '| Family | Strategy | Dev clusters | Dev metric | Dev p | Holdout clusters | Holdout metric | Holdout p | Holm p | Status |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    def fmt(x):
        return '—' if x is None or x == '' else f'{x:.6g}' if isinstance(x, float) else str(x)
    for r in rows:
        lines.append('| ' + ' | '.join(fmt(r[k]) for k in ('family', 'strategy', 'dev_n_clusters', 'dev_metric',
            'dev_p', 'holdout_n_clusters', 'holdout_metric', 'holdout_p', 'holm_p', 'status')) + ' |')
    lines += ['', '## Interpretation and feasibility', '',
        'PM primary metrics are after-cost mean ROI; f is the nonannualized window-Sharpe difference. '
        'Units are not comparable across those two primary classes. Detailed net means and realized volatilities are in results.csv. '
        'Rows that did not pass development have no holdout performance computed; dashes are not zeros. '
        'h is a negative control, never evidence of smart-wallet skill. The pooled hypothesis is the one registered extra test, smart PM across families.', '',
        'The original common-two-horizon feasibility screen found 19/21/23/21 usable headline MoM/headline YoY/payroll/unemployment events. '
        'Per the registered exception, December 2024 MoM contributes t−1d only: the final counts are **20/21/23/21**, '
        '85 family-events across 46 distinct release timestamps. Family raw participant rows / distinct wallets: '
        'MoM 173,861 / 11,708; YoY 401,695 / 24,338; payrolls 109,366 / 8,480; unemployment 84,407 / 7,512. '
        'Core CPI, PCE and GDP were dropped for fewer than 15 releases; see FEASIBILITY.md for market counts and gaps.', '',
        '## Protocol and limitations', '',
        '- Both horizons are averaged within release, then co-released families within UTC timestamp. '
        'Inference uses exact cluster permutation through 16 timestamps, otherwise 65,536 seeded draws with a plus-one correction.',
        '- Development gate: positive primary and p<0.10. Holdout pass: positive primary and after-cost mean, '
        'Holm-adjusted one-sided p<0.05 across all advanced hypotheses. Small holdouts and multiple testing severely limit power.',
        '- SPY ends October 7, 2026; later windows are missing, never zero. SPY holdout availability before performance was '
        '5/5/7/6 events, so none of the included families required pooled-only SPY status. '
        'Zero-duration or post-announcement entry windows are excluded. Binary entropy is averaged over contracts, not normalized across overlapping buckets.',
        '- Separate binary contracts can overlap. CPI extra-bracket objects are grouped as one release cluster, not independent events. '
        'Timestamp clustering does not remove dependence between nearby, overlapping SPY windows.',
        '- Collection exhausted 128 Gamma objects / 1,041 pages / 973,256 participant records. '
        'Participant records and first-trade marks are not executable order-book quotes; $0.02/share PM and 10bp/side SPY costs are proxies.',
        '- Gamma settlement timestamps are conservative metadata proxies; retention, keyword-search completeness, survivorship, '
        'shutdown cancellations/fallback resolutions, and a single seeded placebo limit generality.',
        '- Calibration is frozen on development; wallet skill updates chronologically using only prior-resolved same-family markets plus FOMC. '
        'No out-of-family macro skill or future outcomes enter features.', '']
    (FOLDER / 'RESULTS.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('develop', 'holdout'))
    parser.add_argument('--data-root', type=Path, default=Path.home() / 'data/polymarket/macro')
    args = parser.parse_args()
    root = args.data_root.resolve()
    if root.is_relative_to(ROOT):
        parser.error('Raw data and locks must remain outside git')
    spec = registration()
    work = root / 'strategy_search'
    work.mkdir(exist_ok=True)
    (develop if args.phase == 'develop' else holdout)(root, spec, work)


if __name__ == '__main__':
    main()
