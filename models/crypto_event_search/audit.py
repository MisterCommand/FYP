"""Validate exhausted participant histories and audit point-in-time coverage."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from markets import array, rule

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER.parent / 'strategy_search'))
import search as prior
from build_panel import Market, create_tables, normalize_trade, resolution_time, write_csv


def metadata(root):
    selected = json.loads((root / 'discovery.json').read_text())['selected']
    markets, details, events = {}, {}, []
    conditions_seen = set()
    for item in selected:
        event, family = item['event'], item['family']
        eid = str(event['id'])
        row = {'family': family, 'event_id': eid, 'title': event['title'],
            'gamma_end': event['endDate'], 'contracts': len(event['markets']), 'mapped_contracts': 0,
            'resolution_utc': '', 'resolution_source': '', 'exclusions': ''}
        reasons = Counter()
        for m in event['markets']:
            try:
                info = rule(event, m, family)
                names, prices, tokens = array(m['outcomes']), list(map(float, array(m['outcomePrices']))), array(m['clobTokenIds'])
                positive = 'Yes' if '_above_' in family else 'Up'
                negative = 'No' if positive == 'Yes' else 'Down'
                if not m.get('closed') or set(names) != {positive, negative} or len(set(tokens)) != 2:
                    raise ValueError('Not a closed binary contract')
                payout = dict(zip(names, prices))
                if min(abs(payout[positive]), abs(1 - payout[positive])) > .001 or abs(sum(prices)-1) > .001:
                    raise ValueError('No terminal binary settlement')
                settled, basis = resolution_time(m)
                if settled < info['expiry']:
                    raise ValueError('Settlement precedes underlying observation')
                condition = m['conditionId'].lower()
                if condition in conditions_seen:
                    raise ValueError('Duplicate condition across event objects')
                conditions_seen.add(condition)
                mid, rid = str(m['id']), family + ':' + eid
                by_name = dict(zip(names, map(str, tokens)))
                markets[mid] = Market(mid, rid, rid, m.get('groupItemTitle') or m['question'],
                    condition, by_name[positive], by_name[negative], info['expiry'], settled,
                    basis, int(payout[positive] > .5), payout[positive], ())
                details[mid] = {**info, 'family': family, 'event_id': eid, 'rid': rid,
                    'market_id': mid, 'outcome': positive, 'settled': settled}
                row['mapped_contracts'] += 1
                row['resolution_utc'], row['resolution_source'] = info['utc'], info['resolution_source']
            except (ValueError, KeyError) as error:
                reasons[str(error)] += 1
        row['exclusions'] = json.dumps(reasons, sort_keys=True)
        events.append(row)
    return markets, details, events


def fingerprint(root):
    paths = [root / 'discovery.json', root / 'inventory.json']
    paths += sorted((root / 'trades').glob('*/*.json')) + sorted((root / 'trades').glob('*/page_*.json.gz'))
    paths += sorted((root / 'spot').glob('*.json'))
    result = hashlib.sha256()
    for path in paths:
        result.update(str(path.relative_to(root)).encode())
        result.update(prior.digest(path).encode())
    for name in ('audit.py', 'markets.py', 'feasibility.py', 'spots.py'):
        result.update(name.encode())
        result.update(prior.digest(FOLDER / name).encode())
    return result.hexdigest()


def validate_cache(root):
    value = fingerprint(root)
    with prior.readonly(root / 'trades.sqlite3') as db:
        row = db.execute('SELECT fingerprint FROM build').fetchone()
    if row is None or row[0] != value:
        raise ValueError('Crypto cache/source fingerprint mismatch')
    return value


def build_cache(root, markets, events):
    path = root / 'trades.sqlite3'
    if path.exists():
        validate_cache(root)
        return path
    value = fingerprint(root)
    temporary = root / 'trades.building.sqlite3'
    if temporary.exists():
        raise ValueError('Incomplete crypto cache; inspect before resuming')
    selected = json.loads((root / 'discovery.json').read_text())['selected']
    expected = {str(i['event']['id']): {m['conditionId'].lower(): set(map(str, array(m['clobTokenIds'])))
        for m in i['event']['markets']} for i in selected}
    raw_rows = 0
    raw_wallets, raw_totals = defaultdict(set), Counter()
    with sqlite3.connect(temporary) as db:
        create_tables(db, markets)
        for event in events:
            eid = event['event_id']
            folder = root / 'trades' / eid
            summary = json.loads((folder / 'summary.json').read_text())
            pages = sorted(folder.glob('page_*.json.gz'))
            if summary['status'] != 'exhausted' or summary['next_cursor'] is not None or len(pages) != summary['pages']:
                raise ValueError('History not exhausted or page count inconsistent')
            members = {m.condition_id: m for m in markets.values() if m.event_id == event['family'] + ':' + eid}
            cursor, count, seen = None, 0, set()
            for number, page in enumerate(pages, 1):
                if page.name != f'page_{number:05d}.json.gz':
                    raise ValueError('Noncontiguous page numbering')
                envelope = json.loads(gzip.decompress(page.read_bytes()))
                if envelope['request_cursor'] != cursor:
                    raise ValueError('Trade cursor chain inconsistent')
                response, trades = envelope['response'], []
                for record in response['data']:
                    condition = record['condition_id'].lower()
                    if condition not in expected[eid] or str(record['token_id']) not in expected[eid][condition]:
                        raise ValueError('Trade condition/token outside sampled Gamma event')
                    raw_wallets[event['family']].add(record['proxy_wallet'].lower())
                    if condition in members:
                        trades.append(tuple(normalize_trade(record, members[condition]).__dict__.values()))
                db.executemany('INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', trades)
                count += len(response['data'])
                cursor = response['pagination']['next_cursor']
                if cursor is not None:
                    if cursor in seen or number == len(pages):
                        raise ValueError('Repeated or unexhausted trade cursor')
                    seen.add(cursor)
                elif number != len(pages):
                    raise ValueError('Pages after terminal cursor')
            if cursor is not None or count != summary['participant_rows']:
                raise ValueError('History row count inconsistent')
            raw_rows += count
            raw_totals[event['family']] += count
            db.commit()
            print('Ingested:', eid, count, flush=True)
        db.execute('CREATE INDEX market_time ON trades(market_id, ts)')
        db.execute('CREATE INDEX token_time ON trades(market_id, token_outcome, ts)')
        db.execute('INSERT INTO build VALUES (?,?,?)', (value, raw_rows, db.execute('SELECT COUNT(*) FROM trades').fetchone()[0]))
    temporary.replace(path)
    (root / 'raw_counts.json').write_text(json.dumps({family: {
        'participant_rows': raw_totals[family], 'distinct_wallets': len(raw_wallets[family])}
        for family in raw_totals}, indent=2) + '\n')
    return path


def attach_prior(db, root):
    fresh, _, reason = prior.fresh_cache(root.parent)
    if fresh is None:
        raise ValueError('Registered October FOMC history is required: ' + reason)
    for schema, path in (('fomc', root.parent / 'wallet_backtest_cache/trades.sqlite3'),
                         ('macro', root.parent / 'macro/trades.sqlite3')):
        db.execute(f'ATTACH DATABASE ? AS {schema}', (path.resolve().as_uri() + '?mode=ro',))
    db.execute('ATTACH DATABASE ? AS fresh', (fresh.resolve().as_uri() + '?mode=ro',))


def skill_sql(db, with_pnl=False, before=None):
    schemas = [r[1] for r in db.execute('PRAGMA database_list') if r[1] in ('main', 'fomc', 'macro', 'fresh')]
    pieces = []
    for schema in schemas:
        family = "SUBSTR(m.event_id,1,INSTR(m.event_id,':')-1)" if schema == 'main' else "'prior'"
        pnl = 'SUM(t.signed_yes_shares*(m.realized-t.price))' if with_pnl else '0.'
        limit = f'WHERE m.resolved_ts<{int(before)} AND t.ts<{int(before)}' if before is not None else ''
        pieces.append(f'''SELECT t.wallet, MAX(m.resolved_ts,t.ts) eligible,
            {family} family, COUNT(*) n, {pnl} pnl, SUM(t.notional) gross
            FROM {schema}.trades t JOIN {schema}.markets m USING(market_id)
            {limit}
            GROUP BY t.wallet, eligible, family''')
    return 'SELECT * FROM (' + ' UNION ALL '.join(pieces) + ') ORDER BY eligible'


def skill_stream(db, requests, with_pnl=False):
    if not requests:
        return
    stream = iter(db.execute(skill_sql(db, with_pnl, max(r['cutoff'] for r in requests))))
    current = next(stream, None)
    history = defaultdict(dict)
    for request in sorted(requests, key=lambda r: (r['cutoff'], r['rid'])):
        while current is not None and current[1] < request['cutoff']:
            wallet, _, family, n, pnl, gross = current
            values = history[family].setdefault(wallet, [0, 0., 0.])
            values[0] += n
            values[1] += pnl
            values[2] += gross
            current = next(stream, None)
        base, own = history['prior'], history[request['family']]
        scores = {}
        for wallet in base.keys() | own.keys():
            a, b = base.get(wallet, (0, 0., 0.)), own.get(wallet, (0, 0., 0.))
            n, pnl, gross = (a[i] + b[i] for i in range(3))
            if n >= 5 and gross > 0:
                scores[wallet] = {'score': pnl / gross * n / (n + 20) if with_pnl else 0., 'n_trades': n}
        yield request, scores


def spot_coverage(info, snapshots, hourly):
    if not info['model_compatible']:
        return False
    cutoff = info['cutoff']
    minute = [r for r in snapshots.get('cutoff', []) if int(r[6]) < cutoff * 1000]
    vol = [r for r in hourly if (cutoff - 30 * 86400) * 1000 <= int(r[6]) < cutoff * 1000]
    if not minute or cutoff * 1000 - int(minute[-1][6]) > 61000 or len(vol) < 720:
        return False
    if any(int(b[0])-int(a[0]) != 3600000 for a, b in zip(vol, vol[1:])):
        return False
    if info['strike_ts'] is not None:
        stamp = info['strike_ts'] * 1000
        strike = [r for r in snapshots.get('strike', []) if
            int(r[0]) == stamp] if info['strike_kind'] == 'open' else [r for r in snapshots.get('strike', []) if stamp-61000 <= int(r[6]) < stamp]
        if not strike:
            return False
    return True


def audit(root):
    markets, details, events = metadata(root)
    cache = build_cache(root, markets, events)
    snapshots = json.loads((root / 'spot/snapshots.json').read_text())
    hourly = {s: json.loads((root / f'spot/{s}_hourly.json').read_text()) for s in ('BTCUSDT', 'ETHUSDT')}
    requests = {d['rid']: d for d in details.values()}
    coverage = {}
    with prior.readonly(cache) as db:
        attach_prior(db, root)
        for info, scores in skill_stream(db, list(requests.values())):
            rid, cutoff = info['rid'], info['cutoff']
            members = [m for m in markets.values() if m.event_id == rid]
            eligible = [m for m in members if prior.prior_price(db, m.market_id, cutoff) is not None
                and all(prior.first_trade(db, m.market_id, side, cutoff, info['expiry']) for side in ('YES', 'NO'))]
            spot = spot_coverage(info, snapshots.get(info['event_id'], {}), hourly[info['symbol']])
            coverage[rid] = {'eligible_contracts': len(eligible), 'qualifying_wallets': len(scores),
                'spot_covered': spot, 'usable': bool(eligible and len(scores) >= 200 and spot),
                'cutoff': cutoff, 'expiry': info['expiry']}
            print('Coverage:', rid, coverage[rid], flush=True)
    for row in events:
        summary = json.loads((root / 'trades' / row['event_id'] / 'summary.json').read_text())
        row.update({'participant_rows': summary['participant_rows'], 'event_wallets': summary['distinct_wallets'], 'pages': summary['pages']})
        row.update(coverage.get(row['family'] + ':' + row['event_id'],
            {'eligible_contracts': 0, 'qualifying_wallets': 0, 'spot_covered': False, 'usable': False, 'cutoff': '', 'expiry': ''}))
    inventory = json.loads((root / 'inventory.json').read_text())
    raw_counts = json.loads((root / 'raw_counts.json').read_text())
    families = []
    with prior.readonly(cache) as db:
        for family in inventory:
            rows = [r for r in events if r['family'] == family]
            wallets = db.execute('SELECT COUNT(DISTINCT wallet) FROM trades JOIN markets USING(market_id) WHERE event_id LIKE ?', (family + ':%',)).fetchone()[0]
            normalized = db.execute('SELECT COUNT(*) FROM trades JOIN markets USING(market_id) WHERE event_id LIKE ?', (family + ':%',)).fetchone()[0]
            families.append({'family': family, 'resolved_gamma_events': len(inventory[family]),
                'resolved_gamma_contracts': sum(len(e['markets']) for e in inventory[family]),
                'sampled_events': len(rows), 'sampled_contracts': sum(r['contracts'] for r in rows),
                'usable_events': sum(r['usable'] for r in rows),
                'participant_rows': sum(r['participant_rows'] for r in rows),
                'deduplicated_participant_rows': normalized,
                'distinct_wallets': raw_counts[family]['distinct_wallets'],
                'distinct_wallets_mapped_contracts': wallets, 'included': sum(r['usable'] for r in rows) >= 60})
    write_csv(FOLDER / 'event_coverage.csv', events)
    write_csv(FOLDER / 'family_coverage.csv', families)
    write_csv(FOLDER / 'contract_resolution.csv', list(details.values()))
    print(json.dumps(families, indent=2), flush=True)


if __name__ == '__main__':
    audit(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / 'data/polymarket/crypto')
