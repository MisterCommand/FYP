"""Walk-forward probability calibration and disjoint SPY event-window portfolios."""

import argparse
from bisect import bisect_right
from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime, time, timezone
import hashlib
import math
from pathlib import Path
import platform
import re
from zoneinfo import ZoneInfo

import numpy as np

from build_panel import CUTOFF_DAYS, ROOT, iso, timestamp, write_csv


L2 = 1.0
MIN_TRAIN_MEETINGS = 3
HEURISTIC_K = 0.5
SIGMA_TARGET = 0.01
GAMMA = 10.0
EPSILON = 1e-6
SEED = 42
BOOTSTRAPS = 10000
VAR_Z = 1.6448536269514722
VARIANTS = ("market", "smart", "placebo", "all", "heuristic")
SIGNALS = ("smart", "placebo", "all")
RULES = ("vol_target", "mean_variance")


@dataclass(frozen=True)
class Observation:
    meeting: str
    days: int
    cutoff: int
    resolved: int
    outcome: str
    market_id: str
    p_market: float
    realized: int
    signals: dict
    usable: bool = True


@dataclass(frozen=True)
class Window:
    meeting: str
    days: int
    decision: int
    entry: int
    exit: int
    realized_outcome: str
    value: float


def normalize(values):
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or values.sum() <= 0:
        raise ValueError("Invalid probability vector")
    return values / values.sum()


def adjusted_probabilities(market, signal, beta):
    if not math.isfinite(beta):
        raise ValueError("Nonfinite coefficient")
    if beta == 0:
        return normalize(market)
    p = np.clip(np.asarray(market, dtype=float), EPSILON, 1 - EPSILON)
    x = np.asarray(signal, dtype=float)
    if x.shape != p.shape or not np.isfinite(x).all() or (np.abs(x) > 1).any():
        raise ValueError("Invalid signal vector")
    logits = np.log(p) - np.log1p(-p) + beta * x
    return normalize(np.exp(-np.logaddexp(0, -logits)))


def fit_offset(rows, signal, penalty=L2):
    if penalty <= 0 or not rows:
        raise ValueError("Positive L2 penalty and nonempty training rows required")
    p = np.clip([r.p_market for r in rows], EPSILON, 1 - EPSILON)
    offset = np.log(p) - np.log1p(-p)
    x = np.array([r.signals[signal] for r in rows])
    y = np.array([r.realized for r in rows])
    if not np.isfinite(x).all() or (np.abs(x) > 1).any():
        raise ValueError("Invalid training signal")

    def objective(beta):
        z = offset + beta * x
        return float(np.sum(np.logaddexp(0, z) - y * z) + penalty * beta * beta / 2)

    beta = 0.
    for _ in range(100):
        z = offset + beta * x
        pred = np.exp(-np.logaddexp(0, -z))
        gradient = float(np.sum((pred - y) * x) + penalty * beta)
        hessian = float(np.sum(pred * (1 - pred) * x * x) + penalty)
        step = gradient / hessian
        if abs(gradient) < 1e-10:
            return beta
        while objective(beta - step) > objective(beta) and abs(step) > 1e-12:
            step /= 2
        beta -= step
        if abs(step) < 1e-10:
            return beta
    raise RuntimeError("Offset logistic regression failed to converge")


def fit_at(rows, meeting, cutoff, signal):
    eligible = [r for r in rows if r.usable and r.meeting < meeting and
                r.resolved < cutoff and r.cutoff < cutoff]
    n_meetings = len({r.meeting for r in eligible})
    beta = fit_offset(eligible, signal) if n_meetings >= MIN_TRAIN_MEETINGS else 0.
    return beta, n_meetings, len(eligible)


def load_inputs(folder):
    with (folder / "settlements.csv").open() as handle:
        settlements = list(csv.DictReader(handle))
    meetings = {}
    for row in settlements:
        item = meetings.setdefault(row["meeting"], {
            "decision": timestamp(row["decision_utc"]),
            "resolved": timestamp(row["meeting_resolution_proxy_utc"]), "winner": None})
        if row["realized"] == "1":
            item["winner"] = row["outcome"]
    groups = defaultdict(list)
    with (folder / "panel.csv").open() as handle:
        for row in csv.DictReader(handle):
            usable = row["smart_available"] == "True" and bool(row["p_market"])
            signals = {s: float(row[s + "_signal"]) if row[s + "_signal"] else 0. for s in SIGNALS}
            usable = usable and all(row[s + "_signal"] != "" for s in SIGNALS)
            observation = Observation(row["meeting"], int(row["cutoff_days"]), timestamp(row["cutoff_utc"]),
                meetings[row["meeting"]]["resolved"], row["outcome"], row["market_id"],
                float(row["p_market"]) if row["p_market"] else 0., int(row["realized"]), signals, usable)
            groups[(observation.meeting, observation.days)].append(observation)
    rows = []
    for group in groups.values():
        usable = all(r.usable for r in group)
        if sum(r.realized for r in group) != 1:
            raise ValueError("Each meeting needs exactly one winning outcome")
        for r in group:
            rows.append(Observation(**{**r.__dict__, "usable": usable}))
    return sorted(rows, key=lambda r: (r.meeting, -r.days, r.market_id)), meetings


def load_prices(path):
    prices = []
    with path.open() as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] != "SPY":
                continue
            date = datetime.fromisoformat(row["date"]).date()
            close_time = datetime.combine(date, time(16), ZoneInfo("America/New_York"))
            close = float(row["close"])
            if not math.isfinite(close) or close <= 0:
                raise ValueError("Invalid SPY close")
            prices.append((int(close_time.timestamp()), close))
    prices.sort()
    if not prices or len({t for t, _ in prices}) != len(prices):
        raise ValueError("Empty or duplicated SPY prices")
    return prices


def make_windows(meetings, prices):
    times = [t for t, _ in prices]
    windows = {}
    for meeting, metadata in sorted(meetings.items()):
        decision = metadata["decision"]
        decision_date = datetime.fromtimestamp(decision, timezone.utc).date()
        exits = [(t, p) for t, p in prices if datetime.fromtimestamp(t, timezone.utc).date() > decision_date]
        if not exits or not metadata["winner"]:
            raise ValueError("Missing realized outcome or post-decision price")
        exit_ts, exit_price = exits[0]
        for days in CUTOFF_DAYS:
            cutoff = decision - days * 86400
            index = bisect_right(times, cutoff) - 1
            if index < 0:
                raise ValueError("Missing pre-cutoff SPY close")
            entry_ts, entry_price = prices[index]
            windows[(meeting, days)] = Window(meeting, days, decision, entry_ts, exit_ts,
                                               metadata["winner"], exit_price / entry_price - 1)
    return windows


def outcome_interval(label):
    if label.casefold() == "no change":
        return 0, 0
    match = re.fullmatch(r"(\d+)(\+)? bps (increase|decrease)", label.casefold())
    if not match:
        return None
    amount, plus, direction = match.groups()
    low, high = int(amount), math.inf if plus else int(amount)
    return (low, high) if direction == "increase" else (-high, -low)


def outcome_matches(target, observed):
    target, observed = outcome_interval(target), outcome_interval(observed)
    return target is not None and observed is not None and target[0] <= observed[0] and observed[1] <= target[1]


def scenario_estimates(windows, meetings, current, cutoff, outcomes):
    prior = [w for w in windows.values() if w.days == current.days and w.decision < current.decision
             and w.meeting != current.meeting and w.exit < cutoff and meetings[w.meeting]["resolved"] < cutoff]
    if len(prior) < 2:
        raise ValueError("At least two fully observable prior meeting windows required")
    pooled = np.array([w.value for w in prior])
    result = []
    for outcome in outcomes:
        conditional = np.array([w.value for w in prior if outcome_matches(outcome, w.realized_outcome)])
        values = conditional if len(conditional) >= 3 else pooled
        result.append({"outcome": outcome, "mean": float(values.mean()), "variance": float(values.var(ddof=1)),
                       "n_conditional": len(conditional), "n_pooled": len(pooled), "pooled_fallback": len(conditional) < 3})
    return result


def mixture(probabilities, scenarios):
    p = normalize(probabilities)
    mu = np.array([s["mean"] for s in scenarios])
    variance = np.array([s["variance"] for s in scenarios])
    mean = float(p @ mu)
    var = max(0., float(p @ (variance + mu * mu) - mean * mean))
    sigma = math.sqrt(var)
    return mean, sigma, max(0., VAR_Z * sigma - mean)


def weight(rule, mean, sigma):
    if rule == "vol_target":
        return min(1., SIGMA_TARGET / sigma) if sigma > 0 else 1.
    if rule == "mean_variance":
        if sigma == 0:
            return float(mean > 0)
        return float(np.clip(mean / (GAMMA * sigma * sigma), 0, 1))
    raise ValueError("Unknown portfolio rule")


def kupiec(n, breaches, alpha=.05):
    if n <= 0 or not 0 <= breaches <= n:
        raise ValueError("Invalid breach count")
    observed = breaches / n
    null_log = breaches * math.log(alpha) + (n - breaches) * math.log1p(-alpha)
    fitted_log = (breaches * math.log(observed) if breaches else 0.)
    fitted_log += (n - breaches) * math.log1p(-observed) if breaches < n else 0.
    statistic = max(0., 2 * (fitted_log - null_log))
    return math.erfc(math.sqrt(statistic / 2))


def bootstrap_ci(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Nonempty finite meeting-level values required")
    indices = np.random.default_rng(SEED).integers(0, len(values), size=(BOOTSTRAPS, len(values)))
    low, high = np.quantile(values[indices].mean(axis=1), [.025, .975])
    return float(low), float(high)


def return_metrics(returns):
    values = np.asarray(returns, dtype=float)
    equity = np.concatenate(([1.], np.cumprod(1 + values)))
    volatility = float(values.std(ddof=1)) if len(values) > 1 else 0.
    mean = float(values.mean())
    return {"mean_return": mean, "volatility": volatility,
            "sharpe": mean / volatility if volatility else 0.,
            "max_drawdown": float(np.min(equity / np.maximum.accumulate(equity) - 1)),
            "total_return": float(equity[-1] - 1)}


def run_predictions(rows, meetings, windows):
    groups = defaultdict(list)
    for row in rows:
        if row.usable:
            groups[(row.meeting, row.days)].append(row)
    predictions, accuracy, portfolios, coefficients, scenario_rows = [], [], [], [], []
    for (meeting, days), group in sorted(groups.items()):
        cutoff = group[0].cutoff
        coefficients_here = {s: fit_at(rows, meeting, cutoff, s) for s in SIGNALS}
        coefficients.append({"meeting": meeting, "cutoff_days": days, "cutoff_utc": iso(cutoff),
            "n_prior_usable_meetings": coefficients_here["smart"][1],
            "n_training_rows": coefficients_here["smart"][2],
            **{s + "_beta": coefficients_here[s][0] for s in SIGNALS}})
        current = windows[(meeting, days)]
        scenarios = scenario_estimates(windows, meetings, current, cutoff, [r.outcome for r in group])
        scenario_rows.extend({"meeting": meeting, "cutoff_days": days, **s} for s in scenarios)
        observed = np.array([r.realized for r in group])
        p_market = [r.p_market for r in group]
        for variant in VARIANTS:
            signal = "smart" if variant in ("market", "heuristic") else variant
            beta = 0. if variant == "market" else HEURISTIC_K if variant == "heuristic" else coefficients_here[variant][0]
            p = adjusted_probabilities(p_market, [r.signals[signal] for r in group], beta)
            for r, value in zip(group, p):
                predictions.append({"meeting": meeting, "cutoff_days": days, "market_id": r.market_id,
                    "outcome": r.outcome, "variant": variant, "probability": float(value),
                    "realized": r.realized, "beta": beta})
            accuracy.append({"meeting": meeting, "cutoff_days": days, "variant": variant,
                "brier": float(np.sum((p - observed)**2)),
                "log_loss": -math.log(max(float(p @ observed), 1e-15))})
            mean, sigma, var95 = mixture(p, scenarios)
            for rule in RULES:
                w = weight(rule, mean, sigma)
                portfolios.append({"meeting": meeting, "cutoff_days": days, "rule": rule, "variant": variant,
                    "entry_utc": iso(current.entry), "exit_utc": iso(current.exit),
                    "predicted_mu": mean, "predicted_sigma": sigma, "spy_var95": var95,
                    "weight": w, "spy_return": current.value, "portfolio_return": w * current.value,
                    "portfolio_var95": w * var95, "var_breach": int(w * current.value < -w * var95)})
                if variant == "market":
                    portfolios.append({**portfolios[-1], "variant": "buy_hold_windows", "weight": 1.,
                        "portfolio_return": current.value, "portfolio_var95": var95,
                        "var_breach": int(current.value < -var95)})
    baseline = {(r["meeting"], r["cutoff_days"]): r for r in accuracy if r["variant"] == "market"}
    for row in accuracy:
        base = baseline[(row["meeting"], row["cutoff_days"]) ]
        row.update({"delta_brier": row["brier"] - base["brier"], "delta_log_loss": row["log_loss"] - base["log_loss"]})
    return predictions, accuracy, portfolios, coefficients, scenario_rows


def accuracy_summary(accuracy):
    summary = []
    for horizon in ("pooled", *CUTOFF_DAYS):
        for variant in VARIANTS:
            selected = [r for r in accuracy if r["variant"] == variant and (horizon == "pooled" or r["cutoff_days"] == horizon)]
            row = {"cutoff_days": horizon, "variant": variant, "n_meetings": len({r["meeting"] for r in selected})}
            for metric in ("brier", "log_loss"):
                by_meeting = defaultdict(list)
                for r in selected:
                    by_meeting[r["meeting"]].append(r["delta_" + metric])
                diffs = [float(np.mean(v)) for _, v in sorted(by_meeting.items())]
                low, high = bootstrap_ci(diffs)
                row.update({metric: float(np.mean([r[metric] for r in selected])),
                    "delta_" + metric: float(np.mean(diffs)), metric + "_ci_low": low, metric + "_ci_high": high,
                    metric + "_better": sum(v < -1e-12 for v in diffs),
                    metric + "_worse": sum(v > 1e-12 for v in diffs),
                    metric + "_ties": sum(abs(v) <= 1e-12 for v in diffs)})
            summary.append(row)
    return summary


def portfolio_summary(portfolios):
    summary = []
    for days in CUTOFF_DAYS:
        for rule in RULES:
            baseline = {r["meeting"]: r["portfolio_return"] for r in portfolios
                        if r["cutoff_days"] == days and r["rule"] == rule and r["variant"] == "market"}
            for variant in (*VARIANTS, "buy_hold_windows"):
                selected = sorted((r for r in portfolios if r["cutoff_days"] == days and r["rule"] == rule
                                   and r["variant"] == variant), key=lambda r:r["meeting"])
                diffs = [r["portfolio_return"] - baseline[r["meeting"]] for r in selected]
                low, high = bootstrap_ci(diffs)
                breaches = sum(r["var_breach"] for r in selected)
                summary.append({"cutoff_days": days, "rule": rule, "variant": variant,
                    "n_meetings": len(selected), **return_metrics([r["portfolio_return"] for r in selected]),
                    "mean_weight": float(np.mean([r["weight"] for r in selected])),
                    "var_breaches": breaches, "var_breach_rate": breaches / len(selected),
                    "kupiec_p": kupiec(len(selected), breaches),
                    "delta_mean_return": float(np.mean(diffs)), "return_ci_low": low, "return_ci_high": high})
    return summary


def continuous_buy_hold(portfolios, prices):
    result = []
    for days in CUTOFF_DAYS:
        selected = [r for r in portfolios if r["cutoff_days"] == days]
        start, end = min(timestamp(r["entry_utc"]) for r in selected), max(timestamp(r["exit_utc"]) for r in selected)
        history = [(t, p) for t, p in prices if start <= t <= end]
        returns = np.array([b[1] / a[1] - 1 for a, b in zip(history, history[1:])])
        metrics = return_metrics(returns)
        result.append({"cutoff_days": days, "start": iso(start), "end": iso(end),
            "trading_days": len(returns), "total_return": metrics["total_return"],
            "annualized_mean": metrics["mean_return"] * 252,
            "annualized_volatility": metrics["volatility"] * math.sqrt(252),
            "annualized_sharpe": metrics["sharpe"] * math.sqrt(252), "max_drawdown": metrics["max_drawdown"]})
    return result


def charts(folder, accuracy, portfolios, prices):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(16, 8), sharey=True)
    for i, rule in enumerate(RULES):
        for j, days in enumerate(CUTOFF_DAYS):
            ax = axes[i, j]
            relevant = [r for r in portfolios if r["cutoff_days"] == days and r["rule"] == rule]
            start = min(timestamp(r["entry_utc"]) for r in relevant)
            for variant in (*VARIANTS, "buy_hold_windows"):
                selected = sorted((r for r in relevant if r["variant"] == variant), key=lambda r:r["meeting"])
                dates = [datetime.fromtimestamp(start, timezone.utc)] + [datetime.fromisoformat(r["exit_utc"]) for r in selected]
                equity = np.concatenate(([1.], np.cumprod([1 + r["portfolio_return"] for r in selected])))
                ax.plot(dates, (equity - 1) * 100, label=variant, linestyle="--" if variant == "buy_hold_windows" else "-")
            end = max(timestamp(r["exit_utc"]) for r in relevant)
            history = [(t, p) for t, p in prices if start <= t <= end]
            ax.plot([datetime.fromtimestamp(t, timezone.utc) for t, _ in history],
                    [(p / history[0][1] - 1) * 100 for _, p in history], label="SPY continuous", color="black", linestyle=":", alpha=.6)
            ax.set_title(f"t−{days}: {rule}")
            ax.set_ylabel("Cumulative return (%)")
            ax.tick_params(axis="x", rotation=25)
            ax.grid(alpha=.25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=7, fontsize=9)
    fig.suptitle("SPY event-window strategies (cash between windows); separate horizons, not pooled")
    fig.tight_layout(rect=(0, .055, 1, .96))
    fig.savefig(folder / "cumulative_returns.png", dpi=140)
    plt.close(fig)

    meetings = sorted({r["meeting"] for r in accuracy})
    variants = VARIANTS[1:]
    matrix = np.array([[np.mean([r["delta_brier"] for r in accuracy if r["meeting"] == m and r["variant"] == v])
                        for m in meetings] for v in variants])
    fig, ax = plt.subplots(figsize=(13, 4))
    bound = max(float(np.abs(matrix).max()), 1e-6)
    surface = ax.imshow(matrix, cmap="RdBu_r", vmin=-bound, vmax=bound, aspect="auto")
    for i in range(len(variants)):
        for j in range(len(meetings)):
            ax.text(j, i, f"{matrix[i,j]:+.3f}", ha="center", va="center", fontsize=8,
                    color="white" if abs(matrix[i, j]) > bound / 2 else "black")
    ax.set_xticks(range(len(meetings)), meetings, rotation=45, ha="right")
    ax.set_yticks(range(len(variants)), variants)
    ax.set_title("Brier difference vs normalized market, mean over cutoffs (negative is better)")
    fig.colorbar(surface, ax=ax, label="Δ Brier")
    fig.tight_layout()
    fig.savefig(folder / "brier_differences.png", dpi=140)
    plt.close(fig)


def pct(value):
    return f"{100 * value:.3f}%"


def report(folder, accuracy, portfolio, continuous, coefficients, scenario_rows):
    pooled = [r for r in accuracy if r["cutoff_days"] == "pooled"]
    n = pooled[0]["n_meetings"]
    smart = next(r for r in pooled if r["variant"] == "smart")
    interval_crosses_zero = smart["brier_ci_low"] <= 0 <= smart["brier_ci_high"]
    verdict = ("The smart-signal calibration does not demonstrate a reliable probability improvement" if interval_crosses_zero else
               "The smart-signal calibration changes Brier loss with a bootstrap interval excluding zero")
    maximum_smart_return_delta = max(abs(r["delta_mean_return"]) for r in portfolio if r["variant"] == "smart")
    lines = ["# Wallet probability and SPY portfolio backtest", "",
        f"**Verdict.** {verdict}: pooled ΔBrier {smart['delta_brier']:+.5f} "
        f"(95% meeting-bootstrap CI [{smart['brier_ci_low']:+.5f}, {smart['brier_ci_high']:+.5f}]). "
        f"Smart log loss is worse by {smart['delta_log_loss']:+.5f}; placebo/all-wallet point estimates do better, "
        "not evidence of a skill-selection advantage. The largest absolute smart-versus-market mean portfolio "
        f"return difference is only **{maximum_smart_return_delta * 1e4:.4f} basis points per window** across the six rule/horizon settings. "
        f"Only **{n} usable meetings** ({len(coefficients)} correlated meeting-cutoffs) are available; the first three usable "
        "meetings use market-only learned variants. Portfolio results below are exploratory, not evidence of a "
        "deployable SPY edge: inspect paired return intervals and placebo/all-wallet controls rather than "
        "ranking point estimates. Last-close marking is not a tradable execution assumption. Low power, repeated "
        "horizons and multiple comparisons preclude a strong claim.", "",
        "## Probability accuracy", "",
        "Multi-outcome Brier is the sum over outcomes (not divided by outcome count). Log loss is −log(probability "
        "of the winning outcome). All variants use the identical complete-case smart-available panel: "
        f"{n} meetings × three cutoffs, September 2024–September 2026. Lower losses and negative differences are better. "
        "Pooled CIs resample meetings, retaining all outcomes/cutoffs; signs compare each meeting's mean loss difference.", "",
        "| Variant | Brier | ΔBrier [95% CI] | Better/worse/tied | Log loss | ΔLog loss [95% CI] | Better/worse/tied |",
        "|---|---:|---|---|---:|---|---|"]
    for r in pooled:
        lines.append(f"| {r['variant']} | {r['brier']:.5f} | {r['delta_brier']:+.5f} "
            f"[{r['brier_ci_low']:+.5f}, {r['brier_ci_high']:+.5f}] | {r['brier_better']}/{r['brier_worse']}/{r['brier_ties']} "
            f"| {r['log_loss']:.5f} | {r['delta_log_loss']:+.5f} [{r['log_loss_ci_low']:+.5f}, {r['log_loss_ci_high']:+.5f}] "
            f"| {r['log_loss_better']}/{r['log_loss_worse']}/{r['log_loss_ties']} |")
    lines += ["", "### Per-cutoff accuracy", "", "| Cutoff | Variant | Brier | ΔBrier [95% CI] | Log loss | ΔLog loss [95% CI] |",
              "|---|---|---:|---|---:|---|"]
    for r in accuracy:
        if r["cutoff_days"] != "pooled":
            lines.append(f"| t−{r['cutoff_days']} | {r['variant']} | {r['brier']:.5f} | {r['delta_brier']:+.5f} "
                f"[{r['brier_ci_low']:+.5f}, {r['brier_ci_high']:+.5f}] | {r['log_loss']:.5f} | {r['delta_log_loss']:+.5f} "
                f"[{r['log_loss_ci_low']:+.5f}, {r['log_loss_ci_high']:+.5f}] |")
    lines += ["", "![Brier differences](brier_differences.png)", "", "## SPY event-window portfolios", "",
        "Each horizon is a separate chronological, non-overlapping 14-window strategy. No horizon pooling into one equity curve. "
        "Cash earns zero outside windows and on uninvested capital. Mean, sample volatility and Sharpe are **per event window, "
        "not annualized**; Sharpe uses zero risk-free rate. Drawdown includes initial wealth and compounds window returns. "
        "Δmean and its paired 95% meeting-bootstrap CI are in **basis points of return** versus the same-rule market "
        "(1 bp = 0.01 percentage point). Most adjusted weights nearly coincide with market weights; very small intervals "
        "can reflect sparse, tiny nonzero differences rather than persuasive economic value. "
        "VaR is a positive loss threshold; breaches count realized loss strictly exceeding predicted portfolio VaR. "
        "Kupiec is the asymptotic χ²(1) unconditional-coverage test at 5%, unreliable with just 14 windows. "
        "Zero-exposure windows remain in its denominator but cannot breach, so nominal 5% coverage is not exact "
        "for those degenerate cash forecasts. "
        "`buy_hold_windows` means 100% SPY only during the identical windows, not continuous buy-and-hold; its VaR uses the "
        "market scenario mixture at full exposure. Continuous buy-and-hold is reported separately.", "",
        "| Cutoff | Rule | Variant | Mean | Vol | Sharpe | Max DD | Total | Mean w | VaR breaches | Kupiec p | Δmean bp [95% CI] |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|"]
    for r in portfolio:
        lines.append(f"| t−{r['cutoff_days']} | {r['rule']} | {r['variant']} | {pct(r['mean_return'])} | {pct(r['volatility'])} "
            f"| {r['sharpe']:.3f} | {pct(r['max_drawdown'])} | {pct(r['total_return'])} | {r['mean_weight']:.3f} "
            f"| {r['var_breaches']}/{r['n_meetings']} ({pct(r['var_breach_rate'])}) | {r['kupiec_p']:.3f} "
            f"| {r['delta_mean_return'] * 1e4:+.4f} [{r['return_ci_low'] * 1e4:+.4f}, {r['return_ci_high'] * 1e4:+.4f}] |")
    lines += ["", "![Cumulative returns](cumulative_returns.png)", "", "### Continuous SPY buy-and-hold", "",
        "Held through the gaps, from each horizon's first entry to last exit. Daily-return annualization uses 252 trading days; "
        "these are not directly comparable to the event-window Sharpe/volatility above. No out-of-window VaR forecasts are made.", "",
        "| Cutoff | Start close (UTC) | End close (UTC) | Total | Annualized mean | Annualized vol | Annualized Sharpe | Max DD |",
        "|---|---|---|---:|---:|---:|---:|---:|"]
    for r in continuous:
        lines.append(f"| t−{r['cutoff_days']} | {r['start']} | {r['end']} | {pct(r['total_return'])} | {pct(r['annualized_mean'])} "
            f"| {pct(r['annualized_volatility'])} | {r['annualized_sharpe']:.3f} | {pct(r['max_drawdown'])} |")
    learned = [r for r in coefficients if r["n_prior_usable_meetings"] >= MIN_TRAIN_MEETINGS]
    lines += ["", "## Method and leakage safeguards", "",
        "- Fit a one-feature, no-intercept binary logistic regression with offset `logit(raw p_market)`, **pooling all three "
        "cutoff horizons** from earlier usable meetings. Objective is summed binary negative log likelihood plus "
        f"`λ β²/2`, fixed **λ={L2:g}**; no tuning. Current/future meetings, unresolved prior meetings and rows whose cutoff "
        "is not strictly earlier than the target cutoff are excluded. Each outcome/cutoff is one training row; the "
        "likelihood is a working binary calibration model, not a multinomial likelihood.",
        f"- Fewer than {MIN_TRAIN_MEETINGS} prior usable meetings → β=0, exactly the normalized market vector. "
        f"Otherwise apply `sigmoid(logit(p_market)+β signal)` then normalize across outcomes. Nonzero tilts clip raw "
        f"probabilities to [{EPSILON:g}, 1−{EPSILON:g}]. Market baseline is raw probabilities normalized. Smart, placebo "
        f"and all-wallet fits use the same training/evaluation meetings; the fixed smart heuristic uses **k={HEURISTIC_K:g}** "
        "without a training minimum. It uses Part A smart flow, not the app's different cluster-pilot data.",
        f"- {len(learned)} of {len(coefficients)} target cutoffs fit non-fallback coefficients. All coefficient/count records "
        "are in `coefficients.csv`; probability vectors in `predictions.csv`; meeting×cutoff losses in `accuracy.csv`.",
        "- The app's `analysis.py::analyze` uses decision-origin fixed-trading-day YES/NO windows and reads its own market "
        "probability; it cannot accept this vector or implement the requested cutoff-origin window unchanged. Therefore "
        "use the allowed historical per-outcome alternative. Conditional samples are earlier meetings at the **same cutoff "
        "horizon**, including pre-wallet meetings. Require both resolution proxy and post-decision exit close strictly "
        "before the target cutoff. At least three conditionally matching observations are required; otherwise use all prior "
        "meeting-window returns at that horizon. At least two pooled samples are required; there is no future-data fallback. "
        "Outcome range containment follows EventLens's convention; ambiguous ranges and `other` use the pooled fallback. "
        "Means and sample variances (ddof=1) are never fitted on the target return.",
        f"- {sum(s['pooled_fallback'] for s in scenario_rows)}/{len(scenario_rows)} outcome scenario estimates use the pooled "
        "fallback. Mixture mean is Σpμ and variance Σp(σ²+μ²)−(Σpμ)². VaR95 is the **moment-matched Gaussian** "
        "`max(0, 1.64485 σ−μ)`, not an exact Gaussian-mixture quantile or the app's empirical simulation.",
        "- Daily CSV dates are labels, not close timestamps. Assign each observed SPY close 16:00 America/New_York "
        "(DST-aware), then use the latest close ≤ the UTC-midnight cutoff: ordinarily the preceding trading day, "
        "**not that cutoff date's future close**. Exit is the close on the first observed trading date strictly after "
        "the decision date. Early-close sessions use the same 16:00 proxy; this cannot change midnight inclusion. "
        "Returns are close-to-close on the supplied price series; publication/corporate-action revision history is unverified.",
        "- **Execution qualification:** the requested window starts at the last close before the cutoff, but the "
        "wallet/market snapshot can contain information arriving between that close and UTC midnight. Returns are "
        "hypothetically marked from that observable close, not executable fills after all signals became available. "
        "This can bias apparent profitability; a next-open/next-close execution study is required before trading claims.",
        f"- Vol targeting: `w=min(1, {SIGMA_TARGET:g}/σ_pred)`, a fixed **1% event-window target** for every horizon. "
        f"Mean-variance: `w=clip(μ/({GAMMA:g} σ²),0,1)`, fixed **γ={GAMMA:g}**. No leverage, shorting, costs, slippage, "
        "interest or dividends beyond what is embedded in the supplied close series. Zero variance uses w=1 for vol "
        "targeting, and w=1 only for positive mean under mean-variance.",
        f"- **{BOOTSTRAPS:,} paired percentile bootstrap draws**, seed {SEED}, resampling whole meetings. "
        "For pooled accuracy, first average differences across a meeting's three cutoffs, then resample meetings; "
        "for portfolios resample paired returns within each separate horizon/rule. No multiple-comparison correction. "
        "Sign counts treat |difference|≤1e−12 as a tie.", "",
        "## Limitations", "",
        "The original wallet universe is retention-limited and retrospectively collected, not a proven contemporaneously "
        "available feed. Gamma resolution timestamps are metadata proxies, not verified on-chain finalization times; "
        "daily probability publication timestamps are unverified. Deduplication can collapse indistinguishable fills; "
        "participant flows are not independent wallet beliefs, holdings or unique economic fills. Few tightening/cutting "
        "meetings and sparse per-outcome histories make pooled scenario fallbacks common. A sign reversal or apparently "
        "good portfolio result can reflect unstable scenario means, probability normalization and weight clipping, not "
        "wallet skill. A meeting bootstrap assumes exchangeability despite regime change and serial dependence. Neither "
        "Kupiec non-rejection nor a bootstrap interval establishes calibration or investability at this sample size. "
        "Intervals resample the fixed walk-forward predictions, without refitting inside each bootstrap; only one seeded "
        "placebo cohort realization is evaluated. "
        "No hyperparameter selection was performed, but choosing to investigate this panel remains a research selection effect.", "",
        "## Reproduce and tests", "", "```sh",
        "python3 -m venv ~/data/polymarket/wallet_backtest_env",
        "~/data/polymarket/wallet_backtest_env/bin/pip install -r models/wallet_backtest/requirements.txt",
        "~/data/polymarket/wallet_backtest_env/bin/python models/wallet_backtest/backtest.py",
        "~/data/polymarket/wallet_backtest_env/bin/python -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v",
        "```", "", "Inputs, implementation SHA-256 hashes, dependency versions and fixed settings are recorded in "
        "`backtest_manifest.csv`. Full numeric results (unrounded) are in the companion small derived CSVs. "
        "Test output is recorded in the handoff report.", ""]
    (folder / "BACKTEST.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--prices", type=Path, default=ROOT / "datasets/index_daily.csv")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    rows, meetings = load_inputs(args.panel_dir)
    prices = load_prices(args.prices)
    windows = make_windows(meetings, prices)
    predictions, accuracy, portfolios, coefficients, scenarios = run_predictions(rows, meetings, windows)
    acc_summary = accuracy_summary(accuracy)
    port_summary = portfolio_summary(portfolios)
    continuous = continuous_buy_hold(portfolios, prices)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in (("predictions", predictions), ("accuracy", accuracy), ("portfolio_paths", portfolios),
                        ("coefficients", coefficients), ("scenarios", scenarios), ("accuracy_summary", acc_summary),
                        ("portfolio_summary", port_summary), ("continuous_buy_hold", continuous)):
        write_csv(args.output_dir / f"{name}.csv", table)
    charts(args.output_dir, accuracy, portfolios, prices)
    report(args.output_dir, acc_summary, port_summary, continuous, coefficients, scenarios)
    import matplotlib
    manifest = {"python": platform.python_version(), "numpy": np.__version__, "matplotlib": matplotlib.__version__,
        "lambda": L2, "min_train_meetings": MIN_TRAIN_MEETINGS, "heuristic_k": HEURISTIC_K,
        "sigma_target": SIGMA_TARGET, "gamma": GAMMA, "bootstrap_draws": BOOTSTRAPS, "seed": SEED}
    for path in (args.panel_dir / "panel.csv", args.panel_dir / "settlements.csv", args.prices,
                 Path(__file__), Path(__file__).with_name("build_panel.py"),
                 Path(__file__).with_name("requirements.txt"), Path(__file__).with_name("test_backtest.py")):
        manifest[path.name + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_csv(args.output_dir / "backtest_manifest.csv", [{"key": k, "value": v} for k, v in manifest.items()])
    print(f"Backtest complete: {len(coefficients)} meeting-cutoffs / {len({r['meeting'] for r in coefficients})} meetings; "
          f"{len(predictions)} probabilities; {len(portfolios)} portfolio windows.")
    for r in acc_summary:
        if r["cutoff_days"] == "pooled":
            print(f"{r['variant']:10s} Brier={r['brier']:.6f} Δ={r['delta_brier']:+.6f} "
                  f"CI=[{r['brier_ci_low']:+.6f},{r['brier_ci_high']:+.6f}] LogLoss={r['log_loss']:.6f}")


if __name__ == "__main__":
    main()
