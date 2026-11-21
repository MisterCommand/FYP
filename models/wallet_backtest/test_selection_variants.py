import sqlite3
import unittest

from build_panel import DAY, create_tables, normalize_trade, select_cohorts, wallet_scores
from selection_variants import (
    SELECTORS, cohorts, install_resolution_times, paired_difference, score_cache_key, score_variants,
)
from test_build_panel import insert, market, record


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.cutoff = 100 * DAY
        self.markets = {str(i): market(market_id=str(i), event_id=str(i * 10),
            resolved_ts=(21 + i * 10) * DAY) for i in range(1, 6)}
        self.markets["6"] = market(market_id="6", event_id="60", resolved_ts=self.cutoff)
        self.markets["7"] = market(market_id="7", event_id="70", resolved_ts=self.cutoff + DAY)
        create_tables(self.db, self.markets)
        install_resolution_times(self.db, self.markets)

    def add_history(self):
        for m in list(self.markets.values())[:5]:
            for i in range(5):
                insert(self.db, m, timestamp=m.resolved_ts - 10 * DAY + i)
        return record()["proxy_wallet"]

    def test_every_selector_excludes_unresolved_and_at_or_after_cutoff_trades(self):
        wallet = self.add_history()
        expected = score_variants(self.db, self.cutoff)
        for selector in SELECTORS:
            with self.subTest(selector=selector):
                self.assertIn(wallet, expected[selector])
        for m in self.markets.values():
            for i in range(25):
                insert(self.db, m, timestamp=self.cutoff + i, size=100000, price=.01)
        for m in (self.markets["6"], self.markets["7"]):
            for i in range(25):
                insert(self.db, m, timestamp=80 * DAY + i, proxy_wallet="0x" + "3" * 40)
        self.db.execute("UPDATE markets SET realized=0 WHERE market_id IN ('6', '7')")
        actual = score_variants(self.db, self.cutoff)
        for selector in SELECTORS:
            with self.subTest(selector=selector):
                self.assertEqual(actual[selector], expected[selector])
        self.db.execute("UPDATE markets SET realized=0 WHERE market_id='5'")
        changed = score_variants(self.db, self.cutoff)
        for selector in ("baseline", "hit_rate", "strict", "early_edge", "recent"):
            with self.subTest(selector=selector):
                self.assertNotEqual(changed[selector][wallet]["score"], expected[selector][wallet]["score"])
        self.assertEqual(changed["whale"], expected["whale"])

    def test_baseline_is_exactly_original_and_strict_requires_twenty_trades(self):
        wallet = self.add_history()
        scores = score_variants(self.db, self.cutoff)
        self.assertEqual(scores["baseline"], wallet_scores(self.db, self.cutoff))
        self.assertEqual(scores["strict"][wallet]["n_trades"], 25)
        self.db.execute("DELETE FROM trades WHERE market_id IN ('1', '2')")
        self.assertEqual(score_variants(self.db, self.cutoff)["strict"], {})

    def test_hit_rate_direction_and_chance_level_shrinkage(self):
        m = self.markets["1"]
        for i, (token, side) in enumerate(((m.yes_token, "BUY"), (m.yes_token, "BUY"),
                (m.no_token, "SELL"), (m.yes_token, "SELL"), (m.no_token, "BUY"))):
            trade = normalize_trade(record(condition_id=m.condition_id, timestamp=20 * DAY + i,
                                           token_id=token, side=side), m)
            self.db.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(trade.__dict__.values()))
        score = score_variants(self.db, self.cutoff)["hit_rate"][record()["proxy_wallet"]]
        self.assertAlmostEqual(score["score"], .5 + (.6 - .5) * 5 / 25)
        self.assertEqual(score["notional"], 20)

    def test_whale_is_size_not_skill_and_allows_one_positive_notional_trade(self):
        m = self.markets["1"]
        wallet = self.add_history()
        other = "0x" + "3" * 40
        insert(self.db, m, timestamp=20 * DAY, proxy_wallet=other, side="SELL", size=1000)
        scores = score_variants(self.db, self.cutoff)
        self.assertGreater(scores["whale"][other]["score"], scores["whale"][wallet]["score"])
        self.assertNotIn(other, scores["baseline"])

    def test_early_edge_seven_day_boundary_uses_individual_market_resolution(self):
        m = self.markets["1"]
        for i in range(5):
            insert(self.db, m, timestamp=m.resolved_ts - 10 * DAY + i)
        boundary = m.resolved_ts - 7 * DAY
        insert(self.db, m, timestamp=boundary)
        insert(self.db, m, timestamp=boundary + 1)
        self.db.execute("UPDATE markets SET resolved_ts=? WHERE market_id='1'", (m.resolved_ts + 10 * DAY,))
        scores = score_variants(self.db, self.cutoff)
        wallet = record()["proxy_wallet"]
        self.assertEqual(scores["baseline"][wallet]["n_trades"], 7)
        self.assertEqual(scores["early_edge"][wallet]["n_trades"], 6)

    def test_recent_uses_last_four_resolved_meetings_even_if_empty(self):
        wallet = self.add_history()
        self.assertEqual(score_variants(self.db, self.cutoff)["recent"][wallet]["n_trades"], 20)
        self.db.execute("DELETE FROM trades WHERE market_id='5'")
        self.assertEqual(score_variants(self.db, self.cutoff)["recent"][wallet]["n_trades"], 15)
        self.db.execute("UPDATE markets SET realized=0 WHERE market_id='1'")
        self.assertEqual(score_variants(self.db, self.cutoff)["recent"][wallet]["n_trades"], 15)
        self.assertNotEqual(score_variants(self.db, self.cutoff)["recent"][wallet]["score"],
                            score_variants(self.db, self.cutoff)["baseline"][wallet]["score"])

    def test_score_cache_is_invariant_to_future_rows_but_not_new_eligible_history(self):
        self.add_history()
        before = score_cache_key(self.db, self.cutoff)
        insert(self.db, self.markets["1"], timestamp=self.cutoff)
        insert(self.db, self.markets["7"], timestamp=self.cutoff - DAY)
        self.assertEqual(score_cache_key(self.db, self.cutoff), before)
        insert(self.db, self.markets["1"], timestamp=self.cutoff - 1)
        self.assertNotEqual(score_cache_key(self.db, self.cutoff), before)

    def test_each_selector_empty_history_is_unavailable(self):
        scores = score_variants(self.db, self.cutoff)
        for selector in SELECTORS:
            with self.subTest(selector=selector):
                self.assertEqual(scores[selector], {})
                self.assertEqual(cohorts(scores[selector], selector, "10", self.cutoff), (None, None))
        with self.assertRaises(ValueError):
            cohorts({}, "unknown", "10", self.cutoff)

    def test_every_selector_gate_and_own_seeded_size_matched_placebo(self):
        scores = {str(i): {"score": i} for i in range(400)}
        placebos = []
        for selector in SELECTORS:
            with self.subTest(selector=selector):
                smart, placebo = cohorts(scores, selector, "10", self.cutoff)
                n = 20 if selector == "strict" else 40
                self.assertEqual(smart, {str(i) for i in range(400 - n, 400)})
                self.assertEqual(len(placebo), n)
                self.assertTrue(placebo <= scores.keys())
                self.assertEqual(cohorts(dict(reversed(list(scores.items()))), selector, "10", self.cutoff), (smart, placebo))
                minimum = 399 if selector == "strict" else 199
                small = {str(i): {"score": i} for i in range(minimum)}
                self.assertEqual(cohorts(small, selector, "10", self.cutoff), (None, None))
                placebos.append(frozenset(placebo))
        self.assertEqual(len(set(placebos)), len(SELECTORS))
        self.assertEqual(cohorts(scores, "baseline", "10", self.cutoff), select_cohorts(scores, "10", self.cutoff))


class ComparisonTests(unittest.TestCase):
    def test_paired_differences_use_own_placebo_and_cluster_by_meeting(self):
        rows = []
        for meeting, days, losses in (("2024-01", 1, (2, 1, 4)),
                ("2024-01", 3, (10, 9, 12)), ("2024-03", 1, (0, 4, 0))):
            rows.extend({"meeting": meeting, "cutoff_days": days, "variant": variant, "brier": value}
                        for variant, value in zip(("smart", "market", "placebo"), losses))
        self.assertEqual(paired_difference(rows, "brier", "market"), (-1.5, -4., 1.))
        self.assertEqual(paired_difference(rows, "brier", "placebo"), (-1., -2., 0.))
        self.assertEqual(paired_difference(rows, "brier", "market", horizon=3), (1., 1., 1.))
        self.assertEqual(paired_difference(rows, "brier", "market", {"2024-03"}), (-4., -4., -4.))

    def test_empty_comparisons_and_missing_comparator(self):
        self.assertEqual(paired_difference([], "brier", "market"), (None, None, None))
        with self.assertRaises(KeyError):
            paired_difference([{"meeting": "2024-01", "cutoff_days": 3, "variant": "smart", "brier": .2}],
                              "brier", "market")


if __name__ == "__main__":
    unittest.main()
