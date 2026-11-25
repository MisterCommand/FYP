"""Frozen round-five ETH daily late-whale rule and single terminal look."""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
sys.path.insert(0, str(FOLDER.parent / 'crypto_event_search'))
import audit
from build_panel import Market, array, create_tables, normalize_trade, resolution_time
from markets import rule as market_rule
import signals

FAMILY = 'eth_updown_daily'


class PreFreeze(ValueError):
    pass


class Ineligible(ValueError):
    pass


class Pending(Ineligible):
    pass


def digest(path):
    path = Path(path)
    data = path.read_bytes()
    if path.suffix in ('.py', '.json', '.md', '.csv'):
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.partial')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def require_forward(info, freeze):
    if info['cutoff'] <= freeze:
        raise PreFreeze('Cutoff must be strictly after the freeze commit time')
    if info['cutoff'] != info['expiry'] - 43200:
        raise ValueError('Daily cutoff is not t-12h')


def describe(event, freeze, now):
    if '40' not in {str(s['id']) for s in event.get('series', [])}:
        raise ValueError('Gamma returned another series')
    if len(event['markets']) != 1:
        raise ValueError('Daily event schema changed: expected one binary contract')
    raw = event['markets'][0]
    try:
        info = market_rule(event, raw, FAMILY)
    except ValueError as error:
        raise Ineligible('Unmapped original resolution rule: '+str(error)) from error
    require_forward(info, freeze)
    if not info['model_compatible']:
        raise Ineligible('Oracle is not the registered Binance ETHUSDT source')
    if not event.get('closed') or not raw.get('closed'):
        raise ValueError('Discovery returned an unresolved event')
    if not any(raw.get(key) for key in ('closedTime', 'umaEndDate')):
        raise Pending('Conservative settlement timestamp is missing')
    names, tokens = array(raw['outcomes']), array(raw['clobTokenIds'])
    prices = list(map(float, array(raw['outcomePrices'])))
    if set(names) != {'Up', 'Down'} or len(tokens) != 2 or len(set(tokens)) != 2:
        raise ValueError('Not an Up/Down binary contract')
    payouts = dict(zip(names, prices))
    if len(prices) != 2 or not all(math.isfinite(p) for p in prices) or min(abs(payouts['Up']), abs(1-payouts['Up'])) > .001 or abs(sum(prices)-1) > .001:
        raise ValueError('No terminal binary settlement')
    settled, basis = resolution_time(raw)
    if settled < info['expiry']:
        raise ValueError('Settlement precedes observation')
    if settled > now or info['expiry'] > now:
        raise Pending('Conservative settlement timestamp is not yet available')
    rid = FAMILY + ':' + str(event['id'])
    by_name = dict(zip(names, map(str, tokens)))
    market = Market(str(raw['id']), rid, rid, raw['question'], raw['conditionId'].lower(),
        by_name['Up'], by_name['Down'], info['expiry'], settled, basis,
        int(payouts['Up'] > .5), payouts['Up'], ())
    return {**info, 'family': FAMILY, 'rid': rid,
        'cluster': datetime.fromtimestamp(info['expiry'], timezone.utc).date().isoformat()}, market


def features(db, market, info, freeze, spec):
    require_forward(info, freeze)
    cutoff = info['cutoff']
    entries = {side: audit.prior.first_trade(db, market.market_id, side, cutoff, info['expiry']) for side in ('YES', 'NO')}
    if audit.prior.prior_price(db, market.market_id, cutoff) is None or not all(entries.values()):
        raise Ineligible('Missing common pre-cutoff quote or either strict post-cutoff entry')
    late = db.execute('''SELECT SUM(signed_yes_notional), SUM(notional) FROM trades
        WHERE market_id=? AND ts>=? AND ts<? AND notional>=?''',
        (market.market_id, cutoff-spec['late_whale_lookback_seconds'], cutoff, spec['large_trade_notional'])).fetchone()
    return {**info, 'market_id': market.market_id, 'entries': entries, 'realized': market.realized,
        'late_whale': late[0]/late[1] if late[1] else 0.}


def would_trade(row, spec):
    sign = row['late_whale']
    return bool(sign and row['entries']['YES' if sign > 0 else 'NO'][1] + spec['pm_cost'] < 1)


def progress(rows, spec):
    dates = {r['cluster'] for r in rows}
    traded = {r['cluster'] for r in rows if would_trade(r, spec)}
    return {'n_eligible_dates': len(dates), 'n_traded_dates': len(traded), 'target_dates': spec['N']}


def terminal_look(rows, spec, freeze, root, report):
    status = progress(rows, spec)
    if status['n_eligible_dates'] < spec['N']:
        return status
    dates = sorted({r['cluster'] for r in rows})[:spec['N']]
    selected = sorted((r for r in rows if r['cluster'] in set(dates)), key=lambda r: (r['cluster'], r['rid']))
    for row in selected:
        require_forward(row, freeze['timestamp'])
    claim = {'status': 'claimed', 'freeze': freeze, 'dates': dates,
        'observations_sha256': hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest()}
    lock = root / 'single_look.json'
    if report.exists():
        raise ValueError('Forward report already exists; never retry this study')
    try:
        with lock.open('x') as handle:
            json.dump(claim, handle, indent=2)
    except FileExistsError:
        raise ValueError('Single look already claimed; never delete the lock') from None
    records = []
    for row in selected:
        value, traded = audit.prior.pm_return(row['late_whale'], row, spec['pm_cost'])
        records.append({**row, 'net_return': value, 'traded': int(traded)})
    result = signals.metrics(records, spec)
    passed = result['metric'] > 0 and result['p'] < spec['alpha']
    verdict = 'PASS' if passed else 'FAIL: no forward edge established'
    with report.open('x') as handle:
        handle.write(f'# {verdict}\n\nRound 5; one hypothesis; one terminal look; no interim.\n\n'
            f"Freeze: `{freeze['commit']}` ({freeze['timestamp']}).\n\n"
            f"Dates: {dates[0]} through {dates[-1]}; N={spec['N']}.\n\n"
            f"Mean after-cost ROI: {result['metric']:.9f}; one-sided p={result['p']:.9f}; alpha=0.01.\n\n"
            f"Traded contracts: {result['n_trades']}/{result['n_contracts']}.\n\n"
            'The sign-flip test assumes sign exchangeability under the null; serial dependence, '
            'changing fees, participant-print execution and round-five selection remain limitations.\n')
    atomic_json(lock, {**claim, 'status': 'complete', 'result': result, 'passed': passed})
    return {**status, 'tested': True, 'result': result}
