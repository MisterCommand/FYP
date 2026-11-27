"""Label-blind coverage upper bounds; never collect or score market data."""

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
IMPORT_PATH = sys.path.copy()
try:
    sys.path.insert(0, str(REPO / 'models/stock_to_event_search'))
    import archive
finally:
    sys.path[:] = IMPORT_PATH

ROOT = archive.DATA / 'cross_market_macro_search'
FAMILIES = ('payrolls', 'unemployment')
MINIMUM_DEVELOPMENT = 10
MINIMUM_HOLDOUT = 5
DAY = 86400


def utc(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()


def fresh_intervals(stamps, ends, resolved):
    present = set()
    for stamp in stamps:
        if stamp > resolved:
            continue
        index = bisect_left(ends, stamp)
        if 0 < index < len(ends):
            present.add(index)
    return present


def paired_sources(markets, ends, timestamps):
    result = defaultdict(list)
    for market in markets:
        present = fresh_intervals(timestamps[market['market_id']], ends, market['resolved'])
        for index in present:
            if index - 1 in present:
                result[index].append(market)
    return result


def source_at(pairs, index, cutoff):
    return sorted((m for m in pairs.get(index, ())
        if m['release'] > cutoff and m['resolved'] > cutoff), key=lambda m: m['market_id'])


def optional_inventory(markets, releases):
    groups = {'pce': ('pce',), 'gdp': ('gdp',),
        'core_cpi': ('cpi_core_mom', 'cpi_core_yoy')}
    result = []
    for family, kinds in groups.items():
        own = [r for r in releases.values() if r['family'] in kinds]
        stamps = {r['release_ts'] for r in own}
        valid = {releases[m.event_id]['release_ts'] for m in markets.values()
            if releases[m.event_id]['family'] in kinds}
        result.append({'family': family, 'mapped_releases': len(stamps),
            'valid_market_releases_upper_bound': len(valid),
            'decision': 'audit quotes' if len(valid) >= 15 else 'drop: fewer than 15 even before quote eligibility'})
    return result


def analyze(markets, ends, timestamps, splits):
    targets = [m for m in markets if m['family'] in FAMILIES
        and m['event'] in set(splits[m['family']]['development'] + splits[m['family']]['holdout'])]
    source_pairs = {group: paired_sources([m for m in markets if m['family'] == group], ends, timestamps)
        for group in ('fomc', 'cpi')}
    decisions = [stamp + 300 for stamp in ends]
    daily = defaultdict(Counter)
    t1 = {}
    for market in targets:
        event, family = market['event'], market['family']
        phase = 'development' if event in splits[family]['development'] else 'holdout'
        key = family, event, phase
        counts = daily[key]
        counts['contracts'] += 1
        present = fresh_intervals(timestamps[market['market_id']], decisions, market['resolved'])
        for index in sorted(present):
            cutoff = decisions[index]
            if index < 2 or cutoff >= market['release'] or cutoff >= market['resolved']:
                continue
            fed = source_at(source_pairs['fomc'], index, cutoff)
            cpi = source_at(source_pairs['cpi'], index, cutoff)
            counts['target_fresh_contract_days'] += 1
            counts['fed_covered_contract_days'] += bool(fed)
            counts['cpi_covered_contract_days'] += bool(cpi)
            counts['joint_H3_contract_days_upper_bound'] += bool(fed and cpi)
            if index + 1 in present:
                counts['target_H1_contract_days'] += 1
                counts['joint_H1_contract_days_upper_bound'] += bool(fed and cpi)
        cutoff = market['release'] - DAY
        index = bisect_left(ends, cutoff) - 1
        fed = source_at(source_pairs['fomc'], index, cutoff)
        cpi = source_at(source_pairs['cpi'], index, cutoff)
        if key not in t1:
            t1[key] = {'family': family, 'event': event, 'phase': phase,
                'release_utc': utc(market['release']), 'cutoff_utc': utc(cutoff),
                'feature_start_utc': utc(ends[index - 1]) if index >= 1 else '',
                'feature_end_utc': utc(ends[index]) if index >= 1 else '',
                'fed_contracts_upper_bound': len(fed) if index >= 1 else 0,
                'cpi_contracts_upper_bound': len(cpi) if index >= 1 else 0,
                'fed_source_events': ';'.join(sorted({m['event'] for m in fed})),
                'cpi_source_events': ';'.join(sorted({m['event'] for m in cpi})),
                'target_contracts': 0, 'fresh_target_contracts': 0}
        t1[key]['target_contracts'] += 1
        t1[key]['fresh_target_contracts'] += any(cutoff - DAY < ts <= cutoff
            and ts <= market['resolved'] for ts in timestamps[market['market_id']])
    daily_rows, t1_rows = [], []
    fields = ('contracts', 'target_fresh_contract_days', 'target_H1_contract_days',
        'fed_covered_contract_days', 'cpi_covered_contract_days',
        'joint_H1_contract_days_upper_bound', 'joint_H3_contract_days_upper_bound')
    for key in sorted(daily):
        family, event, phase = key
        daily_rows.append({'family': family, 'event': event, 'phase': phase,
            **{name: daily[key][name] for name in fields}})
        row = t1[key]
        row['joint_H2_covered_upper_bound'] = bool(row['fed_contracts_upper_bound']
            and row['cpi_contracts_upper_bound'] and row['fresh_target_contracts'])
        t1_rows.append(row)
    inventory = []
    for family in FAMILIES:
        for hypothesis in ('H1', 'H2', 'H3'):
            row = {'family': family, 'hypothesis': hypothesis}
            for phase in ('development', 'holdout'):
                candidates = [r for r in (t1_rows if hypothesis == 'H2' else daily_rows)
                    if r['family'] == family and r['phase'] == phase]
                field = 'joint_H2_covered_upper_bound' if hypothesis == 'H2' else 'joint_' + hypothesis + '_contract_days_upper_bound'
                row[phase + '_events_upper_bound'] = sum(bool(r[field]) for r in candidates)
            row['proceed'] = (row['development_events_upper_bound'] >= MINIMUM_DEVELOPMENT
                and row['holdout_events_upper_bound'] >= MINIMUM_HOLDOUT)
            inventory.append(row)
    return {'inventory': inventory, 'daily': daily_rows, 't1': t1_rows,
        'proceed': any(row['proceed'] for row in inventory)}


def run(root=ROOT):
    specification = json.loads((REPO / 'models/stock_to_event_search/registration.json').read_text())
    splits = {family: specification['families'][family] for family in FAMILIES}
    calendar = json.loads((archive.DATA / 'stock_to_event_search/SPY.json').read_text())['chart']['result'][0]
    days = sorted({datetime.fromtimestamp(ts, archive.ET).date()
        for ts, price in zip(calendar['timestamp'], calendar['indicators']['quote'][0]['close'])
        if price is not None and datetime.fromtimestamp(ts, archive.ET).date().isoformat() <= '2026-11-25'})
    ends = [archive.close_stamp(day) for day in days]
    markets = archive.population()
    timestamps = {}
    names = {m['db'] for m in markets}
    for name in sorted(names):
        db = archive.readonly(archive.DATA / name)
        try:
            for market in (m for m in markets if m['db'] == name):
                timestamps[market['market_id']] = [row[0] for row in db.execute(
                    'SELECT ts FROM trades WHERE market_id=? ORDER BY ts,dedup_key', (market['market_id'],))]
        finally:
            db.close()
    result = analyze(markets, ends, timestamps, splits)
    optional_markets, releases, _ = archive.macro_coverage.load_metadata(archive.DATA / 'macro')
    result['optional'] = optional_inventory(optional_markets, releases)
    result['splits'] = splits
    result['calendar'] = {'sessions': len(ends), 'first': str(days[0]), 'last': str(days[-1])}
    result['minimum_events'] = {'development': MINIMUM_DEVELOPMENT, 'holdout': MINIMUM_HOLDOUT}
    result['commodity_coverage'] = 'Assumed perfect for this optimistic screen; not downloaded or measured.'
    sources = [archive.DATA / name for name in sorted(names)]
    sources += [archive.DATA / 'stock_to_event_search/SPY.json',
        archive.DATA / 'macro/discovery.json', archive.DATA / 'macro/bea_schedules.md',
        archive.DATA / 'strategy_search/fresh/event.json',
        archive.DATA / 'strategy_search/fresh/606422/summary.json']
    sources += sorted((archive.DATA / 'macro').glob('bls_batch_*.md'))
    code = [FOLDER / 'audit.py', FOLDER / 'test_audit.py',
        REPO / 'models/stock_to_event_search/archive.py',
        REPO / 'models/stock_to_event_search/registration.json',
        REPO / 'models/macro_event_search/registration.json',
        REPO / 'models/macro_event_search/coverage.py', REPO / 'models/macro_event_search/releases.py',
        REPO / 'models/wallet_backtest/build_panel.py', REPO / 'models/wallet_backtest/settlements.csv',
        REPO / 'models/strategy_search/search.py']
    result['data_hashes'] = {str(path.relative_to(archive.DATA)): archive.digest(path) for path in sources}
    result['code_hashes'] = {str(path.relative_to(REPO)): archive.digest(path) for path in code}
    root.mkdir(parents=True, exist_ok=True)
    for name in ('inventory', 'daily', 't1', 'optional'):
        archive.csv_write(FOLDER / (name + '_coverage.csv'), result[name])
    archive.save(root / 'audit.json', result)
    archive.save(FOLDER / 'audit.json', result)
    for row in result['optional']:
        print('Optional:', row)
    for row in result['inventory']:
        print('Coverage upper bound:', row)
    print('Proceed to commodity audit/preregistration:', result['proceed'])
    print('Performance calculations: 0; commodity downloads: 0; existing archives opened read-only.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()
