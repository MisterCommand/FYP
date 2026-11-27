"""Restore missing Yahoo cross-check snapshots without changing registered pins."""

import hashlib
import json
import urllib.request

import archive


SOURCES = {
    'VIX.json': 'https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?range=5y&interval=1d',
    'VIX9D.json': 'https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX9D?range=5y&interval=1d'}


def prepare(root, specification):
    expected = {name: specification['data_hashes'].get('options_to_event_search/'+name) for name in SOURCES}
    if not all(expected.values()):
        raise ValueError('Missing registered cross-check pin')
    root.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        path = root/name
        if path.exists():
            if archive.digest(path) != expected[name]:
                raise ValueError('Changed cached cross-check snapshot: '+name)
            continue
        request = urllib.request.Request(url, headers={'User-Agent': 'EventLens-research/0.1 (HKUST FYP)'})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
        if hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() != expected[name]:
            raise ValueError('Downloaded snapshot differs from registration; restore the original archived '+name)
        temporary = path.with_suffix(path.suffix+'.partial')
        temporary.write_bytes(raw)
        temporary.replace(path)


if __name__ == '__main__':
    specification = json.loads((archive.FOLDER/'registration.json').read_text())
    prepare(archive.ROOT, specification)
    print('Both Yahoo cross-check snapshots match the historical registration; no pins changed.')
