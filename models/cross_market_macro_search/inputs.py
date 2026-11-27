"""Prepare causal combined predictors without computing target performance."""

from bisect import bisect_left
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import re
import urllib.request

import audit

base = audit.archive
FOLDER, REPO, ROOT, DATA = audit.FOLDER, audit.REPO, audit.ROOT, base.DATA
FAMILIES = audit.FAMILIES
ASSETS = ('combined', 'commodities')
FEATURES = ('fed', 'cpi', 'oil', 'gold', 'copper')
SYMBOLS = {'oil': 'USO', 'gold': 'GLD', 'copper': 'CPER'}
digest, save, csv_write = base.digest, base.save, base.csv_write


def calendar():
    data = json.loads((DATA / 'stock_to_event_search/SPY.json').read_text())['chart']['result'][0]
    days = sorted({datetime.fromtimestamp(ts, base.ET).date()
        for ts, price in zip(data['timestamp'], data['indicators']['quote'][0]['close'])
        if price is not None and datetime.fromtimestamp(ts, base.ET).date().isoformat() <= '2026-11-25'})
    return days, [base.close_stamp(day) for day in days]


def fetch_assets(root):
    root.mkdir(parents=True, exist_ok=True)
    sources = {symbol + '.json': 'https://query1.finance.yahoo.com/v8/finance/chart/' + symbol + '?range=5y&interval=1d'
        for symbol in SYMBOLS.values()}
    for name, url in sources.items():
        path = root / name
        if path.exists():
            continue
        request = urllib.request.Request(url, headers={'User-Agent': 'EventLens-research/0.1 (HKUST FYP)'})
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
        json.loads(content)
        temporary = path.with_suffix('.partial')
        temporary.write_bytes(content)
        temporary.replace(path)
    save(root / 'asset_sources.json', sources)


def load_assets(root, days):
    prices, coverage = {}, {}
    for feature, symbol in SYMBOLS.items():
        data = json.loads((root / (symbol + '.json')).read_text())['chart']['result'][0]
        quotes = {}
        for stamp, price in zip(data['timestamp'], data['indicators']['quote'][0]['close']):
            day = datetime.fromtimestamp(stamp, base.ET).date()
            if day.isoformat() > '2026-11-25' or price is None:
                continue
            if not math.isfinite(price) or price <= 0 or day in quotes:
                raise ValueError('Invalid/duplicate ETF close: ' + symbol)
            quotes[day] = price
        prices[feature] = quotes
        coverage[symbol] = {'observations': len(quotes), 'first': str(min(quotes)) if quotes else '',
            'last': str(max(quotes)) if quotes else '', 'calendar_missing': len(set(days) - quotes.keys()),
            'exchange': data['meta'].get('exchangeName'), 'instrument': data['meta'].get('instrumentType'),
            'regular_end_utc': audit.utc(data['meta']['currentTradingPeriod']['regular']['end'])}
    moves = {}
    for index in range(1, len(days)):
        if all(days[index - 1] in quotes and days[index] in quotes for quotes in prices.values()):
            moves[index] = {feature: math.log(quotes[days[index]] / quotes[days[index - 1]])
                for feature, quotes in prices.items()}
    return moves, coverage


def select_sources(markets):
    fed = [m for m in markets if m['family'] == 'fomc' and m['outcome_key'] == 'nochange']
    cpi = [m for m in markets if m['family'] == 'cpi' and m['outcome_key'].startswith('cpi_headline_yoy:')
        and m['outcome'].strip().startswith(('>=', '≥', '>'))]
    selected = []
    for release in sorted({m['release'] for m in cpi}):
        own = [m for m in cpi if m['release'] == release]
        selected.append(min(own, key=lambda m: (-float(re.search(r'-?\d+(?:\.\d+)?', m['outcome'])[0]), int(m['market_id']))))
    return {'fed': sorted(fed, key=lambda m: (m['release'], int(m['market_id']))), 'cpi': selected}


def features_at(selected, snapshots, ends, commodities, index, cutoff):
    values, provenance = {}, {}
    if index < 2 or index not in commodities or ends[index] >= cutoff:
        return None, provenance
    for group, markets in selected.items():
        market = next((m for m in markets if m['release'] > cutoff), None)
        if market is None:
            provenance[group] = {'status': 'no future archived release'}
            continue
        quotes = snapshots[market['market_id']]
        item = {'market_id': market['market_id'], 'event': market['event'], 'outcome': market['outcome'],
            'release': market['release'], 'status': 'missing fresh endpoint'}
        if market['resolved'] > cutoff and index - 1 in quotes and index in quotes:
            previous, current = quotes[index - 1], quotes[index]
            values[group] = current[1] - previous[1]
            item.update(status='available', previous_ts=previous[0], current_ts=current[0])
        provenance[group] = item
    if len(values) != 2:
        return None, provenance
    return {**values, **commodities[index]}, provenance


def panel(root):
    days, ends = calendar()
    commodities, asset_coverage = load_assets(root, days)
    decisions = [stamp + 300 for stamp in ends]
    all_markets = base.population()
    selected = select_sources(all_markets)
    reference = json.loads((REPO / 'models/stock_to_event_search/registration.json').read_text())
    splits = {family: reference['families'][family] for family in FAMILIES}
    targets = [m for m in all_markets if m['family'] in FAMILIES
        and m['event'] in splits[m['family']]['development'] + splits[m['family']]['holdout']]
    snapshots = {}
    for market in selected['fed'] + selected['cpi']:
        db = base.readonly(DATA / market['db'])
        try:
            snapshots[market['market_id']] = base.market_quotes(db, market, ends)[0]
        finally:
            db.close()
    complete = {}
    for index, cutoff in enumerate(decisions):
        values, provenance = features_at(selected, snapshots, ends, commodities, index, cutoff)
        if values is not None:
            complete[index] = values, provenance
    donor_indices = sorted(complete)

    def donor(family, index):
        eligible = [j for j in donor_indices if j < index]
        if not eligible:
            return {name: 0. for name in FEATURES}, None
        value = int(hashlib.sha256(('42|' + family + '|' + str(ends[index])).encode()).hexdigest(), 16)
        other = eligible[value % len(eligible)]
        return complete[other][0], ends[other]

    data = {'daily': [], 'trading': [], 'accuracy': []}
    counts = {family: Counter() for family in FAMILIES}
    cutoff_rows = {}
    for market in targets:
        family = market['family']
        db = base.readonly(DATA / market['db'])
        try:
            target_quotes, entries = base.market_quotes(db, market, decisions)
            for index, quote in sorted(target_quotes.items()):
                cutoff = decisions[index]
                if index < 2 or cutoff >= market['release']:
                    continue
                counts[family]['fresh_target_days'] += 1
                if index not in complete:
                    counts[family]['missing_combined_predictor_days'] += 1
                    continue
                values, provenance = complete[index]
                placebo, donor_end = donor(family, index)
                row = {**market, 'cutoff': cutoff, 'p0_ts': quote[0], 'p0': quote[1],
                    'moves': values, 'placebo': placebo, 'donor_end': donor_end,
                    'asset_start': ends[index - 1], 'asset_end': ends[index], 'sources': provenance,
                    'entries': {side: entries.get((index, side)) for side in ('YES', 'NO')}}
                data['trading'].append(row)
                if index + 1 in target_quotes:
                    following = target_quotes[index + 1]
                    data['daily'].append({**row, 'next_close': decisions[index + 1],
                        'p1_ts': following[0], 'p1': following[1]})
                else:
                    counts[family]['missing_next_target_day'] += 1
            cutoff = market['release'] - 86400
            index = bisect_left(ends, cutoff) - 1
            values, provenance = features_at(selected, snapshots, ends, commodities, index, cutoff)
            quote = db.execute('SELECT ts,price FROM trades WHERE market_id=? AND ts<=? AND ts>? '
                'ORDER BY ts DESC,dedup_key DESC LIMIT 1', (market['market_id'], cutoff, cutoff - 86400)).fetchone()
            key = family, market['event']
            if key not in cutoff_rows:
                cutoff_rows[key] = {'family': family, 'event': market['event'],
                    'phase': 'development' if market['event'] in splits[family]['development'] else 'holdout',
                    'release_utc': audit.utc(market['release']), 'cutoff_utc': audit.utc(cutoff),
                    'feature_end_utc': audit.utc(ends[index]) if index >= 2 else '',
                    'fed': provenance.get('fed', {}).get('status', 'no completed commodity window'),
                    'fed_market': provenance.get('fed', {}).get('market_id', ''),
                    'cpi': provenance.get('cpi', {}).get('status', 'no completed commodity window'),
                    'cpi_market': provenance.get('cpi', {}).get('market_id', ''),
                    'combined_predictors': values is not None, 'target_fresh_contracts': 0}
            cutoff_rows[key]['target_fresh_contracts'] += quote is not None
            if values is None or quote is None:
                counts[family]['missing_combined_or_target_accuracy_contracts'] += 1
                continue
            placebo, donor_end = donor(family, index)
            data['accuracy'].append({**market, 'cutoff': cutoff, 'p0_ts': quote[0], 'p0': quote[1],
                'moves': values, 'placebo': placebo, 'donor_end': donor_end,
                'asset_start': ends[index - 1], 'asset_end': ends[index], 'sources': provenance})
        finally:
            db.close()
    inventory = []
    for family in FAMILIES:
        for hypothesis, source in (('H1', 'daily'), ('H2', 'accuracy'), ('H3', 'trading')):
            rows = [r for r in data[source] if r['family'] == family]
            item = {'family': family, 'hypothesis': hypothesis, 'contracts_or_days': len(rows)}
            for phase in ('development', 'holdout'):
                item[phase + '_events'] = len({r['event'] for r in rows if r['event'] in splits[family][phase]})
            item['feasible'] = item['development_events'] >= 10 and item['holdout_events'] >= 5
            inventory.append(item)
    meta = {'inventory': inventory, 'splits': splits, 'assets': asset_coverage,
        'missing': counts, 'proceed': any(row['feasible'] for row in inventory),
        'selected_sources': {group: [{key: m[key] for key in ('event', 'market_id', 'outcome', 'release')}
            for m in markets] for group, markets in selected.items()}}
    save(root / 'panel.json', data)
    save(root / 'feasibility.json', meta)
    csv_write(FOLDER / 'feasibility.csv', inventory)
    csv_write(FOLDER / 'source_cutoffs.csv', [cutoff_rows[key] for key in sorted(cutoff_rows)])
    csv_write(FOLDER / 'asset_coverage.csv', [{'symbol': symbol, **row} for symbol, row in asset_coverage.items()])
    print(json.dumps(meta, indent=2))
    print('Performance calculations: 0; source selection uses metadata and availability only.')
    return meta


def sources(root):
    audit_inputs = json.loads((FOLDER / 'audit.json').read_text())['data_hashes']
    paths = [DATA / name for name in audit_inputs]
    paths += [DATA / 'stock_to_event_search/NYSE.html']
    paths += [root / name for name in ('USO.json', 'GLD.json', 'CPER.json',
        'asset_sources.json', 'panel.json', 'feasibility.json')]
    return {str(path.relative_to(DATA)): digest(path) for path in paths}


if __name__ == '__main__':
    fetch_assets(ROOT)
    panel(ROOT)
