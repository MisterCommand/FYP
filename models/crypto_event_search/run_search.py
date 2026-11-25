"""Registered crypto development freeze and exclusive one-shot holdout."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess

from audit import (FOLDER, attach_prior as attach_prior_sources, metadata, prior, skill_stream, validate_cache,
                   write_csv)
from build_panel import aggregate_flow, select_cohorts, window_flows
from register import IDS
from signals import direction, fit_calibration, metrics, spot_probability

ROOT = FOLDER.parents[1]
PREREG_COMMIT = '93662d3c6bdf8ee271af9a2dfe3c788b12b56597'
REGISTERED_FILES = ('registration.json', 'PREREGISTRATION.md', 'event_coverage.csv',
                    'family_coverage.csv', 'contract_resolution.csv', 'register.py')


def committed_text(name, commit):
    return subprocess.check_output(['git', 'show', f'{commit}:models/crypto_event_search/{name}'], cwd=ROOT).replace(b'\r\n', b'\n')


def registration():
    for name in REGISTERED_FILES:
        if committed_text(name, PREREG_COMMIT) != (FOLDER / name).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError('Committed crypto preregistration changed')
    spec = json.loads((FOLDER / 'registration.json').read_text())
    if tuple(spec['strategies']) != IDS or spec['search_round'] != 4 or spec['holdout_alpha'] != .01:
        raise ValueError('Unregistered crypto protocol')
    return spec


def hypotheses(spec):
    return {f'{family}/{strategy}': (family, strategy) for family in spec['families'] for strategy in IDS} | {
        'pooled/' + spec['pooled_strategy']: ('pooled', spec['pooled_strategy'])}


def require_october_history(root):
    fresh, _, reason = prior.fresh_cache(root.parent)
    if fresh is None:
        raise ValueError('Registered October FOMC history is required: ' + reason)


def attach_prior(db, root):
    require_october_history(root)
    attach_prior_sources(db, root)
    if 'fresh' not in {row[1] for row in db.execute('PRAGMA database_list')}:
        raise ValueError('Registered October FOMC history disappeared during attachment')


def prepare(root, spec, phase, needed=None):
    validate_cache(root)
    markets, details, _ = metadata(root)
    selected = {f'{family}:{eid}' for family, split in spec['families'].items()
        if needed is None or family in needed for eid in split[phase]}
    info_by_rid = {d['rid']: d for d in details.values()}
    snapshots = json.loads((root / 'spot/snapshots.json').read_text())
    hourly = {s: json.loads((root / f'spot/{s}_hourly.json').read_text()) for s in ('BTCUSDT', 'ETHUSDT')}
    requests = []
    for rid in selected:
        info, registered = info_by_rid[rid], spec['events'][rid]
        if info['cutoff'] != registered['cutoff'] or info['expiry'] != registered['expiry']:
            raise ValueError('Registered event timing changed')
        requests.append({**info, 'cluster': registered['cluster']})
    states, audit = [], []
    with prior.readonly(root / 'trades.sqlite3') as db:
        attach_prior(db, root)
        for info, scores in skill_stream(db, requests, with_pnl=True):
            rid, cutoff = info['rid'], info['cutoff']
            smart, placebo = select_cohorts(scores, rid, cutoff, spec['seed'])
            if smart is None:
                raise ValueError('Registered event lost its smart set')
            contracts = []
            for market in sorted((m for m in markets.values() if m.event_id == rid), key=lambda m: m.market_id):
                mid = market.market_id
                p = prior.prior_price(db, mid, cutoff)
                entries = {side: prior.first_trade(db, mid, side, cutoff, info['expiry']) for side in ('YES', 'NO')}
                if p is None or not all(entries.values()):
                    continue
                flows = window_flows(db, mid, cutoff)
                late = db.execute('''SELECT SUM(signed_yes_notional), SUM(notional) FROM trades
                    WHERE market_id=? AND ts>=? AND ts<? AND notional>=?''',
                    (mid, cutoff-spec['late_whale_lookback_seconds'], cutoff, spec['large_trade_notional'])).fetchone()
                model = spot_probability(details[mid], snapshots[info['event_id']], hourly[info['symbol']], spec)
                contract = {'meeting': rid, 'market_id': mid, 'cutoff': cutoff,
                    'expiry': info['expiry'], 'resolved': market.resolved_ts,
                    'realized': market.realized, 'p_trade': p, 'p_model': model,
                    'p_previous': prior.prior_price(db, mid, cutoff-(info['expiry']-cutoff)),
                    'entries': entries, 'late_whale': late[0]/late[1] if late[1] else 0.,
                    **{name: aggregate_flow(flows, members)['signal'] for name, members in
                       (('smart', smart), ('placebo', placebo), ('all', None))}}
                contracts.append(contract)
                audit.append({'family': info['family'], 'rid': rid, 'market_id': mid,
                    'cutoff': cutoff, 'expiry': info['expiry'], 'cluster': info['cluster'],
                    'yes_entry': entries['YES'][0], 'no_entry': entries['NO'][0],
                    'yes_price': entries['YES'][1], 'no_price': entries['NO'][1],
                    'p_market': p, 'p_model': model, 'n_smart': len(smart)})
            if len(contracts) != spec['events'][rid]['eligible_contracts']:
                raise ValueError('Registered contract eligibility changed')
            states.append({**info, 'markets': contracts})
            print(phase, rid, len(contracts), 'contracts;', len(smart), 'smart', flush=True)
    return states, audit


def evaluate(strategy, states, spec, frozen=None):
    if strategy not in IDS:
        raise ValueError('Unregistered strategy')
    records, history = [], defaultdict(list)
    for state in sorted(states, key=lambda s: (s['cutoff'], s['rid'])):
        family, rid = state['family'], state['rid']
        if strategy == 'd_calibration_pm':
            if frozen is None:
                theta, fitted = fit_calibration(history[family], rid, state['cutoff'], spec)
            else:
                theta, fitted = frozen[family]['theta'], frozen[family]['fitted']
        else:
            theta, fitted = (0., 1.), False
        for market in state['markets']:
            sign = direction(strategy, market, theta, fitted, spec)
            value, traded = prior.pm_return(sign, market, spec['pm_cost'])
            records.append({'family': family, 'rid': rid, 'cluster': state['cluster'],
                'market_id': market['market_id'], 'net_return': value, 'traded': int(traded)})
        history[family].extend(state['markets'])
    return records


def advanced(spec, results):
    return [key for key in hypotheses(spec) if results[key]['metric'] is not None
        and results[key]['metric'] > 0 and results[key]['p'] < spec['development_alpha']]


def claim_holdout(path, spec, results, requested, manifest):
    if not set(requested) <= set(hypotheses(spec)):
        raise ValueError('Unregistered holdout hypothesis')
    if list(requested) != advanced(spec, results):
        raise ValueError('Holdout differs from development gate')
    with Path(path).open('x') as handle:
        json.dump({**manifest, 'advanced': requested, 'status': 'claimed'}, handle, indent=2)


def inputs(root):
    source = validate_cache(root)
    require_october_history(root)
    files = [FOLDER / name for name in REGISTERED_FILES + ('run_search.py', 'signals.py', 'audit.py',
        'markets.py', 'feasibility.py', 'spots.py')]
    files += [ROOT / p for p in ('models/strategy_search/search.py', 'models/wallet_backtest/build_panel.py',
        'models/wallet_backtest/backtest.py')]
    files += [root / 'trades.sqlite3', root.parent / 'wallet_backtest_cache/trades.sqlite3',
        root.parent / 'macro/trades.sqlite3']
    files += [p for p in (root.parent / 'strategy_search/fresh/trades.sqlite3',
        root.parent / 'strategy_search/fresh/event.json', root.parent / 'strategy_search/fresh/606422/summary.json') if p.exists()]
    return {**{str(p): prior.digest(p) for p in files}, 'crypto_raw_fingerprint': source}


def develop(root, spec, work):
    if (work / 'development.json').exists():
        raise ValueError('Development is frozen')
    states, audit = prepare(root, spec, 'development')
    hashes = inputs(root)
    by_strategy = {s: evaluate(s, states, spec) for s in IDS}
    results = {key: metrics([r for r in by_strategy[s] if f == 'pooled' or r['family'] == f], spec)
        for key, (f, s) in hypotheses(spec).items()}
    frozen = {}
    for family, split in spec['families'].items():
        cutoff = min(spec['events'][family+':'+eid]['cutoff'] for eid in split['holdout'])
        history = [m for state in states if state['family'] == family for m in state['markets']]
        theta, fitted = fit_calibration(history, '', cutoff, spec)
        frozen[family] = {'theta': theta, 'fitted': fitted, 'before_cutoff': cutoff}
    keys = sorted(results, key=lambda k: -(results[k]['metric'] if results[k]['metric'] is not None else -float('inf')))
    manifest = {'prereg_commit': PREREG_COMMIT, 'input_hashes': hashes, 'results': results,
        'advanced': advanced(spec, results), 'frozen': frozen, 'ranks': {k: i+1 for i, k in enumerate(keys)}}
    with (work / 'development.json').open('x') as handle:
        json.dump(manifest, handle, indent=2)
    write_csv(FOLDER / 'development_results.csv', [{'hypothesis': k, 'rank': manifest['ranks'][k], **v} for k, v in results.items()])
    write_csv(FOLDER / 'development_execution.csv', audit)
    write_csv(work / 'development_observations.csv', [dict(strategy=s, **r) for s, rows in by_strategy.items() for r in rows])
    write_csv(FOLDER / 'development_manifest.csv', [{'key': 'development_sha256', 'value': prior.digest(work / 'development.json')},
        {'key': 'prereg_commit', 'value': PREREG_COMMIT}])
    print('Development frozen; advanced hypotheses: ' + (', '.join(manifest['advanced']) or 'none'), flush=True)


def validate_frozen_commit(work):
    name = 'development_manifest.csv'
    if committed_text(name, 'HEAD') != (FOLDER / name).read_bytes().replace(b'\r\n', b'\n'):
        raise ValueError('Development manifest is not committed')
    frozen = {r['key']: r['value'] for r in prior.read_csv(FOLDER / name)}
    if frozen['development_sha256'] != prior.digest(work / 'development.json'):
        raise ValueError('Committed development freeze changed')


def holdout(root, spec, work):
    validate_frozen_commit(work)
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
        evaluated[key] = metrics(rows, spec)
        records.extend(dict(hypothesis=key, **r) for r in rows)
    adjusted = prior.holm({key: value['p'] for key, value in evaluated.items()})
    summary = []
    for key, (family, strategy) in registry.items():
        d, h = dev['results'][key], evaluated.get(key)
        passed = bool(h and h['metric'] is not None and h['metric'] > 0 and d['metric'] > 0 and adjusted[key] < spec['holdout_alpha'])
        row = {'hypothesis': key, 'family': family, 'strategy': strategy, 'dev_rank': dev['ranks'][key],
            'status': 'negative-control pass' if passed and strategy == 'h_placebo_pm' else 'pass' if passed else 'fail' if h else 'not advanced',
            'holm_p': adjusted.get(key, '')}
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
    verdict = 'No preregistered strategy established a holdout edge.' if not passed else 'Registered holdout passes: ' + ', '.join(r['hypothesis'] for r in passed) + '.'
    lines = ['**Verdict: ' + verdict + '**', '', '# Crypto event search — round 4', '',
        'Preregistration commit: `' + PREREG_COMMIT + '`. Crypto holdouts were untouched before registration. '
        'No tuning or additional strategies followed the one-time holdout evaluation; the exclusive lock is retained externally.', '',
        '| Family | Strategy | Dev dates | Dev ROI | Dev p | Holdout dates | Holdout ROI | Raw p | Holm p | Status |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    def fmt(value):
        return '—' if value is None or value == '' else f'{value:.6g}' if isinstance(value, float) else str(value)
    for row in rows:
        lines.append('| ' + ' | '.join(fmt(row[k]) for k in ('family', 'strategy', 'dev_n_clusters', 'dev_metric', 'dev_p',
            'holdout_n_clusters', 'holdout_metric', 'holdout_p', 'holm_p', 'status')) + ' |')
    lines += ['', '## Interpretation and limitations', '',
        '- Primary metric is equal-weight date-cluster after-cost ROI, including cash zeros, not annualized return. '
        'Contracts are averaged within event, events within family/date, then families within date. Event, contract and executed-position counts are in results.csv.',
        '- Development requires positive ROI and one-sided p<0.10. Holdout requires the same positive sign and '
        'Holm-adjusted one-sided p<0.01 across every advanced family/strategy and pooled hypothesis. '
        'This is **round 4 of a search sequence**; stricter alpha does not erase cumulative search risk.',
        '- Dashes mean not evaluated, never zero. Non-advanced holdout strategy performance remains uncomputed. '
        'The sole pooled test is smart-wallet flow. Placebo passes are negative-control warnings, not evidence of skill.',
        '- The sample is at most 120 evenly spread events per identified recurring production family; '
        'see FEASIBILITY.md and the locked coverage CSVs. Weekly families fail the 60-event threshold. '
        'Chainlink TWAP rules and an hourly object in a weekly series are excluded from the aligned Binance sample.',
        '- Three-year retention, recurring-series discovery, survivorship, conservative Gamma settlement-time proxies '
        'and a single seeded placebo limit generality. Date clustering does not remove dependence between nearby dates.',
        '- Per-family split boundaries can differ, so development and holdout dates may overlap across families. '
        'No cross-crypto-family skill/calibration is shared, but phase-specific clustering does not eliminate cross-phase correlation.',
        '- First participant prices are not executable order-book quotes. $0.02/share is the registered flat cost proxy, '
        'not historical fee/spread/slippage/fill reconstruction, including fee-enabled markets. A statistical pass is not proof of executable profit.',
        '- The spot model assumes zero drift/rates and lognormal terminal spot with trailing realized volatility. '
        'It omits volatility risk premia, jumps, intraday seasonality and changing regimes. Only completed pre-cutoff candles '
        'and already-known strike prices enter; no resolution candle close is used as a predictor.',
        '- Calibration is frozen on prior-resolved development events; wallet skill updates only from prior-resolved '
        'FOMC/macro and same-family crypto trades. The earlier FOMC/macro studies are reused training sources, not fresh validation.', '']
    (FOLDER / 'RESULTS.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('develop', 'holdout'))
    parser.add_argument('--data-root', type=Path, default=Path.home() / 'data/polymarket/crypto')
    args = parser.parse_args()
    root = args.data_root.resolve()
    if root.is_relative_to(ROOT):
        parser.error('Raw data and lock must remain outside git')
    spec = registration()
    work = root / 'study'
    work.mkdir(exist_ok=True)
    {'develop': develop, 'holdout': holdout}[args.phase](root, spec, work)


if __name__ == '__main__':
    main()
