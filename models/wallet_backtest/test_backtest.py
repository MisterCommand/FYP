import csv
from dataclasses import replace
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from backtest import (
    Observation, VARIANTS, Window, accuracy_summary, adjusted_probabilities,
    bootstrap_ci, fit_at, fit_offset, kupiec, load_prices, make_windows,
    mixture, outcome_matches, return_metrics, scenario_estimates, weight,
)
from build_panel import timestamp


def observation(meeting, outcome="No change", realized=1, signal=.8, **kwargs):
    result = Observation(meeting, 3, 100, 200, outcome, "1", .5, realized,
                         {s: signal for s in ("smart", "placebo", "all")})
    return replace(result, **kwargs)


def training():
    result = []
    for month in ("2023-01", "2023-03", "2023-05"):
        result.extend((observation(month), observation(month, outcome="25 bps increase", realized=0, signal=-.8)))
    return result


class CalibrationTests(unittest.TestCase):
    def test_walk_forward_beta_ignores_target_future_unresolved_and_late_cutoff_rows(self):
        rows = training()
        expected = fit_at(rows, "2024-01", 1000, "smart")
        self.assertGreater(expected[0], 0)
        self.assertEqual(expected[1:], (3, 6))
        excluded = [observation("2024-01", cutoff=900, resolved=950),
                    observation("2025-01", cutoff=900, resolved=950),
                    observation("2023-07", resolved=1000),
                    observation("2023-09", resolved=1100),
                    observation("2023-11", cutoff=1000)]
        mutated = [replace(r, realized=0, signals={s: -1. for s in r.signals}) for r in excluded]
        self.assertEqual(fit_at(rows + excluded, "2024-01", 1000, "smart"), expected)
        self.assertEqual(fit_at(rows + mutated, "2024-01", 1000, "smart"), expected)
        reversed_labels = [replace(r, realized=1-r.realized) for r in rows]
        self.assertLess(fit_at(reversed_labels, "2024-01", 1000, "smart")[0], 0)

    def test_beta_fallback_and_unavailable_training(self):
        rows = training()
        self.assertEqual(fit_at(rows[:4], "2024-01", 1000, "smart")[0], 0)
        self.assertEqual(fit_at([replace(r, usable=False) for r in rows], "2024-01", 1000, "smart"), (0, 0, 0))
        self.assertEqual(fit_at([], "2024-01", 1000, "smart"), (0, 0, 0))
        np.testing.assert_array_equal(adjusted_probabilities([0, .4, 1], [1, -1, 0], 0), np.array([0, .4, 1]) / 1.4)

    def test_offset_fit_penalty_and_normalized_tilt(self):
        rows = training()
        self.assertLess(abs(fit_offset(rows, "smart", 100)), abs(fit_offset(rows, "smart", .1)))
        p = adjusted_probabilities([.4, .6], [1, -1], .5)
        self.assertAlmostEqual(p.sum(), 1)
        self.assertGreater(p[0], .4)
        for args in (([], "smart", 1), (rows, "smart", 0)):
            with self.assertRaises(ValueError):
                fit_offset(*args)
        with self.assertRaises(ValueError):
            adjusted_probabilities([.5, .5], [2, 0], .5)
        with self.assertRaises(ValueError):
            adjusted_probabilities([0, 0], [0, 0], 0)


class ScenarioTests(unittest.TestCase):
    def history(self):
        windows, meetings = {}, {}
        for i, value in enumerate((.01, .02, -.01)):
            label = f"2023-0{i+1}"
            windows[(label, 3)] = Window(label, 3, 100 + i, 90, 150, "No change", value)
            meetings[label] = {"resolved": 160}
        current = Window("2024-01", 3, 1000, 900, 1100, "No change", .7)
        meetings[current.meeting] = {"resolved": 1200}
        windows[(current.meeting, 3)] = current
        return windows, meetings, current

    def test_scenarios_exclude_future_labels_returns_and_unfinished_prior_windows(self):
        windows, meetings, current = self.history()
        outcomes = ["No change", "25 bps increase"]
        expected = scenario_estimates(windows, meetings, current, 900, outcomes)
        self.assertEqual(expected[0]["n_conditional"], 3)
        self.assertFalse(expected[0]["pooled_fallback"])
        self.assertAlmostEqual(expected[0]["mean"], .02 / 3)
        self.assertTrue(expected[1]["pooled_fallback"])
        for name, decision, exit_ts, resolved in (("future", 2000, 2100, 2200),
                                                ("unfinished", 500, 900, 600),
                                                ("unresolved", 500, 600, 900)):
            windows[(name, 3)] = Window(name, 3, decision, 400, exit_ts, "25 bps increase", -999.)
            meetings[name] = {"resolved": resolved}
        windows[("other_horizon", 7)] = Window("other_horizon", 7, 100, 90, 150, "No change", 999.)
        meetings["other_horizon"] = {"resolved": 160}
        self.assertEqual(scenario_estimates(windows, meetings, current, 900, outcomes), expected)
        current = replace(current, value=-999., realized_outcome="25 bps increase")
        windows[(current.meeting, 3)] = current
        self.assertEqual(scenario_estimates(windows, meetings, current, 900, outcomes), expected)
        first = windows[("2023-01", 3)]
        windows[("2023-01", 3)] = replace(first, value=.5)
        self.assertNotEqual(scenario_estimates(windows, meetings, current, 900, outcomes), expected)

    def test_empty_scenario_history_fails_and_sparse_conditionals_use_pooled_variance(self):
        windows, meetings, current = self.history()
        with self.assertRaises(ValueError):
            scenario_estimates({}, meetings, current, 900, ["No change"])
        windows.pop(("2023-01", 3))
        values = scenario_estimates(windows, meetings, current, 900, ["No change", "other"])
        self.assertTrue(all(v["pooled_fallback"] for v in values))
        self.assertAlmostEqual(values[0]["variance"], np.var([.02, -.01], ddof=1))
        self.assertTrue(outcome_matches("50+ bps decrease", "75+ bps decrease"))
        self.assertFalse(outcome_matches("50 bps decrease", "50+ bps decrease"))
        self.assertFalse(outcome_matches("other", "No change"))

    def test_entry_uses_actual_prior_close_not_future_close_on_cutoff_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            with path.open("w") as handle:
                writer = csv.writer(handle)
                writer.writerow(["date", "ticker", "close"])
                for day, close in ((3, 90), (7, 95), (10, 100), (11, 120), (12, 130), (13, 110), (14, 99)):
                    writer.writerow([f"2024-06-{day:02d}T00:00:00+00:00", "SPY", close])
            prices = load_prices(path)
            meetings = {"2024-06": {"decision": timestamp("2024-06-12T00:00:00Z"), "winner": "No change"}}
            window = make_windows(meetings, prices)[("2024-06", 1)]
            self.assertEqual(window.entry, timestamp("2024-06-10T20:00:00Z"))
            self.assertEqual(window.exit, timestamp("2024-06-13T20:00:00Z"))
            self.assertAlmostEqual(window.value, .1)

    def test_mixture_variance_includes_between_scenario_variance(self):
        mean, sigma, var = mixture([.5, .5], [{"mean": .01, "variance": .0004}, {"mean": .03, "variance": .0009}])
        self.assertAlmostEqual(mean, .02)
        self.assertAlmostEqual(sigma**2, .00075)
        self.assertGreater(var, 0)
        self.assertEqual(weight("vol_target", .01, .02), .5)
        self.assertEqual(weight("mean_variance", -.01, .02), 0)
        self.assertEqual(weight("mean_variance", .01, 0), 1)


class MetricsTests(unittest.TestCase):
    def test_cluster_bootstrap_keeps_cutoffs_together_and_sign_counts_use_meetings(self):
        accuracy = []
        for meeting, diff in (("a", -1.), ("b", 1.)):
            for days in (7, 3, 1):
                for variant in VARIANTS:
                    value = 0. if variant == "market" else diff
                    accuracy.append({"meeting": meeting, "cutoff_days": days, "variant": variant,
                                     "brier": 1 + value, "log_loss": 1 + value,
                                     "delta_brier": value, "delta_log_loss": value})
        row = next(r for r in accuracy_summary(accuracy) if r["cutoff_days"] == "pooled" and r["variant"] == "smart")
        self.assertEqual(row["n_meetings"], 2)
        self.assertEqual((row["brier_ci_low"], row["brier_ci_high"]), (-1, 1))
        self.assertEqual((row["brier_better"], row["brier_worse"], row["brier_ties"]), (1, 1, 0))

    def test_kupiec_boundaries_and_path_drawdown(self):
        self.assertEqual(kupiec(20, 1), 1)
        self.assertAlmostEqual(kupiec(14, 0), math.erfc(math.sqrt(-14 * math.log(.95))))
        self.assertTrue(0 <= kupiec(14, 14) < .001)
        metrics = return_metrics([-.1, .1])
        self.assertAlmostEqual(metrics["max_drawdown"], -.1)
        self.assertAlmostEqual(metrics["total_return"], -.01)
        self.assertEqual(bootstrap_ci([0] * 14), (0, 0))
        with self.assertRaises(ValueError):
            bootstrap_ci([])


if __name__ == "__main__":
    unittest.main()
