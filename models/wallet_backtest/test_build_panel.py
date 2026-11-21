import csv
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from build_panel import (
    DAY, Market, aggregate_flow, build_panel, create_tables, load_markets,
    normalize_trade, probability_at, resolution_time, select_cohorts,
    settlement_pnl, timestamp, wallet_scores, window_flows,
)


def market(**kwargs):
    result = Market("1", "10", "2024-01", "No change", "0x" + "a" * 64,
                    "123456789012345678901234567890", "987654321098765432109876543210",
                    30 * DAY, 31 * DAY, "closedTime", 1, 1., ((DAY, .4), (20 * DAY, .6)))
    return replace(result, **kwargs)


def record(**kwargs):
    result = {"condition_id": market().condition_id, "token_id": market().yes_token,
              "proxy_wallet": "0x" + "1" * 40, "transaction_hash": "0x" + "2" * 64,
              "side": "BUY", "size": 10, "price": .4, "timestamp": 10 * DAY}
    result.update(kwargs)
    return result


def insert(db, m, **kwargs):
    row = record(condition_id=m.condition_id, token_id=m.yes_token, **kwargs)
    trade = normalize_trade(row, m)
    db.execute("INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(trade.__dict__.values()))
    return trade


class TradeTests(unittest.TestCase):
    def test_yes_no_buy_sell_pnl_and_notional(self):
        for yes, side, sign, expected_pnl in (
                (True, "BUY", 1, 6), (True, "SELL", -1, -6),
                (False, "BUY", -1, -4), (False, "SELL", 1, 4)):
            with self.subTest(yes=yes, side=side):
                trade = normalize_trade(record(token_id=market().yes_token if yes else market().no_token,
                                               side=side), market())
                self.assertEqual(trade.signed_yes_shares, sign * 10)
                self.assertEqual(trade.notional, 4)
                self.assertEqual(trade.signed_yes_notional, sign * 4)
                self.assertAlmostEqual(settlement_pnl(trade.signed_yes_shares, trade.price, 1), expected_pnl)
                self.assertAlmostEqual(settlement_pnl(trade.signed_yes_shares, trade.price, 0),
                                       -4 if side == "BUY" and yes else
                                       4 if side == "SELL" and yes else
                                       6 if side == "BUY" else -6)

    def test_dedup_ignores_profiles_not_distinct_participants_or_sides(self):
        with sqlite3.connect(":memory:") as db:
            create_tables(db, {"1": market()})
            insert(db, market())
            insert(db, market(), size=10.0, price=.400, name="new profile")
            insert(db, market(), proxy_wallet="0x" + "3" * 40)
            insert(db, market(), side="SELL")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM wallet_trades").fetchone()[0], 3)

    def test_invalid_records_fail_loudly(self):
        for kwargs in ({"token_id": "unknown"}, {"condition_id": "wrong"},
                       {"side": "HOLD"}, {"size": 0}, {"price": 1.1},
                       {"price": "NaN"}, {"proxy_wallet": "not a wallet"}, {"timestamp": 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                normalize_trade(record(**kwargs), market())


class PointInTimeTests(unittest.TestCase):
    def test_skill_excludes_unresolved_meetings_and_at_or_after_cutoff_trades(self):
        cutoff = 60 * DAY
        old = market()
        current = market(market_id="2", event_id="20", resolved_ts=cutoff + 1)
        boundary = market(market_id="3", event_id="30", resolved_ts=cutoff)
        with sqlite3.connect(":memory:") as db:
            create_tables(db, {m.market_id: m for m in (old, current, boundary)})
            for i in range(5):
                insert(db, old, timestamp=10 * DAY + i)
                insert(db, current, timestamp=10 * DAY + i, proxy_wallet="0x" + "3" * 40)
                insert(db, boundary, timestamp=10 * DAY + i, proxy_wallet="0x" + "4" * 40)
            insert(db, old, timestamp=cutoff, price=.01, size=100000)
            insert(db, old, timestamp=cutoff + 1, price=.01, size=100000)
            scores = wallet_scores(db, cutoff)
            self.assertEqual(list(scores), [record()["proxy_wallet"]])
            score = next(iter(scores.values()))
            self.assertEqual(score["n_trades"], 5)
            self.assertAlmostEqual(score["pnl"], 30)
            self.assertAlmostEqual(score["notional"], 20)
            self.assertAlmostEqual(score["score"], 1.5 * 5 / 25)
            db.execute("UPDATE markets SET realized = 0 WHERE market_id != '1'")
            self.assertEqual(wallet_scores(db, cutoff), scores)

    def test_whole_meeting_must_be_resolved(self):
        cutoff = 60 * DAY
        early, late = market(resolved_ts=cutoff - 1), market(market_id="2", resolved_ts=cutoff + 1)
        with sqlite3.connect(":memory:") as db:
            create_tables(db, {"1": early, "2": late})
            for i in range(5):
                insert(db, early, timestamp=10 * DAY + i)
            self.assertEqual(wallet_scores(db, cutoff), {})

    def test_skill_empty_minimum_trades_and_zero_notional(self):
        with sqlite3.connect(":memory:") as db:
            create_tables(db, {"1": market()})
            self.assertEqual(wallet_scores(db, 60 * DAY), {})
            for i in range(4):
                insert(db, market(), timestamp=10 * DAY + i)
            for i in range(5):
                insert(db, market(), timestamp=11 * DAY + i, proxy_wallet="0x" + "3" * 40, price=0)
            self.assertEqual(wallet_scores(db, 60 * DAY), {})

    def test_flow_window_is_inclusive_start_exclusive_end(self):
        cutoff, start = 60 * DAY, 53 * DAY
        with sqlite3.connect(":memory:") as db:
            create_tables(db, {"1": market()})
            insert(db, market(), timestamp=start - 1, size=10000)
            insert(db, market(), timestamp=start)
            insert(db, market(), timestamp=cutoff - 1, side="SELL", size=5)
            insert(db, market(), timestamp=cutoff, size=10000)
            before = window_flows(db, "1", cutoff)
            result = aggregate_flow(before)
            self.assertEqual(result["n_trades"], 2)
            self.assertEqual(result["n_wallets"], 1)
            self.assertEqual(result["gross_notional"], 6)
            self.assertAlmostEqual(result["signal"], 1 / 3)
            insert(db, market(), timestamp=cutoff + 1, size=100000)
            self.assertEqual(window_flows(db, "1", cutoff), before)
            self.assertEqual(aggregate_flow(before, set())["signal"], 0)
            self.assertEqual(aggregate_flow([])["n_trades"], 0)

    def test_market_probability_includes_cutoff_but_not_future(self):
        m = market(quotes=((10, .1), (20, .2), (21, .9)))
        self.assertEqual(probability_at(m, 20), (20, .2))
        self.assertEqual(probability_at(m, 9), (None, None))

    def test_top_decile_minimum_and_seeded_placebo(self):
        scores = {str(i): {"score": i} for i in range(200)}
        smart, placebo = select_cohorts(scores, "event", 123)
        self.assertEqual(smart, {str(i) for i in range(180, 200)})
        self.assertEqual(len(placebo), len(smart))
        self.assertTrue(placebo <= scores.keys())
        self.assertNotEqual(smart, placebo)
        self.assertEqual(select_cohorts(dict(reversed(list(scores.items()))), "event", 123), (smart, placebo))
        self.assertEqual(select_cohorts(dict(list(scores.items())[:199]), "event", 123), (None, None))
        self.assertEqual(select_cohorts({}, "event", 123), (None, None))

    def test_empty_panel_preserves_unavailable_versus_known_zero_flow(self):
        m = market()
        with sqlite3.connect(":memory:") as db:
            create_tables(db, {"1": m})
            rows, cohorts = build_panel(db, {"1": m}, {m.event_id: 0})
            self.assertEqual(len(rows), 3)
            self.assertEqual([r["cutoff_days"] for r in rows], [7, 3, 1])
            for row in rows:
                self.assertIsNone(row["smart_signal"])
                self.assertIsNone(row["placebo_n_trades"])
                self.assertEqual(row["all_signal"], 0)
                self.assertFalse(row["smart_available"])
            clipped, _ = build_panel(db, {"1": m}, {m.event_id: 100 * DAY})
            self.assertTrue(all(r["all_signal"] is None for r in clipped))


class SettlementTests(unittest.TestCase):
    def test_day_only_resolution_is_conservative_and_naive_times_rejected(self):
        resolved, basis = resolution_time({"closedTime": "2023-02-01 21:02:06+00", "umaEndDate": "February 1, 2023"})
        self.assertEqual(resolved, timestamp("2023-02-02T00:00:00Z"))
        self.assertIn("day_upper_bound", basis)
        with self.assertRaises(ValueError):
            timestamp("2023-02-01")
        with self.assertRaises(ValueError):
            resolution_time({})

    def test_gamma_crosscheck_tolerates_terminal_rounding_but_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows = [{"date": "2024-01-01T00:00:00Z", "event_id": "10", "market_id": "1",
                     "meeting_month": "2024-01", "outcome": "no change", "final_outcome": "1",
                     "market_probability": ".5"}]
            with (path / "probabilities.csv").open("w") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            gamma = {"id": "1", "closed": True, "outcomes": '["Yes", "No"]',
                     "clobTokenIds": '["123456789012345678901234567890", "2"]',
                     "outcomePrices": '["0.9999975", "0.0000025"]', "conditionId": market().condition_id,
                     "closedTime": "2024-01-31T21:00:00Z"}
            (path / "1.json").write_text(json.dumps(gamma))
            loaded = load_markets(path / "probabilities.csv", path, {"2024-01": "2024-01-31"})
            self.assertEqual(loaded["1"].yes_token, "123456789012345678901234567890")
            self.assertEqual(loaded["1"].outcome, "No change")
            gamma["outcomePrices"] = '["0", "1"]'
            (path / "1.json").write_text(json.dumps(gamma))
            with self.assertRaisesRegex(ValueError, "settlement disagrees"):
                load_markets(path / "probabilities.csv", path, {"2024-01": "2024-01-31"})


if __name__ == "__main__":
    unittest.main()
