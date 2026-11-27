"""Synthetic tests: timing and coverage only, with no performance fixtures."""

from types import SimpleNamespace
import unittest

import audit


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.ends = [1000, 2000, 3000, 4000, 5000]
        self.splits = {family: {'development': [family + ':a'], 'holdout': [family + ':b']}
            for family in audit.FAMILIES}

    def market(self, family, mid, event=None, release=90000, resolved=100000):
        return {'family': family, 'market_id': mid, 'event': event or family + ':a',
            'release': release, 'resolved': resolved}

    def test_freshness_exact_endpoint_and_missing_intervals(self):
        self.assertEqual(audit.fresh_intervals([1000, 1001, 2000, 4000], self.ends, 10000), {1, 3})
        self.assertEqual(audit.fresh_intervals([], self.ends, 10000), set())
        self.assertEqual(audit.fresh_intervals([2500, 4000], self.ends, 3000), {2})

    def test_same_contract_required_at_both_source_endpoints(self):
        markets = [self.market('cpi', 'one'), self.market('cpi', 'two')]
        pairs = audit.paired_sources(markets, self.ends, {'one': [1500], 'two': [2500]})
        self.assertEqual(dict(pairs), {})
        pairs = audit.paired_sources(markets, self.ends, {'one': [1500, 2500], 'two': []})
        self.assertEqual([m['market_id'] for m in pairs[2]], ['one'])

    def test_source_must_be_unreleased_and_unresolved_at_decision(self):
        pairs = {2: [self.market('cpi', 'a', release=3300),
            self.market('cpi', 'b', release=3400, resolved=3300),
            self.market('cpi', 'c', release=3400)]}
        self.assertEqual([m['market_id'] for m in audit.source_at(pairs, 2, 3300)], ['c'])
        self.assertEqual(audit.source_at(pairs, 1, 3300), [])

    def fixture(self, cpi=True, target_next=True):
        markets = [self.market('fomc', 'fed'), self.market('cpi', 'cpi'),
            self.market('payrolls', 'target')]
        stamps = {'fed': [1500, 2500], 'cpi': [1500, 2500] if cpi else [],
            'target': [2500, 3500] if target_next else [2500]}
        return markets, stamps

    def test_H3_does_not_require_H1_future_quote(self):
        markets, stamps = self.fixture(target_next=False)
        result = audit.analyze(markets, self.ends, stamps, self.splits)
        row = result['daily'][0]
        self.assertEqual(row['joint_H3_contract_days_upper_bound'], 1)
        self.assertEqual(row['joint_H1_contract_days_upper_bound'], 0)
        self.assertFalse(result['proceed'])

    def test_H1_current_and_next_target_intervals(self):
        markets, stamps = self.fixture()
        result = audit.analyze(markets, self.ends, stamps, self.splits)
        self.assertEqual(result['daily'][0]['joint_H1_contract_days_upper_bound'], 1)

    def test_missing_source_is_not_zero_filled(self):
        markets, stamps = self.fixture(cpi=False)
        result = audit.analyze(markets, self.ends, stamps, self.splits)
        self.assertEqual(result['daily'][0]['fed_covered_contract_days'], 1)
        self.assertEqual(result['daily'][0]['joint_H3_contract_days_upper_bound'], 0)
        self.assertEqual(result['inventory'][0]['development_events_upper_bound'], 0)

    def test_H2_uses_strictly_earlier_completed_window(self):
        markets, stamps = self.fixture()
        markets[-1]['release'] = audit.DAY + 3000
        stamps['target'] = [2600]
        result = audit.analyze(markets, self.ends, stamps, self.splits)
        row = result['t1'][0]
        self.assertEqual(row['feature_end_utc'], audit.utc(2000))
        self.assertEqual(row['fed_contracts_upper_bound'], 0)
        self.assertFalse(row['joint_H2_covered_upper_bound'])

    def test_H2_requires_fresh_target_not_stale_or_future(self):
        markets, stamps = self.fixture()
        markets[-1]['release'] = audit.DAY + 3300
        for target, expected in (([3200], True), ([3301], False), ([3300 - audit.DAY], False)):
            stamps['target'] = target
            result = audit.analyze(markets, self.ends, stamps, self.splits)
            self.assertEqual(result['t1'][0]['joint_H2_covered_upper_bound'], expected)

    def test_empty_markets_are_safe(self):
        result = audit.analyze([], self.ends, {}, self.splits)
        self.assertFalse(result['proceed'])
        self.assertEqual(len(result['inventory']), 6)
        self.assertEqual(result['daily'], [])
        self.assertEqual(result['t1'], [])

    def test_prices_labels_and_entries_are_never_read(self):
        markets, stamps = self.fixture()
        first = audit.analyze(markets, self.ends, stamps, self.splits)
        for market in markets:
            market.update(realized=object(), p0=object(), price=object(), entries=object())
        self.assertEqual(first, audit.analyze(markets, self.ends, stamps, self.splits))

    def test_optional_release_pooling_cannot_double_core_CPI(self):
        releases = {'mom': {'family': 'cpi_core_mom', 'release_ts': 100},
            'yoy': {'family': 'cpi_core_yoy', 'release_ts': 100},
            'gdp': {'family': 'gdp', 'release_ts': 200}}
        markets = {key: SimpleNamespace(event_id=key) for key in releases}
        rows = {row['family']: row for row in audit.optional_inventory(markets, releases)}
        self.assertEqual(rows['core_cpi']['mapped_releases'], 1)
        self.assertEqual(rows['core_cpi']['valid_market_releases_upper_bound'], 1)
        self.assertEqual(rows['pce']['valid_market_releases_upper_bound'], 0)
        self.assertTrue(all(row['decision'].startswith('drop:') for row in rows.values()))

    def test_out_of_population_target_is_excluded(self):
        markets, stamps = self.fixture()
        markets[-1]['event'] = 'payrolls:unregistered'
        result = audit.analyze(markets, self.ends, stamps, self.splits)
        self.assertEqual(result['daily'], [])

    def test_synthetic_minimum_gate_is_ten_and_five_events(self):
        markets = [self.market('fomc', 'fed', release=1000000),
            self.market('cpi', 'cpi', release=1000000)]
        stamps = {'fed': [1500, 2500], 'cpi': [1500, 2500]}
        for phase, count in (('development', 10), ('holdout', 5)):
            self.splits['payrolls'][phase] = []
            for index in range(count):
                event = 'payrolls:' + phase + str(index)
                self.splits['payrolls'][phase].append(event)
                markets.append(self.market('payrolls', event, event=event))
                stamps[event] = [2500, 3500]
        result = audit.analyze(markets, self.ends, stamps, self.splits)
        self.assertTrue(result['proceed'])
        stamps['payrolls:holdout4'] = []
        self.assertFalse(audit.analyze(markets, self.ends, stamps, self.splits)['proceed'])


if __name__ == '__main__':
    unittest.main()
