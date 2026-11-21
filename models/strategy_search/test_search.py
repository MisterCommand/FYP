import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from search import (FOLDER, IDS, advance, calibrated, claim_holdout, corrected_windows,
    digest, direction, evaluate, first_trade, fit_calibration, holdout, holm, metrics, permutation_p,
    pm_return, prior_price, registration, timestamp)
from build_panel import DAY, create_tables, normalize_trade
from test_build_panel import market, record


class EntryTests(unittest.TestCase):
    def test_pm_entry_is_strictly_after_cutoff_and_before_decision_for_chosen_token(self):
        m = market()
        with sqlite3.connect(":memory:") as db:
            create_tables(db, {"1": m})
            for t, token, price in ((99, m.yes_token, .1), (100, m.yes_token, .2),
                    (101, m.no_token, .7), (102, m.yes_token, .3), (103, m.yes_token, .4),
                    (110, m.yes_token, .9)):
                trade = normalize_trade(record(timestamp=t, token_id=token, price=price), m)
                db.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(trade.__dict__.values()))
            self.assertEqual(first_trade(db, "1", "YES", 100, 110), (102, .3))
            self.assertEqual(first_trade(db, "1", "NO", 100, 110), (101, .7))
            self.assertEqual(prior_price(db, "1", 100), .1)
            self.assertIsNone(first_trade(db, "1", "YES", 109, 110))
            self.assertIsNone(prior_price(db, "missing", 100))

    def test_spy_entry_uses_next_close_and_exit_strictly_after_decision_day(self):
        decision = timestamp("2026-03-18T00:00:00Z")
        cutoff = decision - 3 * DAY
        prices = [(cutoff - 1, 100.), (cutoff, 101.), (cutoff + 1, 102.),
                  (decision + 20 * 3600, 103.), (decision + DAY + 20 * 3600, 104.)]
        result = corrected_windows({"2026-03": {"decision": decision, "winner": "No change"}}, prices)
        window = result[("2026-03", 3)]
        self.assertEqual(window.entry, cutoff + 1)
        self.assertEqual(window.exit, decision + DAY + 20 * 3600)
        self.assertAlmostEqual(window.value, 104 / 102 - 1)
        self.assertEqual(corrected_windows({"2026-03": {"decision": decision, "winner": "No change"}}, []), {})

    def test_pm_binary_settlement_costs_flats_and_unprofitable_entry(self):
        item = {"entries": {"YES": (1, .4), "NO": (2, .6)}, "realized": 1}
        self.assertAlmostEqual(pm_return(1, item, .02)[0], 1 / .42 - 1)
        self.assertEqual(pm_return(-1, item, .02), (-1., True))
        self.assertEqual(pm_return(0, item, .02), (0., False))
        item["entries"]["YES"] = (1, .99)
        self.assertEqual(pm_return(1, item, .02), (0., False))


class CalibrationTests(unittest.TestCase):
    def history(self):
        return [{"meeting": f"2024-{i:02d}", "cutoff": i * DAY, "resolved": (i + 1) * DAY,
                 "p_trade": p, "realized": y} for i in range(1, 4) for p, y in ((.1, 0), (.7, 1))]

    def test_calibration_excludes_current_future_unresolved_and_at_cutoff_rows(self):
        history = self.history()
        expected = fit_calibration(history, "2024-05", 10 * DAY)
        bad = [{"meeting": "2024-05", "cutoff": DAY, "resolved": 2 * DAY, "p_trade": .999, "realized": 0},
               {"meeting": "2025-01", "cutoff": DAY, "resolved": 2 * DAY, "p_trade": .999, "realized": 0},
               {"meeting": "2024-01", "cutoff": DAY, "resolved": 10 * DAY, "p_trade": .999, "realized": 0},
               {"meeting": "2024-01", "cutoff": 10 * DAY, "resolved": 2 * DAY, "p_trade": .999, "realized": 0}]
        self.assertEqual(fit_calibration(history + bad, "2024-05", 10 * DAY), expected)
        changed = copy.deepcopy(history)
        changed[0]["realized"] = 1
        self.assertNotEqual(fit_calibration(changed, "2024-05", 10 * DAY), expected)
        self.assertTrue(expected[1])

    def test_calibration_minimum_empty_and_missing_snapshots(self):
        self.assertEqual(fit_calibration([], "2024-05", 10 * DAY), ((0., 1.), False))
        history = self.history()
        for row in history:
            if row["meeting"] == "2024-03":
                row["p_trade"] = None
        self.assertEqual(fit_calibration(history, "2024-05", 10 * DAY), ((0., 1.), False))
        self.assertAlmostEqual(calibrated(.6, (0., 1.)), .6)

    def test_holdout_uses_frozen_calibration_without_refitting(self):
        spec = json.loads((FOLDER / "registration.json").read_text())
        item = {"meeting": "2026-03", "market_id": "1", "entries": {"YES": (100, .6), "NO": (101, .4)},
            "p_trade": .7, "p_previous": .6, "realized": 1, "smart": 1., "all": -.2,
            "late_whale": .5, "placebo": -.1}
        states = [{"meeting": "2026-03", "cutoff": 99, "markets": [item], "window": None}]
        with patch("search.fit_calibration", side_effect=AssertionError("holdout refit")):
            rows = evaluate("d_calibration_pm", states, spec, [], {}, {},
                            {"theta": (1., 1.), "fitted": True, "beta": 0.})
        self.assertEqual(rows[0]["traded"], 1)


class SignalTests(unittest.TestCase):
    def test_registered_pm_signal_directions_and_missing_momentum(self):
        spec = json.loads((FOLDER / "registration.json").read_text())
        item = {"smart": .4, "all": -.6, "p_trade": .6, "p_previous": .5,
                "late_whale": -.2, "placebo": .3}
        for name in ("a_smart_pm", "b_contrarian_pm", "c_momentum_pm", "h_placebo_pm"):
            self.assertGreater(direction(name, item, (0., 1.), True, spec), 0)
        self.assertLess(direction("e_late_whale_pm", item, (0., 1.), True, spec), 0)
        self.assertGreater(direction("d_calibration_pm", item, (1., 1.), True, spec), 0)
        self.assertEqual(direction("d_calibration_pm", item, (1., 1.), False, spec), 0)
        item["p_previous"] = None
        self.assertEqual(direction("c_momentum_pm", item, (0., 1.), True, spec), 0)
        with self.assertRaises(ValueError):
            direction("new_strategy", item, (0., 1.), True, spec)


class InferenceAndLockTests(unittest.TestCase):
    def spec(self):
        return json.loads((FOLDER / "registration.json").read_text())

    def development(self):
        return {name: {"metric": .1, "p": .05 if name in ("a_smart_pm", "g_wallet_control") else .5} for name in IDS}

    def test_registry_is_committed_and_g_never_advances(self):
        spec = registration()
        self.assertEqual(tuple(s["id"] for s in spec["strategies"]), IDS)
        self.assertEqual(advance(spec, self.development()), ["a_smart_pm"])

    def test_crlf_registration_passes_but_content_change_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            for name in ("registration.json", "PREREGISTRATION.md"):
                original = (FOLDER / name).read_bytes().replace(b"\r\n", b"\n")
                (target / name).write_bytes(original.replace(b"\n", b"\r\n"))
            with patch("search.FOLDER", target):
                self.assertEqual(registration(), self.spec())
                path = target / "registration.json"
                path.write_bytes(path.read_bytes().replace(b'"version": 1', b'"version": 2'))
                with self.assertRaisesRegex(ValueError, "preregistration has changed"):
                    registration()

    def test_digest_normalizes_text_line_endings_but_preserves_content_and_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            for suffix in (".json", ".md", ".py", ".csv", ".txt", ".sqlite3"):
                path = Path(folder) / ("input" + suffix)
                path.write_bytes(b"first\nsecond\n")
                original = digest(path)
                path.write_bytes(b"first\r\nsecond\r\n")
                if suffix == ".sqlite3":
                    self.assertNotEqual(digest(path), original)
                else:
                    self.assertEqual(digest(path), original)
                path.write_bytes(b"changed\nsecond\n")
                self.assertNotEqual(digest(path), original)

    def test_holdout_only_accepts_listed_advanced_strategies_and_claims_once(self):
        spec, dev = self.spec(), self.development()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lock.json"
            with self.assertRaisesRegex(ValueError, "unregistered"):
                claim_holdout(path, spec, dev, ["new_strategy"], {})
            self.assertFalse(path.exists())
            with self.assertRaisesRegex(ValueError, "gate"):
                claim_holdout(path, spec, dev, ["b_contrarian_pm"], {})
            self.assertFalse(path.exists())
            self.assertEqual(claim_holdout(path, spec, dev, ["a_smart_pm"], {}), ["a_smart_pm"])
            with self.assertRaises(FileExistsError):
                claim_holdout(path, spec, dev, ["a_smart_pm"], {})
        with self.assertRaisesRegex(ValueError, "preregistered"):
            evaluate("new_strategy", [], spec, [], {}, {})

    def test_exact_cluster_permutation_holm_and_equal_meeting_weighting(self):
        self.assertEqual(permutation_p("a_smart_pm", [1.] * 5, [0.] * 5), 1 / 32)
        self.assertEqual(permutation_p("a_smart_pm", [], []), 1.)
        self.assertEqual(permutation_p("a_smart_pm", [0.] * 5, [0.] * 5), 1.)
        self.assertEqual(holm({"a": .01, "b": .03, "c": .2}), {"a": .03, "b": .06, "c": .2})
        self.assertEqual(holm({}), {})
        rows = [{"meeting": "a", "net_return": 1., "benchmark_return": 0., "traded": 1}] * 3
        rows += [{"meeting": "b", "net_return": -1., "benchmark_return": 0., "traded": 1}]
        stats = metrics("a_smart_pm", rows)
        self.assertEqual(stats["metric"], 0.)
        self.assertEqual(stats["n_meetings"], 2)
        self.assertEqual(metrics("a_smart_pm", [])["p"], 1.)

    def test_holdout_rejects_unknown_strategy_or_changed_inputs_before_reading_data(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            manifest = {"results": self.development(), "advanced": ["new_strategy"], "input_hashes": {"code": "one"}}
            path = work / "development.json"
            path.write_text(json.dumps(manifest))
            with patch("search.inputs", return_value={"code": "one"}), patch("search.prepare") as loader:
                with self.assertRaisesRegex(ValueError, "unregistered"):
                    holdout(work, self.spec(), work)
                loader.assert_not_called()
            manifest["advanced"] = ["a_smart_pm"]
            path.write_text(json.dumps(manifest))
            with patch("search.inputs", return_value={"code": "two"}), patch("search.prepare") as loader:
                with self.assertRaisesRegex(ValueError, "changed"):
                    holdout(work, self.spec(), work)
                loader.assert_not_called()
            self.assertFalse((work / "holdout_lock.json").exists())


if __name__ == "__main__":
    unittest.main()
