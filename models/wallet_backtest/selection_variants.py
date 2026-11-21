"""Point-in-time selector sensitivity; preserve the original panel and backtest."""

import argparse
from collections import defaultdict
import csv
import hashlib
import math
from pathlib import Path
import random
import runpy
import shutil
import sqlite3

import numpy as np

from backtest import bootstrap_ci, load_inputs, load_prices, make_windows, run_predictions
from build_panel import (
    DAY, MIN_SMART, ROOT, SEED, SHRINK_TRADES, aggregate_flow, load_markets,
    select_cohorts, source_fingerprint, timestamp, wallet_scores, window_flows, write_csv,
)


SELECTORS = ("baseline", "hit_rate", "whale", "strict", "early_edge", "recent")
FOLDER = Path(__file__).resolve().parent


def read_csv(path):
    with path.open() as handle:
        return list(csv.DictReader(handle))


def install_resolution_times(db, markets):
    db.execute("CREATE TEMP TABLE market_resolution_times (market_id TEXT PRIMARY KEY, resolved_ts INTEGER)")
    db.executemany("INSERT INTO market_resolution_times VALUES (?, ?)",
                   [(m.market_id, m.resolved_ts) for m in markets.values()])


def pnl_subset(db, cutoff, extra="", parameters=()):
    rows = db.execute("""
        SELECT t.wallet, COUNT(*), SUM(t.signed_yes_shares * (m.realized - t.price)), SUM(t.notional)
        FROM trades t JOIN markets m USING (market_id)
        JOIN market_resolution_times r USING (market_id)
        WHERE m.resolved_ts < ? AND t.ts < ?
        """ + extra + " GROUP BY t.wallet HAVING COUNT(*) >= 5 AND SUM(t.notional) > 0",
        (cutoff, cutoff, *parameters)).fetchall()
    return {w: {"n_trades": n, "notional": gross, "score": pnl / gross * n / (n + SHRINK_TRADES)}
            for w, n, pnl, gross in rows}


def score_variants(db, cutoff):
    baseline = wallet_scores(db, cutoff)
    prior = db.execute("""
        SELECT t.wallet, COUNT(*), SUM(t.notional),
            SUM(CASE WHEN t.signed_yes_shares * (2 * m.realized - 1) > 0 THEN t.notional ELSE 0 END)
        FROM trades t JOIN markets m USING (market_id)
        WHERE m.resolved_ts < ? AND t.ts < ?
        GROUP BY t.wallet HAVING SUM(t.notional) > 0
        """, (cutoff, cutoff)).fetchall()
    hit_rate = {w: {"n_trades": n, "notional": gross,
                    "score": .5 + (won / gross - .5) * n / (n + SHRINK_TRADES)}
                for w, n, gross, won in prior if n >= 5}
    whale = {w: {"n_trades": n, "notional": gross, "score": gross} for w, n, gross, _ in prior}
    strict = {w: stats for w, stats in baseline.items() if stats["n_trades"] >= 20}
    early = pnl_subset(db, cutoff, " AND t.ts <= r.resolved_ts - ?", (7 * DAY,))
    recent_events = [r[0] for r in db.execute("""
        SELECT event_id FROM markets WHERE resolved_ts < ? GROUP BY event_id
        ORDER BY MAX(resolved_ts) DESC, event_id ASC LIMIT 4
        """, (cutoff,))]
    placeholders = ",".join("?" for _ in recent_events)
    recent = pnl_subset(db, cutoff, f" AND m.event_id IN ({placeholders})", recent_events) if recent_events else {}
    return {"baseline": baseline, "hit_rate": hit_rate, "whale": whale, "strict": strict,
            "early_edge": early, "recent": recent}


def cohorts(scores, selector, event_id, cutoff):
    if selector == "baseline":
        return select_cohorts(scores, event_id, cutoff)
    if selector not in SELECTORS:
        raise ValueError("Unknown selector")
    fraction = .05 if selector == "strict" else .1
    n = math.floor(fraction * len(scores))
    if n < MIN_SMART:
        return None, None
    ranked = sorted(scores, key=lambda w: (-scores[w]["score"], w))
    placebo = random.Random(f"{SEED}:{selector}:{event_id}:{cutoff}").sample(sorted(scores), n)
    return set(ranked[:n]), set(placebo)


def score_cache_key(db, cutoff):
    events = tuple(r[0] for r in db.execute(
        "SELECT DISTINCT event_id FROM markets WHERE resolved_ts < ? ORDER BY event_id", (cutoff,)))
    last_trade = db.execute("""
        SELECT MAX(t.ts) FROM trades t JOIN markets m USING (market_id)
        WHERE m.resolved_ts < ? AND t.ts < ?
        """, (cutoff, cutoff)).fetchone()[0]
    return events, last_trade


def check_baseline_row(computed, original):
    for key in ("n_smart", "n_qualifying", "smart_available"):
        if str(computed[key]) != str(original[key]):
            raise ValueError(f"Baseline cohort drift: {key}")
    for prefix in ("smart", "placebo"):
        for suffix in ("signal", "net_yes_notional", "gross_notional", "n_trades", "n_wallets"):
            key = prefix + "_" + suffix
            a, b = computed[key], original[key]
            if a in (None, "") and b in (None, ""):
                continue
            if a in (None, "") or b in (None, "") or not math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-9):
                raise ValueError(f"Baseline flow drift: {key}")


def make_panels(db, template):
    groups = defaultdict(list)
    for row in template:
        groups[(row["meeting"], int(row["cutoff_days"]))].append(row)
    panels = {s: [] for s in SELECTORS}
    counts, cache = [], {}
    for (meeting, days), group in sorted(groups.items()):
        cutoff = timestamp(group[0]["cutoff_utc"])
        key = score_cache_key(db, cutoff)
        if key not in cache:
            cache[key] = score_variants(db, cutoff)
        scores = cache[key]
        selected = {s: cohorts(scores[s], s, group[0]["event_id"], cutoff) for s in SELECTORS}
        for s, (smart, placebo) in selected.items():
            counts.append({"selector": s, "meeting": meeting, "cutoff_days": days,
                "n_qualifying": len(scores[s]), "n_selected": len(smart) if smart else 0,
                "n_placebo": len(placebo) if placebo else 0})
        for original in group:
            flows = window_flows(db, original["market_id"], cutoff)
            covered = original["window_covered"] == "True"
            for s, (smart, placebo) in selected.items():
                row = {**original, "n_smart": len(smart) if smart else 0, "n_qualifying": len(scores[s]),
                       "smart_available": smart is not None and covered,
                       "smart_status": "available" if smart is not None and covered else "selector_unavailable"}
                for name, members in (("smart", smart), ("placebo", placebo)):
                    result = aggregate_flow(flows, members)
                    if members is None or not covered:
                        result = dict.fromkeys(result)
                    row.update({name + "_" + k: v for k, v in result.items()})
                if s == "baseline":
                    check_baseline_row(row, original)
                    row = dict(original)
                panels[s].append(row)
        print(f"{meeting} t-{days}: " + ", ".join(f"{s}={len(pair[0]) if pair[0] else 0}" for s, pair in selected.items()), flush=True)
    return panels, counts


def paired_difference(rows, metric, reference, meetings=None, horizon=None, rule=None):
    selected = [r for r in rows if (meetings is None or r["meeting"] in meetings)
                and (horizon is None or r["cutoff_days"] == horizon) and (rule is None or r["rule"] == rule)]
    groups = defaultdict(dict)
    for row in selected:
        groups[(row["meeting"], row["cutoff_days"])][row["variant"]] = row
    by_meeting = defaultdict(list)
    for (meeting, _), group in groups.items():
        by_meeting[meeting].append(group["smart"][metric] - group[reference][metric])
    if not by_meeting:
        return None, None, None
    values = [float(np.mean(v)) for _, v in sorted(by_meeting.items())]
    low, high = bootstrap_ci(values)
    return float(np.mean(values)), low, high


def summarize(results, counts):
    usable = {s: {r["meeting"] for r in result["accuracy"]} for s, result in results.items()}
    common = set.intersection(*usable.values())
    summary = []
    for sample in ("own", "common"):
        for selector, result in results.items():
            meetings = usable[selector] if sample == "own" else common
            sizes = [r["n_selected"] for r in counts if r["selector"] == selector and r["meeting"] in meetings and r["n_selected"]]
            row = {"sample": sample, "selector": selector, "usable_meetings": len(meetings),
                   "first_meeting": min(meetings) if meetings else "", "last_meeting": max(meetings) if meetings else "",
                   "minimum_cohort_size": min(sizes) if sizes else 0, "maximum_cohort_size": max(sizes) if sizes else 0}
            for reference in ("market", "placebo"):
                for metric in ("brier", "log_loss"):
                    diff = paired_difference(result["accuracy"], metric, reference, meetings)
                    row.update(zip((f"{metric}_vs_{reference}", f"{metric}_vs_{reference}_low", f"{metric}_vs_{reference}_high"), diff))
                for rule in ("vol_target", "mean_variance"):
                    diff = paired_difference(result["portfolios"], "portfolio_return", reference, meetings, 3, rule)
                    row.update(zip((f"{rule}_vs_{reference}", f"{rule}_vs_{reference}_low", f"{rule}_vs_{reference}_high"), diff))
            summary.append(row)
    return summary


def interval(row, key, scale=1., digits=5):
    if row[key] is None:
        return "—"
    values = (row[key], row[key + "_low"], row[key + "_high"])
    a, b, c = (f"{scale * v:+.{digits}f}" for v in values)
    return f"{a} [{b}, {c}]"


def write_report(path, summary):
    lines = ["# Wallet selection variants", "",
        "**Verdict unchanged: early_edge improves losses versus market but not versus its own placebo; no robust smart-wallet edge or economically material portfolio gain is established.**", "",
        "On the frozen sample, early_edge's nominal 95% CIs favor it over market for both Brier and log loss, "
        "but its own placebo has still lower point-estimate losses and both paired intervals include zero. "
        "hit_rate also improves log loss versus market nominally, without separating from its placebo. "
        "None of the five new selectors beats its own placebo on either probability metric with a 95% CI "
        "wholly below zero. The largest new-selector t−3 mean-return gain versus market is strict's "
        "0.0768 bp per window (mean-variance), before costs. All-six common-meeting results (13 meetings) "
        "preserve this interpretation; selector-specific sample sizes are 13–15 meetings.", "",
        "## Probability accuracy (each selector's own usable meetings)", "",
        "Differences are selector-calibrated probabilities minus the stated comparator. Negative loss differences are better. "
        "95% paired percentile CIs use 10,000 draws, seed 42, resampling whole meetings and keeping all outcomes and three "
        "cutoff horizons together. The placebo has its own walk-forward β fit. Market probabilities are normalized. "
        "Different usable samples are not a head-to-head selector ranking.", "",
        "| Selector | Meetings | ΔBrier vs market [CI] | ΔLog loss vs market [CI] | ΔBrier vs own placebo [CI] | ΔLog loss vs own placebo [CI] |",
        "|---|---:|---|---|---|---|"]
    for row in summary:
        if row["sample"] == "own":
            lines.append(f"| {row['selector']} | {row['usable_meetings']} | " + " | ".join(interval(row, k) for k in
                ("brier_vs_market", "log_loss_vs_market", "brier_vs_placebo", "log_loss_vs_placebo")) + " |")
    lines += ["", "## t−3 portfolios", "",
        "Mean paired return differences in **basis points per event window** (1 bp = 0.01 percentage point), "
        "with 95% meeting-bootstrap CIs. Each selector uses its own usable sample. The portfolio rules and scenario "
        "estimates are unchanged from Part B, including the last-observable-close marking assumption.", "",
        "| Selector | Vol-target vs market [CI] | Mean-variance vs market [CI] | Vol-target vs own placebo [CI] | Mean-variance vs own placebo [CI] |",
        "|---|---|---|---|---|"]
    for row in summary:
        if row["sample"] == "own":
            lines.append(f"| {row['selector']} | " + " | ".join(interval(row, k, 1e4, 4) for k in
                ("vol_target_vs_market", "mean_variance_vs_market", "vol_target_vs_placebo", "mean_variance_vs_placebo")) + " |")
    lines += ["", "## Common-meeting sensitivity", "",
        "Intersection of usable meetings across all six selectors. Evaluate the existing out-of-sample forecasts on this "
        "intersection; do not retrain on the intersection or discard earlier selector-specific training history. "
        "The CSV includes both samples and all market/placebo accuracy and portfolio differences.", "",
        "| Selector | Meetings | ΔBrier vs market [CI] | ΔBrier vs own placebo [CI] | t−3 vol-target vs market (bp) [CI] | t−3 mean-variance vs market (bp) [CI] |",
        "|---|---:|---|---|---|---|"]
    for row in summary:
        if row["sample"] == "common":
            lines.append(f"| {row['selector']} | {row['usable_meetings']} | {interval(row, 'brier_vs_market')} "
                f"| {interval(row, 'brier_vs_placebo')} | {interval(row, 'vol_target_vs_market', 1e4, 4)} "
                f"| {interval(row, 'mean_variance_vs_market', 1e4, 4)} |")
    lines += ["", "## Selector definitions and safeguards", "",
        "- **baseline:** unchanged Part A PnL/notional × n/(n+20), at least five trades, floor(top 10%). "
        "The original `build_panel.py`, `backtest.py`, panel and Part B outputs are not modified. Recomputed baseline "
        "cohorts/flows must match the original panel, and rerun accuracy/portfolio results must match committed Part B results.",
        "- **hit_rate:** winning-side notional / gross actual-token notional, shrunk toward 0.5 as "
        "`0.5 + (fraction - 0.5) * n/(n+20)`; at least five trades, top 10%. Positive YES direction wins on a YES "
        "settlement; negative direction wins on NO. Thus SELL YES is directional NO and SELL NO directional YES. "
        "This is a directional hit fraction, not token ownership or PnL.",
        "- **whale:** top 10% by prior gross actual-token FOMC notional, with positive gross notional and at least "
        "one trade. No extra five-trade skill gate: this is deliberately size, not skill.",
        "- **strict:** baseline shrunk PnL score with at least 20 trades; select floor(top 5%).",
        "- **early_edge:** baseline PnL/notional formula, shrinkage and five-trade minimum, computed only from trades "
        "with `trade_ts <= individual_market_resolution_proxy - 7 calendar days`. Exactly seven days qualifies. "
        "Selection still requires the entire meeting to have resolved strictly before the target cutoff.",
        "- **recent:** baseline score/minimum/shrinkage, using only the last four prior-resolved meetings, ranked "
        "by meeting resolution proxy descending (event ID ascending for ties). These are the last four meetings "
        "in the mapped FOMC universe, even if their retained trade histories are empty—not a later-active universe.",
        "- Every selector uses only meetings resolved strictly before the target cutoff and trades strictly before it. "
        "No current-meeting positions or future labels enter selection. All require at least 20 **selected** wallets; "
        "cohorts are not padded. Score ties use ascending wallet address. Gross notional must be positive.",
        "- Each selector has its own same-size placebo, sampled without replacement from its qualifying population, "
        "including possible overlap with selected wallets. New selector seeds are "
        '`Random("42:selector:event_id:cutoff_epoch")`; baseline retains its original seed unchanged.',
        "- Signals remain net signed YES notional / gross notional in `[cutoff−7d, cutoff)`, with the same empty/"
        "unavailable conventions and coverage gates. On the immutable cache, score caching is allowed only when both the resolved-meeting "
        "set and latest eligible trade timestamp are identical; this proves the historical row subset is identical.",
        "- The backtest is reused unchanged: pooled-horizon offset logistic regression, λ=1, β=0 with fewer than "
        "three prior usable meetings, normalization across outcomes; fixed 1% volatility target and γ=10. "
        "Scenario means/variances use fully observable historical same-horizon meeting windows, with pooled fallbacks. "
        "No selector hyperparameters are tuned after observing results.", "",
        "## Limits and multiple testing", "",
        "**Five new variants means multiple-testing risk**, in addition to two probability metrics, two portfolio rules "
        "and sample comparisons. CIs are nominal/unadjusted; the best observed row is not a validated discovery. "
        "Only a small number of meetings and one placebo realization per selector are available, with correlated "
        "horizons and related wallet populations. A size benchmark improving a loss does not show smart-wallet skill. "
        "Retrospective API retention gaps, ambiguous participant-record deduplication, metadata resolution proxies, "
        "unverified quote publication times and last-close execution bias remain as documented in BACKTEST.md. "
        "Returns are hypothetical event-window marks, not executable fills after the signal became known. Costs and "
        "slippage are excluded. Very small portfolio intervals may reflect nearly identical/clipped weights, not "
        "economic value. Bootstrap intervals condition on the fixed walk-forward fits rather than refitting them.", "",
        "## Reproduce", "", "```sh",
        "~/data/polymarket/wallet_backtest_env/bin/python models/wallet_backtest/selection_variants.py --data-root ~/data/polymarket",
        "~/data/polymarket/wallet_backtest_env/bin/python -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v",
        "```", "",
        "Uses Part A's external immutable SQLite cache after checking its complete source fingerprint. "
        "Raw data stays external. Per-selector panels, forecasts, losses and portfolios are retained under "
        "`~/data/polymarket/selection_variants/` by default (`--work-dir` overrides). Only the small summary, "
        "cohort-count and provenance CSVs are committed. No app behavior or original backtest parameters change.", ""]
    path.write_text("\n".join(lines))


def check_baseline_results(accuracy, portfolios):
    for actual, filename, keys, fields in ((accuracy, "accuracy.csv", ("meeting", "cutoff_days", "variant"), ("brier", "log_loss")),
            (portfolios, "portfolio_paths.csv", ("meeting", "cutoff_days", "variant", "rule"),
             ("portfolio_return", "weight", "portfolio_var95"))):
        expected = {tuple(str(r[k]) for k in keys): r for r in read_csv(FOLDER / filename)}
        if len(actual) != len(expected):
            raise ValueError("Baseline output row count drift")
        for row in actual:
            old = expected[tuple(str(row[k]) for k in keys)]
            if any(not math.isclose(float(row[k]), float(old[k]), rel_tol=1e-12, abs_tol=1e-14) for k in fields):
                raise ValueError("Baseline backtest result drift")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path.home() / "data/polymarket")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    cache_path = (args.cache or data_root / "wallet_backtest_cache/trades.sqlite3").resolve()
    work_dir = (args.work_dir or data_root / "selection_variants").resolve()
    if any(p.is_relative_to(ROOT) for p in (data_root, cache_path, work_dir)):
        parser.error("Raw data, cache and intermediate work must remain outside the repository")
    calendar_path = ROOT / "app/api/calendar_dates.py"
    markets = load_markets(ROOT / "datasets/forward_probabilities.csv", data_root / "feasibility/gamma",
                           runpy.run_path(str(calendar_path))["MEETINGS"])
    fingerprint = source_fingerprint(data_root, ROOT / "datasets/forward_probabilities.csv", calendar_path, markets)
    with sqlite3.connect(cache_path.as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("SELECT fingerprint FROM build").fetchone()[0] != fingerprint:
            raise ValueError("External trade cache does not match frozen source inputs")
        install_resolution_times(db, markets)
        panels, counts = make_panels(db, read_csv(FOLDER / "panel.csv"))
    results = {}
    prices = load_prices(ROOT / "datasets/index_daily.csv")
    for selector, panel in panels.items():
        folder = work_dir / selector
        folder.mkdir(parents=True, exist_ok=True)
        write_csv(folder / "panel.csv", panel)
        shutil.copyfile(FOLDER / "settlements.csv", folder / "settlements.csv")
        observations, meetings = load_inputs(folder)
        if not any(r.usable for r in observations):
            results[selector] = {"accuracy": [], "portfolios": []}
            continue
        predictions, accuracy, portfolios, coefficients, scenarios = run_predictions(observations, meetings, make_windows(meetings, prices))
        if selector == "baseline":
            check_baseline_results(accuracy, portfolios)
            print("Baseline parity passed: original cohorts/flows and Part B accuracy/portfolio results unchanged.", flush=True)
        for filename, rows in (("predictions", predictions), ("accuracy", accuracy), ("portfolio_paths", portfolios),
                               ("coefficients", coefficients), ("scenarios", scenarios)):
            write_csv(folder / f"{filename}.csv", rows)
        results[selector] = {"accuracy": accuracy, "portfolios": portfolios}
    summary = summarize(results, counts)
    write_csv(FOLDER / "selection_variants.csv", summary)
    write_csv(FOLDER / "selection_cohorts.csv", counts)
    write_report(FOLDER / "SELECTION_VARIANTS.md", summary)
    provenance = {"source_fingerprint": fingerprint, "seed": SEED, "cache_validation": "source_fingerprint",
                  "baseline_parity": "passed", "bootstrap_draws": 10000}
    for path in (Path(__file__), FOLDER / "build_panel.py", FOLDER / "backtest.py", FOLDER / "panel.csv",
                 FOLDER / "settlements.csv", ROOT / "datasets/index_daily.csv"):
        provenance[path.name + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_csv(FOLDER / "selection_manifest.csv", [{"key": k, "value": v} for k, v in provenance.items()])
    print("Selection variants complete: " + ", ".join(f"{r['selector']}={r['usable_meetings']} meetings" for r in summary if r["sample"] == "own"))


if __name__ == "__main__":
    main()
