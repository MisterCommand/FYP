"""Coverage-only crypto discovery and collection; no strategy returns."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import runpy
import sys
import time
from urllib.parse import urlencode

MODELS = Path(__file__).resolve().parents[1]
load_collector = runpy.run_path(str(MODELS / 'macro_event_search/feasibility.py'))['load_collector']

SERIES = {
    'btc_above_daily': ('45',), 'eth_above_daily': ('42',),
    'btc_updown_daily': ('41',), 'eth_updown_daily': ('40',),
    'btc_updown_weekly': ('10094',), 'eth_updown_weekly': ('10095',),
    'btc_updown_hourly': ('10110', '10114'), 'eth_updown_hourly': ('10117',),
}
SAMPLE_CAP = 120


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def even_sample(events, cap=SAMPLE_CAP):
    ordered = sorted(events, key=lambda e: (e['endDate'], int(e['id'])))
    if cap < 2:
        raise ValueError('Sampling cap must be at least two')
    if len(ordered) <= cap:
        return ordered
    return [ordered[i * (len(ordered) - 1) // (cap - 1)] for i in range(cap)]


def discover(root, collector):
    folder = root / 'gamma'
    folder.mkdir(exist_ok=True)
    config = root / 'discovery_config.json'
    if not config.exists():
        now = datetime.now(timezone.utc)
        save(config, {'as_of': now.isoformat(),
            'retention_floor': now.replace(year=now.year - 3).isoformat(),
            'sample_cap': SAMPLE_CAP, 'series': SERIES})
    spec = json.loads(config.read_text())

    def inventory(pair):
        family, ids = pair
        found = {}
        for sid in ids:
            page, cursor = 0, None
            previous = set()
            cursors = set()
            while True:
                path = folder / f'after_{sid}_{page:06d}.json.gz'
                if not path.exists():
                    query = {'series_id': sid, 'closed': 'true', 'limit': 50,
                        'order': 'endDate', 'ascending': 'true',
                        'end_date_min': spec['retention_floor'], 'end_date_max': spec['as_of']}
                    if cursor:
                        query['after_cursor'] = cursor
                    response = collector.fetch('https://gamma-api.polymarket.com/events/keyset?' + urlencode(query))
                    with gzip.open(path, 'wt') as handle:
                        json.dump({'request_cursor': cursor, 'response': response}, handle)
                with gzip.open(path, 'rt') as handle:
                    envelope = json.load(handle)
                if envelope['request_cursor'] != cursor:
                    raise ValueError('Gamma keyset cursor chain changed')
                batch = envelope['response']['events']
                if not isinstance(batch, list):
                    raise ValueError('Invalid Gamma event page')
                ids_in_page = {str(e['id']) for e in batch}
                if previous & ids_in_page:
                    raise ValueError('Gamma pagination overlaps; freeze/restart discovery')
                previous.update(ids_in_page)
                for e in batch:
                    if sid not in {str(s['id']) for s in e.get('series', [])}:
                        raise ValueError('Gamma series filter ignored')
                    if not e.get('closed') or not spec['retention_floor'] <= e['endDate'] <= spec['as_of']:
                        raise ValueError('Gamma closed/date filter ignored')
                    found[str(e['id'])] = e
                cursor = envelope['response'].get('next_cursor')
                if not cursor:
                    break
                if cursor in cursors:
                    raise ValueError('Gamma keyset cursor repeated')
                cursors.add(cursor)
                page += 1
        print('Inventory:', family, len(found), flush=True)
        return family, list(found.values())

    with ThreadPoolExecutor(max_workers=4) as pool:
        inventory_by_family = dict(pool.map(inventory, SERIES.items()))
    save(root / 'inventory.json', inventory_by_family)
    selected = [{'family': family, 'event': event}
        for family, events in inventory_by_family.items() for event in even_sample(events)]
    save(root / 'discovery.json', {**spec, 'selected': selected,
        'sampling': 'Sort by Gamma endDate then numeric event ID; select floor(i*(N-1)/(cap-1)), i=0..cap-1; retain all when N<=cap.'})
    print('Sample:', dict(Counter(r['family'] for r in selected)), flush=True)


def mapping(selected):
    rows = []
    for item in selected:
        for market in item['event']['markets']:
            tokens = market['clobTokenIds']
            if not isinstance(tokens, str):
                tokens = json.dumps(tokens)
            rows.append({'event_id': str(item['event']['id']), 'market_id': str(market['id']),
                'meeting_month': item['family'] + ':' + str(item['event']['id']),
                'outcome': market.get('groupItemTitle') or market['question'],
                'condition_id': market['conditionId'], 'tokens': tokens,
                'start_date': market.get('startDate', ''), 'created_at': market.get('createdAt', '')})
    return rows


def collect(root, collector):
    selected = json.loads((root / 'discovery.json').read_text())['selected']
    collector.MAPPING = mapping(selected)
    collector.OUTPUT = root / 'trades'
    collector.OUTPUT.mkdir(exist_ok=True)
    collector.DEADLINE = time.monotonic() + 21600
    with ThreadPoolExecutor(max_workers=4) as pool:
        summaries = list(pool.map(collector.collect, sorted({r['event_id'] for r in collector.MAPPING})))
    counts = Counter(r['status'] for r in summaries)
    print('Collection status:', dict(counts), flush=True)
    if set(counts) != {'exhausted'}:
        raise ValueError('Incomplete histories; not eligible for research')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('discover', 'collect'))
    parser.add_argument('--data-root', type=Path, default=Path.home() / 'data/polymarket/crypto')
    args = parser.parse_args()
    root = args.data_root.resolve()
    if root.is_relative_to(MODELS.parent):
        parser.error('Raw data must remain outside git')
    root.mkdir(parents=True, exist_ok=True)
    collector = load_collector(root)
    {'discover': discover, 'collect': collect}[args.phase](root, collector)


if __name__ == '__main__':
    main()
