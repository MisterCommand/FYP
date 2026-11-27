"""Synthetic fresh-setup and immutable-snapshot regression fixtures."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import archive
import setup_cross_checks
import study


class SetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.data = self.base/'data'
        self.data.mkdir()
        self.root = self.data/'options_to_event_search'
        for module, name, value in ((archive, 'DATA', self.data), (archive, 'ROOT', self.root)):
            mocked = patch.object(module, name, value)
            mocked.start()
            self.addCleanup(mocked.stop)
        network = patch('urllib.request.urlopen', side_effect=AssertionError('No real network'))
        network.start()
        self.addCleanup(network.stop)
        self.payloads = {name: json.dumps({'synthetic': name}).encode()+b'\r\n' for name in setup_cross_checks.SOURCES}

    def fresh_archive(self):
        prior = self.data/'stock_to_event_search'
        prior.mkdir()
        (prior/'SPY.json').write_bytes(b'synthetic calendar')
        with patch.object(archive.urllib.request, 'urlopen', side_effect=lambda *a, **kw: io.BytesIO(b'synthetic response')) as request:
            archive.fetch_assets(self.root)
            self.assertEqual(request.call_count, 3)
        for name in ('VIX.json', 'VIX9D.json'):
            self.assertFalse((self.root/name).exists())
        for name in ('wallet_backtest_cache/trades.sqlite3', 'strategy_search/fresh/trades.sqlite3',
                'strategy_search/fresh/event.json', 'strategy_search/fresh/606422/summary.json',
                'macro/trades.sqlite3', 'macro/discovery.json', 'macro/bea_schedules.md'):
            path = self.data/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic archive input')
        for name in ('panel.json', 'feasibility.json'):
            archive.save(self.root/name, {})
        for name, raw in self.payloads.items():
            (self.root/name).write_bytes(raw)
        specification = {'code_hashes': {}, 'data_hashes': archive.sources(self.root)}
        for name in self.payloads:
            (self.root/name).unlink()
        return specification

    def download(self, request, **kwargs):
        name = 'VIX9D.json' if '%5EVIX9D?' in request.full_url else 'VIX.json'
        return io.BytesIO(self.payloads[name])

    def test_fresh_archive_preflight_rejects_then_setup_restores_missing_inputs(self):
        specification = self.fresh_archive()
        output = self.base/'report'
        output.mkdir()
        archive.save(output/'registration.json', specification)
        (output/'PREREGISTRATION.md').write_text('synthetic committed registration\n')
        def git(*args):
            return 'false' if args[0] == 'rev-parse' else 'synthetic-commit'
        def show(args, **kwargs):
            return (output/args[-1].split('/')[-1]).read_bytes()
        before = {p.relative_to(self.data): p.read_bytes() for p in self.data.rglob('*') if p.is_file()}
        with patch.object(study, 'FOLDER', output), patch.object(study, 'git', side_effect=git), patch.object(study.subprocess, 'check_output', side_effect=show):
            with self.assertRaisesRegex(ValueError, 'Frozen source inputs changed'):
                study.registration()
            with patch.object(setup_cross_checks.urllib.request, 'urlopen', side_effect=self.download) as request:
                setup_cross_checks.prepare(self.root, specification)
                self.assertEqual(request.call_count, 2)
            self.assertEqual(study.registration(), (specification, 'synthetic-commit'))
            setup_cross_checks.prepare(self.root, specification)
            self.assertEqual(study.registration()[0], specification)
        for relative, raw in before.items():
            self.assertEqual((self.data/relative).read_bytes(), raw)
        for name, raw in self.payloads.items():
            self.assertEqual((self.root/name).read_bytes(), raw)
        print('Synthetic repro: fresh fetch omits both cross-checks; preflight rejects. Setup restores both matching snapshots; preflight passes; cached rerun makes no requests; real network requests: 0.')

    def test_changed_download_is_rejected_without_saving(self):
        specification = self.fresh_archive()
        with patch.object(setup_cross_checks.urllib.request, 'urlopen', return_value=io.BytesIO(b'changed live response')):
            with self.assertRaisesRegex(ValueError, 'Downloaded snapshot differs'):
                setup_cross_checks.prepare(self.root, specification)
        self.assertFalse((self.root/'VIX.json').exists())
        self.assertFalse((self.root/'VIX.json.partial').exists())

    def test_changed_cache_is_rejected_without_overwrite_or_request(self):
        specification = self.fresh_archive()
        path = self.root/'VIX.json'
        path.write_bytes(b'changed cached response')
        with self.assertRaisesRegex(ValueError, 'Changed cached cross-check'):
            setup_cross_checks.prepare(self.root, specification)
        self.assertEqual(path.read_bytes(), b'changed cached response')

    def test_network_failure_leaves_no_snapshot(self):
        specification = self.fresh_archive()
        with patch.object(setup_cross_checks.urllib.request, 'urlopen', side_effect=urllib.error.URLError('synthetic offline')):
            with self.assertRaises(urllib.error.URLError):
                setup_cross_checks.prepare(self.root, specification)
        self.assertFalse((self.root/'VIX.json').exists())

    def test_missing_pin_fails_before_creating_directory_or_fetching(self):
        with self.assertRaisesRegex(ValueError, 'Missing registered cross-check pin'):
            setup_cross_checks.prepare(self.root, {'data_hashes': {}})
        self.assertFalse(self.root.exists())


if __name__ == '__main__':
    unittest.main()
