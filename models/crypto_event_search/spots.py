"""Archive free Binance hourly volatility candles and minute reference snapshots."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.parse import urlencode

from feasibility import load_collector, save
from markets import rule

BASE = 'https://data-api.binance.vision/api/v3/klines'


def candles(collector, path, symbol, interval, start, end, limit):
    query = {'symbol': symbol, 'interval': interval, 'startTime': start * 1000,
        'endTime': end * 1000, 'limit': limit}
    if not path.exists():
        save(path, {'url': BASE, 'params': query, 'data': collector.fetch(BASE + '?' + urlencode(query))})
    envelope = json.loads(path.read_text())
    if envelope['params'] != query:
        raise ValueError('Candle request changed')
    rows = envelope['data']
    if not isinstance(rows, list) or any(len(row) != 12 for row in rows):
        raise ValueError('Malformed Binance candle response')
    times = [int(row[0]) for row in rows]
    if len(set(times)) != len(times) or times != sorted(times):
        raise ValueError('Candle timestamps duplicate or unsorted')
    if any(not start * 1000 <= t <= end * 1000 for t in times):
        raise ValueError('Candle response outside request')
    return rows


def collect_spot(root):
    collector = load_collector(root)
    folder = root / 'spot'
    folder.mkdir(exist_ok=True)
    selected = json.loads((root / 'discovery.json').read_text())['selected']
    events = []
    for item in selected:
        try:
            metadata = rule(item['event'], item['event']['markets'][0], item['family'])
        except ValueError:
            continue
        events.append((str(item['event']['id']), metadata))
    for symbol in ('BTCUSDT', 'ETHUSDT'):
        subset = [m for _, m in events if m['symbol'] == symbol]
        start = (min(m['cutoff'] for m in subset) - 32 * 86400) // 3600 * 3600
        end = max(m['expiry'] for m in subset) // 3600 * 3600
        rows = []
        while start <= end:
            stop = min(end, start + 999 * 3600)
            rows.extend(candles(collector, folder / f'{symbol}_1h_{start}_{stop}.json', symbol, '1h', start, stop, 1000))
            start = stop + 3600
        save(folder / f'{symbol}_hourly.json', rows)
        print('Hourly candles:', symbol, len(rows), flush=True)

    def snapshots(pair):
        eid, m = pair
        rows = {}
        for label, stamp in (('cutoff', m['cutoff']), ('strike', m['strike_ts'])):
            if stamp is None:
                continue
            start = stamp // 60 * 60 - 180
            rows[label] = candles(collector, folder / f'{eid}_{label}.json', m['symbol'], '1m', start, start + 300, 6)
        return eid, rows

    with ThreadPoolExecutor(max_workers=4) as pool:
        snapshot_map = dict(pool.map(snapshots, events))
    save(folder / 'snapshots.json', snapshot_map)
    print('Minute snapshot events:', len(snapshot_map), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path.home() / 'data/polymarket/crypto')
    args = parser.parse_args()
    if args.data_root.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error('Raw data must remain outside git')
    collect_spot(args.data_root)
