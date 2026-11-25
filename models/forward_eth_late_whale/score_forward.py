"""Collect the preregistered forward universe; reveal its test only once at N."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time
from urllib.parse import urlencode

import rule
from feasibility import load_collector, mapping
from spots import candles


def git(*args):
    return subprocess.check_output(['git', *args], cwd=rule.REPO).decode().strip()


def registration():
    if git('rev-parse', '--is-shallow-repository') != 'false':
        raise ValueError('Full Git history is required to identify the freeze')
    relative = 'models/forward_eth_late_whale/'
    commits = git('log', '--diff-filter=A', '--format=%H', '--', relative+'registration.json').splitlines()
    if len(commits) != 1:
        raise ValueError('Exactly one committed forward registration is required')
    commit = commits[0]
    for name in ('registration.json', 'FORWARD_PREREGISTRATION.md'):
        blob = subprocess.check_output(['git', 'show', f'{commit}:{relative}{name}'], cwd=rule.REPO)
        if blob.replace(b'\r\n', b'\n') != (rule.FOLDER/name).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError('Frozen registration changed')
    spec = json.loads((rule.FOLDER/'registration.json').read_text())
    for name, expected in spec['code_hashes'].items():
        if rule.digest(rule.REPO/name) != expected:
            raise ValueError('Pinned rule/collector code changed: '+name)
    data = Path.home()/'data/polymarket'
    for name, expected in spec['collector_hashes'].items():
        if rule.digest(data/name) != expected:
            raise ValueError('Approved collector changed: '+name)
    freeze = {'commit': commit, 'timestamp': int(git('show', '-s', '--format=%ct', commit))}
    if int(time.time()) < freeze['timestamp'] or spec['wallet_eligibility_proof']['cutoff'] >= freeze['timestamp']:
        raise ValueError('Freeze clock or prior-wallet eligibility proof is invalid')
    return spec, freeze


def discover(root, collector, freeze):
    folder = root/'gamma'/str(time.time_ns())
    folder.mkdir(parents=True)
    cursor, seen_cursors, found = None, set(), {}
    while True:
        query = {'series_id': '40', 'closed': 'true', 'limit': 50, 'order': 'endDate', 'ascending': 'true'}
        if cursor:
            query['after_cursor'] = cursor
        response = collector.fetch('https://gamma-api.polymarket.com/events/keyset?'+urlencode(query))
        with gzip.open(folder/f'page_{len(seen_cursors):05d}.json.gz', 'wt') as handle:
            json.dump({'request_cursor': cursor, 'response': response}, handle)
        for event in response['events']:
            eid = str(event['id'])
            if eid in found or '40' not in {str(s['id']) for s in event.get('series', [])} or not event.get('closed'):
                raise ValueError('Gamma overlap or ignored series/closed filter')
            found[eid] = event
        cursor = response.get('next_cursor')
        if not cursor:
            break
        if not response['events']:
            raise ValueError('Gamma pagination made no progress')
        if cursor in seen_cursors:
            raise ValueError('Repeated Gamma cursor')
        seen_cursors.add(cursor)
    return list(found.values())


def cache_event(root, event, market, collector, spec):
    eid = str(event['id'])
    metadata = root/'events'/f'{eid}.json'
    if metadata.exists():
        archived = json.loads(metadata.read_text())
        old, new = archived['markets'][0], event['markets'][0]
        keys = ('id', 'conditionId', 'outcomes', 'outcomePrices', 'clobTokenIds', 'description', 'closedTime', 'umaEndDate', 'resolutionSource')
        if any(old.get(k) != new.get(k) for k in keys) or any(archived.get(k) != event.get(k) for k in ('title', 'endDate')):
            raise ValueError('Archived market rules/settlement changed')
        event = archived
    else:
        rule.atomic_json(metadata, event)
    folder = root/'trades'/eid
    summary_path = folder/'summary.json'
    if not summary_path.exists() or json.loads(summary_path.read_text())['status'] != 'exhausted':
        collector.MAPPING = mapping([{'family': rule.FAMILY, 'event': event}])
        collector.OUTPUT = root/'trades'
        collector.DEADLINE = time.monotonic()+21600
        collector.collect(eid)
    summary = json.loads(summary_path.read_text())
    pages = sorted(folder.glob('page_*.json.gz'))
    if summary['status'] != 'exhausted' or summary['next_cursor'] is not None or len(pages) != summary['pages']:
        raise ValueError('Forward trade history incomplete; repair, never skip it')
    paths = [metadata, summary_path, folder/'config.json', *pages]
    source = hashlib.sha256(json.dumps({str(p.relative_to(root)): rule.digest(p) for p in paths}, sort_keys=True).encode()).hexdigest()
    target = root/'cache'/f'{eid}.sqlite3'
    if target.exists():
        with rule.audit.prior.readonly(target) as db:
            if db.execute('SELECT fingerprint FROM build').fetchone()[0] != source:
                raise ValueError('Forward cache/source mismatch')
        return target, source
    temporary = target.with_suffix('.building.sqlite3')
    if temporary.exists():
        raise ValueError('Interrupted cache build; inspect before retrying')
    cursor, count, seen = None, 0, set()
    with sqlite3.connect(temporary) as db:
        rule.create_tables(db, {market.market_id: market})
        for number, path in enumerate(pages, 1):
            if path.name != f'page_{number:05d}.json.gz':
                raise ValueError('Noncontiguous trade pages')
            with gzip.open(path, 'rt') as handle:
                envelope = json.load(handle)
            if envelope['request_cursor'] != cursor:
                raise ValueError('Trade cursor chain changed')
            response = envelope['response']
            trades = [tuple(rule.normalize_trade(r, market).__dict__.values()) for r in response['data']]
            db.executemany('INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', trades)
            count += len(trades)
            cursor = response['pagination']['next_cursor']
            if cursor is not None:
                if cursor in seen or number == len(pages):
                    raise ValueError('Repeated/unexhausted trade cursor')
                seen.add(cursor)
            elif number != len(pages):
                raise ValueError('Trade pages follow terminal cursor')
        if cursor is not None or count != summary['participant_rows']:
            raise ValueError('Trade count/terminal cursor inconsistent')
        db.execute('CREATE INDEX market_time ON trades(market_id,ts)')
        db.execute('CREATE INDEX token_time ON trades(market_id,token_outcome,ts)')
        db.execute('INSERT INTO build VALUES (?,?,?)', (source, count, db.execute('SELECT COUNT(*) FROM trades').fetchone()[0]))
    temporary.replace(target)
    return target, source


def spot_eligible(root, event_id, info, collector):
    folder = root/'spot'
    symbol, cutoff = 'ETHUSDT', info['cutoff']
    start, end = (cutoff-32*86400)//3600*3600, cutoff//3600*3600
    hourly = candles(collector, folder/f'{event_id}_hourly.json', symbol, '1h', start, end, 1000)
    snapshots = {}
    for label, stamp in (('cutoff', cutoff), ('strike', info['strike_ts'])):
        start = stamp//60*60-180
        snapshots[label] = candles(collector, folder/f'{event_id}_{label}.json', symbol, '1m', start, start+300, 6)
    if not rule.audit.spot_coverage(info, snapshots, hourly):
        raise ValueError('Incomplete common spot coverage; repair, never skip it')
    return {p.name: rule.digest(p) for p in folder.glob(f'{event_id}_*.json')}


def run(root, spec, freeze, collector, now):
    lock = root/'single_look.json'
    if lock.exists():
        saved = json.loads(lock.read_text())
        if saved['status'] != 'complete':
            raise ValueError('Single look was claimed; no automatic retry is permitted')
        print('Single look already complete; not collecting or testing again.')
        return saved
    rows, exclusions = [], []
    events = discover(root, collector, freeze)
    candidates = []
    for event in events:
        try:
            info, market = rule.describe(event, freeze['timestamp'], now)
        except (rule.PreFreeze, rule.Ineligible) as error:
            exclusions.append({'event_id': str(event['id']), 'reason': str(error)})
            continue
        candidates.append((info, market, event))
    if candidates:
        data = root.parent
        for name, expected in spec['training_hashes'].items():
            if rule.digest(data/name) != expected:
                raise ValueError('Frozen prior-wallet corpus/proof changed: '+name)
    for info, market, event in sorted(candidates, key=lambda x: (x[0]['expiry'], x[0]['rid'])):
        cache, source = cache_event(root, event, market, collector, spec)
        spot_hashes = spot_eligible(root, str(event['id']), info, collector)
        with rule.audit.prior.readonly(cache) as db:
            try:
                row = rule.features(db, market, info, freeze['timestamp'], spec)
            except rule.Ineligible as error:
                exclusions.append({'event_id': str(event['id']), 'reason': str(error)})
                continue
        rows.append({**row, 'cache_source_sha256': source, 'spot_hashes': spot_hashes})
    status = {**rule.progress(rows, spec), 'freeze': freeze, 'as_of': now,
        'n_resolved_candidates': len(candidates), 'exclusions': exclusions, 'tested': False}
    rule.atomic_json(root/'progress.json', status)
    print(f"Progress: n eligible={status['n_eligible_dates']}; n traded={status['n_traded_dates']}; N={spec['N']}; no interim look.")
    if status['n_eligible_dates'] < spec['N']:
        print('Test not computed; forward ROI and p-value remain undisclosed.')
        return status
    report = rule.FOLDER/'FORWARD_RESULTS.md'
    result = rule.terminal_look(rows, spec, freeze, root, report)
    rule.atomic_json(root/'progress.json', {**status, 'tested': True, 'report': str(report)})
    print('Terminal look complete; report: '+str(report))
    return result


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    spec, freeze = registration()
    root = Path.home()/spec['data_root']
    if root.resolve().is_relative_to(rule.REPO):
        raise ValueError('Forward raw data and locks must remain outside Git')
    for name in ('', 'events', 'trades', 'cache', 'spot'):
        (root/name).mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(root/'runner.sqlite3', timeout=0) as guard:
        guard.execute('BEGIN EXCLUSIVE')
        run(root, spec, freeze, load_collector(root), int(time.time()))


if __name__ == '__main__':
    main()
