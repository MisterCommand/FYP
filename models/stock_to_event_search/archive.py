"""Read only the registered FOMC/macro archives; collect public asset histories."""

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import datetime, time
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import urllib.request
from zoneinfo import ZoneInfo

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
DATA = Path.home()/'data/polymarket'
ROOT = DATA/'stock_to_event_search'
sys.path.insert(0, str(REPO/'models/macro_event_search'))
import coverage as macro_coverage

ET = ZoneInfo('America/New_York')
ASSETS = ('spy', 'rates')
FAMILIES = ('fomc', 'cpi', 'payrolls', 'unemployment')


def outcome_key(value):
    return re.sub(r'\s+', '', value.casefold()).replace('≤', '<=').replace('≥', '>=').replace(',', '').replace('bps', 'bp')


def digest(path):
    result = hashlib.sha256()
    if Path(path).suffix in ('.py', '.json', '.md', '.csv', '.txt', '.html'):
        return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix+'.partial')
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')
    temporary.replace(path)


def csv_write(path, rows):
    if not rows:
        path.write_text('')
        return
    with path.open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)


def close_stamp(day):
    early = ((day.month, day.day) in ((7, 3), (12, 24)) or
        (day.month == 11 and day.weekday() == 4 and 23 <= day.day <= 29))
    return int(datetime.combine(day, time(13 if early else 16), ET).timestamp())


def fetch_assets(root):
    sources = {
        'SPY.json': 'https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=5y&interval=1d',
        'SHY.json': 'https://query1.finance.yahoo.com/v8/finance/chart/SHY?range=5y&interval=1d',
        'DGS2.csv': 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2&cosd=2022-01-01&coed=2026-11-25',
        'H15.html': 'https://www.federalreserve.gov/releases/h15/',
        'NYSE.html': 'https://www.nyse.com/markets/hours-calendars'}
    for name, url in sources.items():
        path = root/name
        if path.exists():
            continue
        request = urllib.request.Request(url, headers={'User-Agent': 'EventLens-research/0.1 (HKUST FYP)'})
        with urllib.request.urlopen(request, timeout=60) as response:
            path.write_bytes(response.read())
    save(root/'asset_sources.json', sources)


def load_assets(root):
    quotes, coverage = {}, {}
    for symbol in ('SPY', 'SHY'):
        data = json.loads((root/(symbol+'.json')).read_text())['chart']['result'][0]
        rows = {}
        for ts, price in zip(data['timestamp'], data['indicators']['quote'][0]['close']):
            if price is None:
                continue
            day = datetime.fromtimestamp(ts, ET).date()
            if day.isoformat() > '2026-11-25':
                continue
            if day in rows or not math.isfinite(price) or price <= 0:
                raise ValueError('Invalid or duplicate asset close')
            rows[day] = float(price)
        quotes[symbol] = rows
        coverage[symbol] = {'start': str(min(rows)), 'end': str(max(rows)), 'daily_closes': len(rows)}
    dates = sorted(quotes['SPY'])
    if set(dates) != set(quotes['SHY']):
        raise ValueError('SPY and SHY trading calendars differ')
    moves = []
    for previous, day in zip(dates, dates[1:]):
        moves.append({'date': str(day), 'start': close_stamp(previous), 'end': close_stamp(day),
            'spy': quotes['SPY'][day]/quotes['SPY'][previous]-1,
            'rates': 1-quotes['SHY'][day]/quotes['SHY'][previous]})
    fred = [r for r in csv.DictReader(io.StringIO((root/'DGS2.csv').read_text())) if r['DGS2'] not in ('', '.')]
    coverage['DGS2'] = {'start': fred[0]['observation_date'], 'end': fred[-1]['observation_date'],
        'daily_observations': len(fred), 'used': False,
        'reason': 'H.15 published after 16:00 ET; use permitted sign-flipped SHY proxy to avoid look-ahead'}
    return moves, coverage


def population():
    result = []
    with (REPO/'models/wallet_backtest/settlements.csv').open() as handle:
        for row in csv.DictReader(handle):
            day = datetime.fromisoformat(row['decision_utc']).date()
            release = int(datetime.combine(day, time(14), ET).timestamp())
            result.append({'family': 'fomc', 'event': 'fomc:'+row['meeting'],
                'market_id': row['market_id'], 'outcome': row['outcome'], 'outcome_key': outcome_key(row['outcome']),
                'release': release, 'resolved': int(datetime.fromisoformat(row['market_resolution_proxy_utc']).timestamp()),
                'realized': int(row['realized']), 'db': 'wallet_backtest_cache/trades.sqlite3'})
    fresh = json.loads((DATA/'strategy_search/fresh/event.json').read_text())
    with readonly(DATA/'strategy_search/fresh/trades.sqlite3') as db:
        for mid, _, outcome, resolved, realized in db.execute('SELECT * FROM markets'):
            result.append({'family': 'fomc', 'event': 'fomc:2026-10', 'market_id': mid,
                'outcome': outcome, 'outcome_key': outcome_key(outcome),
                'release': int(datetime(2026, 10, 28, 14, tzinfo=ET).timestamp()),
                'resolved': resolved, 'realized': realized, 'db': 'strategy_search/fresh/trades.sqlite3'})
        if db.execute('SELECT fingerprint FROM build').fetchone()[0] != digest(DATA/'strategy_search/fresh/event.json'):
            raise ValueError('Fresh FOMC metadata/cache mismatch')
    summary = json.loads((DATA/'strategy_search/fresh/606422/summary.json').read_text())
    if summary['status'] != 'exhausted' or str(fresh['id']) != '606422':
        raise ValueError('Fresh FOMC history is incomplete')
    markets, releases, _ = macro_coverage.load_metadata(DATA/'macro')
    registered = json.loads((REPO/'models/macro_event_search/registration.json').read_text())['families']
    admitted = {family+':'+ref for family, item in registered.items() for ref in item['development']+item['holdout']}
    for market in markets.values():
        if market.event_id not in admitted:
            continue
        release = releases[market.event_id]
        family = 'cpi' if release['family'].startswith('cpi_') else release['family']
        result.append({'family': family, 'event': family+':'+str(release['release_ts']),
            'market_id': market.market_id, 'outcome': market.outcome,
            'outcome_key': release['family']+':'+outcome_key(market.outcome),
            'release': release['release_ts'], 'resolved': market.resolved_ts,
            'realized': market.realized, 'db': 'macro/trades.sqlite3'})
    return sorted(result, key=lambda r: (r['release'], r['market_id']))


def placebo_move(moves, index, key):
    if index < 1:
        return None
    seed = int(hashlib.sha256(('42|'+key).encode()).hexdigest(), 16)
    return moves[seed % index]


def market_quotes(db, market, times):
    snapshots, buckets = {}, {}
    for ts, price, token, raw_price in db.execute('SELECT ts,price,token_outcome,raw_price FROM trades WHERE market_id=? ORDER BY ts,dedup_key', (market['market_id'],)):
        if ts > market['resolved']:
            break
        if not 0 <= price <= 1 or not 0 <= raw_price <= 1 or token not in ('YES', 'NO'):
            raise ValueError('Invalid archived quote')
        j = bisect_left(times, ts)
        if j < len(times):
            snapshots[j] = (ts, price)
        if ts < market['release'] and j > 0 and ts > times[j-1]:
            buckets.setdefault((j-1, token), (ts, raw_price))
    entries, following = {}, {}
    for i in reversed(range(len(times))):
        for token in ('YES', 'NO'):
            if (i, token) in buckets:
                following[token] = buckets[(i, token)]
            entries[i, token] = following.get(token)
    return snapshots, entries


def panel(root):
    moves, asset_coverage = load_assets(root)
    times = [m['end'] for m in moves]
    markets = population()
    rows, trading, accuracy, counts = [], [], [], defaultdict(Counter)
    connections = {name: readonly(DATA/name) for name in {m['db'] for m in markets}}
    try:
        for market in markets:
            db, family = connections[market['db']], market['family']
            snapshots, entries = market_quotes(db, market, times)
            present = sorted(snapshots)
            if present:
                for i in range(max(1, present[0]), len(moves)):
                    if moves[i]['end'] >= market['release']:
                        break
                    counts[family]['candidate_trading_days'] += 1
                    if i not in snapshots:
                        counts[family]['missing_fresh_trading_day'] += 1
                    if i < len(moves)-1:
                        counts[family]['candidate_market_days'] += 1
                        if i not in snapshots or i+1 not in snapshots:
                            counts[family]['missing_fresh_PM_day'] += 1
                    if i not in snapshots:
                        continue
                    donor = placebo_move(moves, i, family+'|'+str(times[i]))
                    row = {**market, 'cutoff': times[i],
                        'p0': snapshots[i][1], 'p0_ts': snapshots[i][0],
                        'entries': {s: entries.get((i, s)) for s in ('YES', 'NO')},
                        'moves': {a: moves[i][a] for a in ASSETS},
                        'placebo': {a: donor[a] if donor else 0. for a in ASSETS},
                        'donor_end': donor['end'] if donor else None}
                    trading.append(row)
                    if i+1 in snapshots and i < len(moves)-1:
                        rows.append({**row, 'next_close': times[i+1], 'p1': snapshots[i+1][1], 'p1_ts': snapshots[i+1][0]})
                    if not all(row['entries'].values()):
                        counts[family]['missing_entry_side_days'] += 1
            cutoff = market['release']-86400
            i = bisect_right(times, cutoff)-1
            quote = db.execute('SELECT ts,price FROM trades WHERE market_id=? AND ts<=? AND ts>? ORDER BY ts DESC,dedup_key DESC LIMIT 1',
                (market['market_id'], cutoff, cutoff-86400)).fetchone()
            if i < 0 or quote is None:
                counts[family]['missing_t1_accuracy_quotes'] += 1
                continue
            donor = placebo_move(moves, i, family+'|'+str(times[i]))
            accuracy.append({**market, 'cutoff': cutoff, 'p0': quote[1], 'p0_ts': quote[0],
                'asset_end': times[i], 'moves': {a: moves[i][a] for a in ASSETS},
                'placebo': {a: donor[a] if donor else 0. for a in ASSETS},
                'donor_end': donor['end'] if donor else None})
    finally:
        for db in connections.values():
            db.close()
    inventory, splits = [], {}
    for family in FAMILIES:
        for name in ('candidate_market_days', 'missing_fresh_PM_day', 'candidate_trading_days',
                'missing_fresh_trading_day', 'missing_entry_side_days', 'missing_t1_accuracy_quotes'):
            counts[family].setdefault(name, 0)
        own = [m for m in markets if m['family'] == family]
        usable = {r['event'] for r in rows+trading+accuracy if r['family'] == family}
        ordered = sorted(usable, key=lambda e: min(m['release'] for m in own if m['event'] == e))
        holdout = max(5, math.ceil(.3*len(ordered)))
        if len(ordered)-holdout < 5:
            raise ValueError('Too few events for fixed split: '+family)
        splits[family] = {'development': ordered[:-holdout], 'holdout': ordered[-holdout:]}
        inventory.append({'family': family, 'archived_events': len({m['event'] for m in own}),
            'usable_events': len(usable), 'development_events': len(ordered)-holdout, 'holdout_events': holdout,
            'markets': len(own), 'daily_market_windows': sum(r['family'] == family for r in rows),
            'trading_market_days': sum(r['family'] == family for r in trading),
            'accuracy_market_cutoffs': sum(r['family'] == family for r in accuracy), **dict(counts[family])})
    save(root/'panel.json', {'daily': rows, 'trading': trading, 'accuracy': accuracy})
    save(root/'feasibility.json', {'inventory': inventory, 'splits': splits, 'assets': asset_coverage})
    return inventory, splits, asset_coverage


def sources(root):
    paths = [DATA/name for name in ('wallet_backtest_cache/trades.sqlite3', 'strategy_search/fresh/trades.sqlite3',
        'strategy_search/fresh/event.json', 'strategy_search/fresh/606422/summary.json', 'macro/trades.sqlite3',
        'macro/discovery.json', 'macro/bea_schedules.md')]
    paths += sorted((DATA/'macro').glob('bls_batch_*.md'))
    paths += [root/name for name in ('SPY.json', 'SHY.json', 'DGS2.csv', 'H15.html', 'NYSE.html', 'asset_sources.json', 'panel.json', 'feasibility.json')]
    return {str(p.relative_to(DATA)): digest(p) for p in paths}


if __name__ == '__main__':
    fetch_assets(ROOT)
    inventory, splits, coverage = panel(ROOT)
    print(json.dumps({'counts': inventory, 'assets': coverage}, indent=2))
