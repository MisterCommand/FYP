"""Preregistered strategy search with separate development and single-use holdout stages."""

import argparse
from bisect import bisect_right
from collections import defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "models/wallet_backtest"))
from backtest import (Window, adjusted_probabilities, fit_at, load_inputs, load_prices,
                      mixture, scenario_estimates, weight)
from build_panel import (DAY, Market, aggregate_flow, array, create_tables, iso,
                         normalize_trade, resolution_time, select_cohorts, timestamp,
                         wallet_scores, window_flows, write_csv)

PREREG_COMMIT = "a020b802e49483538fcce6e589b117a723dc21b6"
IDS = ("a_smart_pm", "b_contrarian_pm", "c_momentum_pm", "d_calibration_pm",
       "e_late_whale_pm", "f_uncertainty_spy", "g_wallet_control", "h_placebo_pm")


def digest(path):
    result = hashlib.sha256()
    if Path(path).suffix in {".json", ".md", ".py", ".csv", ".txt"}:
        return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read_csv(path):
    with Path(path).open() as handle:
        return list(csv.DictReader(handle))


def registration():
    for name in ("registration.json", "PREREGISTRATION.md"):
        committed = subprocess.check_output(["git", "show", f"{PREREG_COMMIT}:models/strategy_search/{name}"], cwd=ROOT)
        if committed.replace(b"\r\n", b"\n") != (FOLDER / name).read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError("Committed preregistration has changed")
    spec = json.loads((FOLDER / "registration.json").read_text())
    if tuple(s["id"] for s in spec["strategies"]) != IDS:
        raise ValueError("Strategy registry does not match the fixed implementation")
    return spec


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def first_trade(db, market_id, token, cutoff, decision):
    row = db.execute("""SELECT ts, raw_price FROM trades
        WHERE market_id=? AND token_outcome=? AND ts>? AND ts<? ORDER BY ts, dedup_key LIMIT 1""",
        (market_id, token, cutoff, decision)).fetchone()
    return tuple(row) if row else None


def prior_price(db, market_id, cutoff):
    row = db.execute("""SELECT raw_price FROM trades WHERE market_id=? AND token_outcome='YES'
        AND ts<? ORDER BY ts DESC, dedup_key LIMIT 1""", (market_id, cutoff)).fetchone()
    return float(row[0]) if row else None


def corrected_windows(metadata, prices, days=3):
    times = [t for t, _ in prices]
    windows = {}
    for meeting, info in sorted(metadata.items()):
        cutoff = info["decision"] - days * DAY
        index = bisect_right(times, cutoff)
        decision_day = datetime.fromtimestamp(info["decision"], timezone.utc).date()
        exits = [(t, p) for t, p in prices if datetime.fromtimestamp(t, timezone.utc).date() > decision_day]
        if index >= len(prices) or not exits:
            continue
        entry, price = prices[index]
        exit_ts, exit_price = exits[0]
        if entry >= exit_ts:
            continue
        windows[(meeting, days)] = Window(meeting, days, info["decision"], entry, exit_ts,
                                         info["winner"], exit_price / price - 1)
    return windows


def fit_calibration(rows, meeting, cutoff, minimum=3, penalty=1.):
    eligible = [r for r in rows if r["meeting"] < meeting and r["resolved"] < cutoff
                and r["cutoff"] < cutoff and r["p_trade"] is not None]
    if len({r["meeting"] for r in eligible}) < minimum:
        return (0., 1.), False
    p = np.clip([r["p_trade"] for r in eligible], 1e-6, 1 - 1e-6)
    x = np.column_stack((np.ones(len(p)), np.log(p) - np.log1p(-p)))
    y = np.array([r["realized"] for r in eligible])
    center = np.array([0., 1.])
    theta = center.copy()

    def objective(value):
        z = x @ value
        return np.sum(np.logaddexp(0, z) - y * z) + penalty * np.sum((value - center)**2) / 2

    for _ in range(100):
        pred = np.exp(-np.logaddexp(0, -(x @ theta)))
        gradient = x.T @ (pred - y) + penalty * (theta - center)
        if np.max(np.abs(gradient)) < 1e-9:
            return tuple(map(float, theta)), True
        hessian = x.T @ ((pred * (1 - pred))[:, None] * x) + penalty * np.eye(2)
        step = np.linalg.solve(hessian, gradient)
        while objective(theta - step) > objective(theta) and np.max(np.abs(step)) > 1e-12:
            step /= 2
        theta -= step
        if np.max(np.abs(step)) < 1e-10:
            return tuple(map(float, theta)), True
    raise RuntimeError("Calibration fit did not converge")


def calibrated(p, theta):
    p = float(np.clip(p, 1e-6, 1 - 1e-6))
    return float(np.exp(-np.logaddexp(0, -(theta[0] + theta[1] * math.log(p / (1 - p))))))


def pm_return(direction, market, cost):
    if not direction:
        return 0., False
    side = "YES" if direction > 0 else "NO"
    entry = market["entries"][side]
    paid = entry[1] + cost
    if paid >= 1:
        return 0., False
    settlement = market["realized"] if direction > 0 else 1 - market["realized"]
    return settlement / paid - 1, True


def direction(strategy, market, theta, fitted, spec):
    if strategy == "a_smart_pm":
        return market["smart"]
    if strategy == "b_contrarian_pm":
        return -market["all"]
    if strategy == "c_momentum_pm":
        return 0. if market["p_trade"] is None or market["p_previous"] is None else market["p_trade"] - market["p_previous"]
    if strategy == "d_calibration_pm":
        p = market["p_trade"]
        if not fitted or p is None:
            return 0.
        q = calibrated(p, theta)
        if p >= spec["favorite_threshold"] and q > p:
            return 1.
        if p <= spec["longshot_threshold"] and q < p:
            return -1.
        return 0.
    if strategy == "e_late_whale_pm":
        return market["late_whale"]
    if strategy == "h_placebo_pm":
        return market["placebo"]
    raise ValueError("Unregistered PM strategy")


def fresh_cache(data_root):
    folder = data_root / "strategy_search/fresh"
    event_path = folder / "event.json"
    summary_path = folder / "606422/summary.json"
    if not summary_path.exists():
        return None, {}, "Fresh collection unavailable"
    summary = json.loads(summary_path.read_text())
    if summary["status"] != "exhausted":
        return None, {}, "Fresh collection not exhausted"
    event = json.loads(event_path.read_text())
    markets = {}
    for m in event["markets"]:
        prices = dict(zip(array(m["outcomes"]), map(float, array(m["outcomePrices"]))))
        if min(abs(prices["Yes"]), abs(prices["Yes"] - 1)) > 1e-3:
            raise ValueError("Fresh market has no terminal settlement")
        tokens = dict(zip(array(m["outcomes"]), map(str, array(m["clobTokenIds"]))))
        resolved, basis = resolution_time(m)
        item = Market(str(m["id"]), str(event["id"]), "2026-10", m["groupItemTitle"],
            m["conditionId"].lower(), tokens["Yes"], tokens["No"], timestamp("2026-10-28T00:00:00Z"),
            resolved, basis, int(prices["Yes"] > .5), prices["Yes"], ())
        markets[item.market_id] = item
    if sum(m.realized for m in markets.values()) != 1:
        raise ValueError("Fresh meeting must have one winning outcome")
    path = folder / "trades.sqlite3"
    if not path.exists():
        temporary = path.with_suffix(".building")
        if temporary.exists():
            raise ValueError("Incomplete fresh cache; inspect before retry")
        by_condition = {m.condition_id: m for m in markets.values()}
        raw_count = 0
        with sqlite3.connect(temporary) as db:
            create_tables(db, markets)
            for page in sorted((folder / "606422").glob("page_*.json.gz")):
                with gzip.open(page, "rt") as handle:
                    rows = json.load(handle)["response"]["data"]
                raw_count += len(rows)
                trades = [normalize_trade(r, by_condition[r["condition_id"].lower()]) for r in rows]
                db.executemany("INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               [tuple(t.__dict__.values()) for t in trades])
            if raw_count != summary["participant_rows"]:
                raise ValueError("Fresh page count mismatch")
            db.execute("CREATE INDEX market_time ON trades(market_id, ts)")
            db.execute("CREATE INDEX token_time ON trades(market_id, token_outcome, ts)")
            db.execute("INSERT INTO build VALUES (?, ?, ?)",
                       (digest(event_path), raw_count, db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]))
        temporary.replace(path)
    with readonly(path) as db:
        if db.execute("SELECT fingerprint FROM build").fetchone()[0] != digest(event_path):
            raise ValueError("Fresh metadata fingerprint mismatch")
    return path, markets, (f"Fresh October PM collection exhausted: {summary['participant_rows']:,} participant records, "
                          f"{summary['distinct_wallets']:,} wallets, {summary['pages']} pages; SPY window unavailable")


def prepare(meeting_ids, data_root, spec, phase):
    observations, metadata = load_inputs(ROOT / "models/wallet_backtest")
    prices = load_prices(ROOT / "datasets/index_daily.csv")
    fresh_path, fresh_markets, fresh_status = fresh_cache(data_root)
    if fresh_markets:
        metadata["2026-10"] = {"decision": next(iter(fresh_markets.values())).decision_ts,
            "resolved": max(m.resolved_ts for m in fresh_markets.values()),
            "winner": next(m.outcome for m in fresh_markets.values() if m.realized)}
    horizon = max(meeting_ids)
    visible_metadata = {m: v for m, v in metadata.items() if m <= horizon}
    windows = corrected_windows(visible_metadata, prices, spec["cutoff_days"])
    panel = defaultdict(list)
    for r in read_csv(ROOT / "models/wallet_backtest/panel.csv"):
        if r["meeting"] in meeting_ids and int(r["cutoff_days"]) == spec["cutoff_days"]:
            panel[r["meeting"]].append(r)
    if "2026-10" in meeting_ids and fresh_markets:
        panel["2026-10"] = [{"meeting": m.meeting, "event_id": m.event_id, "market_id": m.market_id,
            "outcome": m.outcome, "realized": str(m.realized), "p_market": ""} for m in fresh_markets.values()]
    states, audit = [], []
    with readonly(data_root / "wallet_backtest_cache/trades.sqlite3") as db:
        fresh_db = readonly(fresh_path) if fresh_path else None
        try:
            for meeting in meeting_ids:
                if meeting not in panel:
                    continue
                info = metadata[meeting]
                cutoff = info["decision"] - spec["cutoff_days"] * DAY
                smart, placebo = select_cohorts(wallet_scores(db, cutoff), panel[meeting][0]["event_id"], cutoff)
                if smart is None:
                    raise ValueError("Registered meeting lost its usable smart set")
                source = fresh_db if meeting == "2026-10" else db
                markets = []
                for row in panel[meeting]:
                    mid = row["market_id"]
                    flows = window_flows(source, mid, cutoff)
                    entry = {side: first_trade(source, mid, side, cutoff, info["decision"]) for side in ("YES", "NO")}
                    late = source.execute("""SELECT SUM(signed_yes_notional), SUM(notional) FROM trades
                        WHERE market_id=? AND ts>=? AND ts<? AND notional>=?""",
                        (mid, cutoff - DAY, cutoff, spec["large_trade_notional"])).fetchone()
                    market = {"meeting": meeting, "market_id": mid, "outcome": row["outcome"],
                        "cutoff": cutoff, "resolved": info["resolved"], "realized": int(row["realized"]),
                        "p_market": float(row["p_market"]) if row["p_market"] else None,
                        "p_trade": prior_price(source, mid, cutoff), "p_previous": prior_price(source, mid, cutoff - 7 * DAY),
                        "entries": entry, "late_whale": late[0] / late[1] if late[1] else 0.,
                        **{name: aggregate_flow(flows, members)["signal"]
                           for name, members in (("smart", smart), ("placebo", placebo), ("all", None))}}
                    markets.append(market)
                    window = windows.get((meeting, spec["cutoff_days"]))
                    audit.append({"phase": phase, "meeting": meeting, "market_id": mid, "cutoff_utc": iso(cutoff),
                        "yes_entry_utc": iso(entry["YES"][0]) if entry["YES"] else "",
                        "no_entry_utc": iso(entry["NO"][0]) if entry["NO"] else "",
                        "pm_eligible": all(entry.values()), "n_smart": len(smart),
                        "spy_entry_utc": iso(window.entry) if window else "",
                        "spy_exit_utc": iso(window.exit) if window else ""})
                states.append({"meeting": meeting, "cutoff": cutoff, "markets": markets,
                               "window": windows.get((meeting, spec["cutoff_days"]))})
        finally:
            if fresh_db:
                fresh_db.close()
    return states, audit, observations, metadata, windows, fresh_status


def evaluate(strategy, states, spec, observations, metadata, windows, frozen=None):
    if strategy not in {s["id"] for s in spec["strategies"]}:
        raise ValueError("Strategy is not preregistered")
    dev_obs = [r for r in observations if r.meeting in spec["development"]]
    history, records = [], []
    for state in states:
        meeting, cutoff = state["meeting"], state["cutoff"]
        eligible = [m for m in state["markets"] if all(m["entries"].values())]
        if frozen is None:
            theta, fitted = fit_calibration(history, meeting, cutoff, spec["minimum_fit_meetings"], spec["calibration_l2"])
            beta = fit_at(dev_obs, meeting, cutoff, "smart")[0] if strategy == "g_wallet_control" else 0.
        else:
            theta, fitted, beta = frozen["theta"], frozen["fitted"], frozen["beta"]
        if strategy.endswith("_pm"):
            for market in eligible:
                sign = direction(strategy, market, theta, fitted, spec)
                value, traded = pm_return(sign, market, spec["pm_cost"])
                records.append({"strategy": strategy, "meeting": meeting, "market_id": market["market_id"],
                    "net_return": value, "benchmark_return": 0., "traded": int(traded)})
        elif state["window"]:
            current = state["window"]
            p = [m["p_market"] for m in state["markets"]]
            p = np.array(p, dtype=float)
            p /= p.sum()
            if strategy == "f_uncertainty_spy":
                entropy = -float(np.sum(p[p > 0] * np.log(p[p > 0]))) / math.log(len(p))
                disagreement = np.mean([m["smart"] * m["all"] < 0 for m in state["markets"]])
                exposure = spec["reduced_exposure"] if (entropy >= spec["entropy_threshold"] or
                    disagreement >= spec["disagreement_threshold"]) else 1.
                benchmark = 1.
            elif strategy == "g_wallet_control":
                scenarios = scenario_estimates(windows, metadata, current, cutoff, [m["outcome"] for m in state["markets"]])
                adjusted = adjusted_probabilities(p, [m["smart"] for m in state["markets"]], beta)
                mu, sigma, _ = mixture(adjusted, scenarios)
                exposure = weight("mean_variance", mu, sigma)
                mu, sigma, _ = mixture(p, scenarios)
                benchmark = weight("mean_variance", mu, sigma)
            else:
                raise ValueError("Unregistered SPY strategy")
            net = current.value - 2 * spec["spy_cost_per_side"]
            records.append({"strategy": strategy, "meeting": meeting, "market_id": "SPY",
                "net_return": exposure * net, "benchmark_return": benchmark * net, "traded": int(exposure > 0)})
        history.extend(eligible)
    return records


def sharpe(values):
    values = np.array(values, dtype=float)
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.
    return float(values.mean() / std) if std > 1e-15 else 0.


def statistic(strategy, values, benchmark):
    if strategy == "f_uncertainty_spy":
        return sharpe(values) - sharpe(benchmark)
    return float(np.mean(np.array(values) - np.array(benchmark)))


def permutation_p(strategy, values, benchmark):
    if not values:
        return 1.
    observed = statistic(strategy, values, benchmark)
    count = 0
    for signs in itertools.product((-1, 1), repeat=len(values)):
        signs = np.array(signs)
        if strategy == "f_uncertainty_spy":
            a = np.where(signs > 0, values, benchmark)
            b = np.where(signs > 0, benchmark, values)
            null = statistic(strategy, a, b)
        else:
            null = float(np.mean((np.array(values) - np.array(benchmark)) * signs))
        count += null >= observed - 1e-12
    return count / (2 ** len(values))


def metrics(strategy, records):
    groups = defaultdict(list)
    for row in records:
        groups[row["meeting"]].append(row)
    values = [float(np.mean([r["net_return"] for r in group])) for _, group in sorted(groups.items())]
    benchmark = [float(np.mean([r["benchmark_return"] for r in group])) for _, group in sorted(groups.items())]
    return {"n_meetings": len(values), "n_markets": len(records), "n_trades": sum(r["traded"] for r in records),
        "metric": statistic(strategy, values, benchmark) if values else None,
        "p": permutation_p(strategy, values, benchmark), "net_mean": float(np.mean(values)) if values else None,
        "benchmark_mean": float(np.mean(benchmark)) if values else None,
        "volatility": float(np.std(values, ddof=1)) if len(values) > 1 else None,
        "benchmark_volatility": float(np.std(benchmark, ddof=1)) if len(values) > 1 else None,
        "realized_second_moment": float(np.mean(np.array(values)**2)) if values else None,
        "benchmark_second_moment": float(np.mean(np.array(benchmark)**2)) if values else None,
        "sharpe": sharpe(values) if values else None, "benchmark_sharpe": sharpe(benchmark) if values else None}


def holm(pvalues):
    result, previous = {}, 0.
    ordered = sorted(pvalues, key=lambda k: (pvalues[k], k))
    for i, name in enumerate(ordered):
        previous = max(previous, min(1., (len(ordered) - i) * pvalues[name]))
        result[name] = previous
    return result


def advance(spec, development):
    return [s["id"] for s in spec["strategies"] if s["confirmatory"]
            and development[s["id"]]["metric"] is not None and development[s["id"]]["metric"] > 0
            and development[s["id"]]["p"] < spec["development_alpha"]]


def claim_holdout(path, spec, development, requested, manifest):
    registered = {s["id"] for s in spec["strategies"]}
    if not set(requested) <= registered:
        raise ValueError("Holdout requested an unregistered strategy")
    expected = advance(spec, development)
    if list(requested) != expected:
        raise ValueError("Holdout strategies differ from the preregistered development gate")
    with Path(path).open("x") as handle:
        json.dump({**manifest, "advanced": expected, "descriptive": ["g_wallet_control"], "status": "claimed"}, handle, indent=2)
    return expected


def inputs(data_root):
    paths = [FOLDER / "registration.json", FOLDER / "PREREGISTRATION.md", Path(__file__),
        ROOT / "models/wallet_backtest/build_panel.py", ROOT / "models/wallet_backtest/backtest.py",
        ROOT / "models/wallet_backtest/panel.csv", ROOT / "models/wallet_backtest/settlements.csv",
        ROOT / "datasets/index_daily.csv", data_root / "wallet_backtest_cache/trades.sqlite3"]
    paths += [p for p in (data_root / "strategy_search/fresh/event.json",
        data_root / "strategy_search/fresh/trades.sqlite3", data_root / "strategy_search/fresh/606422/summary.json") if p.exists()]
    return {str(p): digest(p) for p in paths}


def develop(data_root, spec, work):
    if (work / "development.json").exists():
        raise ValueError("Development is frozen; do not overwrite it after screening")
    states, audit, observations, metadata, windows, fresh_status = prepare(spec["development"], data_root, spec, "development")
    output, records = {}, []
    for strategy in IDS:
        rows = evaluate(strategy, states, spec, observations, metadata, windows)
        output[strategy] = metrics(strategy, rows)
        records.extend(rows)
    history = [m for state in states for m in state["markets"] if all(m["entries"].values())]
    theta, fitted = fit_calibration(history, "9999", math.inf, spec["minimum_fit_meetings"], spec["calibration_l2"])
    beta = fit_at([r for r in observations if r.meeting in spec["development"]], "9999", math.inf, "smart")[0]
    rng = np.random.default_rng(spec["seed"])
    null_ps = []
    for _ in range(spec["null_shuffles"]):
        null_records = []
        for state in states:
            eligible = [m for m in state["markets"] if all(m["entries"].values())]
            signals = rng.permutation([m["smart"] for m in eligible])
            for market, sign in zip(eligible, signals):
                value, traded = pm_return(sign, market, spec["pm_cost"])
                null_records.append({"meeting": state["meeting"], "net_return": value,
                                     "benchmark_return": 0., "traded": int(traded)})
        null_ps.append(metrics("a_smart_pm", null_records)["p"])
    ranks = {}
    for primary in {s["primary"] for s in spec["strategies"]}:
        candidates = [s["id"] for s in spec["strategies"] if s["primary"] == primary]
        candidates.sort(key=lambda s: (-(output[s]["metric"] if output[s]["metric"] is not None else -math.inf), s))
        ranks.update({s: rank for rank, s in enumerate(candidates, 1)})
    manifest = {"prereg_commit": PREREG_COMMIT, "input_hashes": inputs(data_root), "results": output,
        "development_rank_within_primary_metric": ranks,
        "frozen": {"theta": theta, "fitted": fitted, "beta": beta}, "advanced": advance(spec, output),
        "dev_shuffle_fraction_p_below_0_10": float(np.mean(np.array(null_ps) < spec["development_alpha"])),
        "fresh_status": fresh_status}
    (work / "development.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_csv(FOLDER / "development_observations.csv", records)
    write_csv(FOLDER / "development_execution.csv", audit)
    print("Development frozen; advanced IDs: " + (", ".join(manifest["advanced"]) or "none"))


def holdout(data_root, spec, work):
    manifest_path = work / "development.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["input_hashes"] != inputs(data_root):
        raise ValueError("Code, preregistration or source data changed since development freeze")
    advanced = claim_holdout(work / "holdout_lock.json", spec, manifest["results"], manifest["advanced"],
        {"prereg_commit": PREREG_COMMIT, "development_sha256": digest(manifest_path),
         "registration_sha256": digest(FOLDER / "registration.json"), "code_sha256": digest(__file__)})
    states, audit, observations, metadata, windows, fresh_status = prepare(
        spec["historical_holdout"] + spec["fresh_holdout"], data_root, spec, "holdout")
    evaluated, fresh, records = {}, {}, []
    for strategy in advanced + ["g_wallet_control"]:
        rows = evaluate(strategy, states, spec, observations, metadata, windows, manifest["frozen"])
        records.extend(rows)
        evaluated[strategy] = metrics(strategy, rows)
        fresh[strategy] = metrics(strategy, [r for r in rows if r["meeting"] in spec["fresh_holdout"]])
    adjusted = holm({s: evaluated[s]["p"] for s in advanced})
    summary = []
    for entry in spec["strategies"]:
        strategy = entry["id"]
        dev, held, new = manifest["results"][strategy], evaluated.get(strategy), fresh.get(strategy)
        passed = (strategy in advanced and held["metric"] is not None and held["metric"] > 0
                  and adjusted[strategy] < spec["holdout_alpha"] and held["net_mean"] > 0)
        fresh_positive = bool(new and new["n_meetings"] and new["metric"] > 0 and new["net_mean"] > 0)
        status = "not advanced" if held is None else "descriptive only" if not entry["confirmatory"] else "fail"
        if passed:
            status = "negative-control pass" if strategy == "h_placebo_pm" else (
                "fresh-corroborated exploratory pass" if fresh_positive else "exploratory, not independently confirmed")
        row = {"strategy": strategy, "primary_metric": entry["primary"],
            "dev_rank": manifest["development_rank_within_primary_metric"][strategy], "dev_n": dev["n_meetings"],
            "dev_metric": dev["metric"], "dev_p": dev["p"], "advanced": strategy in advanced,
            "holdout_n": held["n_meetings"] if held else "", "holdout_metric": held["metric"] if held else "",
            "holdout_p": held["p"] if held else "", "holm_p": adjusted.get(strategy, ""),
            "fresh_n": new["n_meetings"] if new else "", "fresh_metric": new["metric"] if new else "",
            "status": status}
        for prefix, stats in (("dev", dev), ("holdout", held)):
            for key in ("net_mean", "benchmark_mean", "volatility", "benchmark_volatility", "sharpe", "benchmark_sharpe",
                        "realized_second_moment", "benchmark_second_moment", "n_trades", "n_markets"):
                row[prefix + "_" + key] = stats[key] if stats else ""
        summary.append(row)
    write_csv(FOLDER / "results.csv", summary)
    if records:
        write_csv(FOLDER / "holdout_observations.csv", records)
    write_csv(FOLDER / "holdout_execution.csv", audit)
    (work / "holdout_results.json").write_text(json.dumps({"summary": summary, "fresh_status": fresh_status,
        "development_shuffle_fraction": manifest["dev_shuffle_fraction_p_below_0_10"]}, indent=2) + "\n")
    provenance = {"prereg_commit": PREREG_COMMIT, "registration_sha256": digest(FOLDER / "registration.json"),
        "code_sha256": digest(__file__), "development_manifest_sha256": digest(manifest_path),
        "holdout_lock_sha256": digest(work / "holdout_lock.json"), "advanced_ids": ",".join(advanced),
        "frozen_platt": json.dumps(manifest["frozen"]["theta"]), "frozen_beta": manifest["frozen"]["beta"],
        "fresh_status": fresh_status}
    write_csv(FOLDER / "study_manifest.csv", [{"key": k, "value": v} for k, v in provenance.items()])
    write_report(summary, manifest, fresh_status)
    print("Holdout evaluated once; lock retained. " + "; ".join(f"{r['strategy']}: {r['status']}" for r in summary))


def write_report(summary, manifest, fresh_status):
    passes = [r for r in summary if r["status"] in (
        "fresh-corroborated exploratory pass", "exploratory, not independently confirmed")]
    verdict = "No preregistered strategy established a holdout edge." if not passes else (
        "Exploratory holdout passes found; see fresh-meeting qualification below, not independent broad confirmation.")
    lines = ["# Strategy-search results", "", "**Verdict: " + verdict + "**", "",
        "**HOLDOUT DISCLOSURE: the five historical holdout meetings were used in earlier analyses of wallet-tilt "
        "strategies only. Strategies a–f were never evaluated on them, so the holdout is untouched for those strategies. "
        "g is descriptive only and excluded from the Holm family.**", "",
        "The preregistration was committed before any new strategy performance computation. No parameters were "
        "tuned and no candidates were added after screening or holdout. All primary metrics are higher-is-better. "
        "PM metrics are after-cost ROI per equal-dollar market sleeve, averaged within meeting then across meetings. "
        "f is a window-Sharpe difference; g is mean after-cost excess return. Their numerical units differ.", "",
        "Development ranks are within each primary-metric family, not across incomparable units.", "",
        "| Strategy | Dev rank | Dev n | Dev metric | Dev one-sided p | Holdout n | Holdout metric | Holdout p | Holm p | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    def fmt(value):
        return "—" if value is None or value == "" else f"{value:.6f}" if isinstance(value, float) else str(value)
    for r in summary:
        lines.append("| " + " | ".join(fmt(r[k]) for k in ("strategy", "dev_rank", "dev_n", "dev_metric", "dev_p", "holdout_n",
            "holdout_metric", "holdout_p", "holm_p", "status")) + " |")
    lines += ["", "## Split, fresh data and controls", "",
        "Development: " + ", ".join(json.loads((FOLDER / "registration.json").read_text())["development"]) + ". "
        "Historical holdout: 2026-03, 2026-04, 2026-06, 2026-07, 2026-09. Fresh PM holdout: October 28, 2026, "
        "event 606422 / markets 2589810–2589814. " + fresh_status + ".", "",
        "Advanced IDs: " + (", ".join(manifest["advanced"]) or "none") + ". "
        "Non-advanced holdout performance is deliberately not calculated. g is evaluated once descriptively "
        "regardless of screening and never enters Holm. h is a negative control; a pass would be a warning, not an edge.", "",
        "Development-only shuffled-signal screening frequency (100 fixed shuffles, not selectable candidates): "
        f"{manifest['dev_shuffle_fraction_p_below_0_10']:.1%}. This is conditional on one tiny development sample, "
        "not a general false-positive-rate estimate.", "",
        "| Advanced strategy | Fresh PM meetings | Fresh primary metric (after costs) |", "|---|---:|---:|"]
    for r in summary:
        if r["advanced"]:
            lines.append(f"| {r['strategy']} | {r['fresh_n']} | {fmt(r['fresh_metric'])} |")
    lines += ["", "A pass without positive fresh-meeting performance is **exploratory, not independently confirmed**. "
        "Even a fresh-positive single meeting supplies corroboration, not independent statistical confirmation. "
        "The SPY CSV ends October 7, so f/g have no fresh October execution window.", "",
        "## SPY volatility-timing / descriptive control", "",
        "Net event-window returns include 10 bp per side times exposure for strategy and comparator. "
        "Volatility is sample std and Sharpe is not annualized. Realized second moments are in the CSV. "
        "A mechanical reduction in volatility alone is not evidence of profitable timing.", "",
        "| Strategy / sample | Net mean | Comparator mean | Vol | Comparator vol | Sharpe | Comparator Sharpe |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for r in summary:
        if r["strategy"] in ("f_uncertainty_spy", "g_wallet_control"):
            for sample in ("dev", "holdout"):
                lines.append(f"| {r['strategy']} / {sample} | " + " | ".join(fmt(r[sample + "_" + k]) for k in
                    ("net_mean", "benchmark_mean", "volatility", "benchmark_volatility", "sharpe", "benchmark_sharpe")) + " |")
    lines += ["", "## Execution coverage", "",
        "| Sample | Markets | Both PM token entries available | Missing token entries |",
        "|---|---:|---:|---:|"]
    for phase in ("development", "holdout"):
        rows = read_csv(FOLDER / f"{phase}_execution.csv")
        available = sum(r["pm_eligible"] == "True" for r in rows)
        lines.append(f"| {phase} | {len(rows)} | {available} | {len(rows) - available} |")
    lines += ["", "## Execution, lock and limitations", "",
        "PM entries use the first chosen-token participant price strictly after cutoff, before decision-day midnight, "
        "plus $0.02/share. Both token entries must exist for common execution eligibility. SPY enters at the first "
        "close strictly after cutoff, not the prior close. Execution CSVs record timestamps and missingness. "
        "Calibration and β are frozen from development for holdout; online wallet skill and scenario history use "
        "only prior-resolved/observable meetings. Parameters and exact permutation/Holm rules are in PREREGISTRATION.md.", "",
        "The exclusive external holdout lock was claimed before loading holdout evaluation data and remains in place. "
        "Code/data/preregistration hashes must match the frozen development manifest. Unknown or non-advanced "
        "strategies cannot be evaluated by the holdout runner. Reports can be inspected without rerunning evaluation.", "",
        "Nine development and only five old/six potential PM holdout clusters give low power and coarse exact p-values. "
        "Sign-flip symmetry / paired-swap exchangeability may fail for skewed returns, and meetings may be dependent. "
        "API retention leaves incomplete early skill history. Maker/taker participant records are not independent "
        "fills, inventory or people; deduplication is imperfect. First trade prints plus assumed costs do not prove "
        "fillable liquidity, spread, depth or impact. Momentum prices may be stale. Multiple strategies and earlier "
        "wallet-tilt exposure limit confirmatory interpretation. The 100 dev shuffles are diagnostics only.", "",
        "## Reproduce (single-use holdout)", "", "```sh",
        "~/data/polymarket/wallet_backtest_env/bin/python models/strategy_search/search.py develop",
        "~/data/polymarket/wallet_backtest_env/bin/python models/strategy_search/search.py holdout",
        "~/data/polymarket/wallet_backtest_env/bin/python -m unittest discover -s models/strategy_search -p 'test_*.py' -v",
        "```", "", "Default external work: `~/data/polymarket/strategy_search/`. `--data-root` is configurable. "
        "A second holdout invocation refuses to run; do not remove the lock to obtain another draw. "
        "Only small derived CSVs and source/docs are committed; raw data and frozen JSON manifests remain external.", ""]
    (FOLDER / "RESULTS.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("develop", "holdout"))
    parser.add_argument("--data-root", type=Path, default=Path.home() / "data/polymarket")
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    if data_root.is_relative_to(ROOT):
        parser.error("Raw data and working state must remain outside the repository")
    spec = registration()
    work = data_root / "strategy_search"
    work.mkdir(parents=True, exist_ok=True)
    (develop if args.phase == "develop" else holdout)(data_root, spec, work)


if __name__ == "__main__":
    main()
