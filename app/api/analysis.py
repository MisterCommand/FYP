import numpy as np
import pandas as pd

from data import cutoff, event_summary, load, snapshot

SEED = 42


def mixture(p, mu_yes, mu_no, var_yes, var_no):
    return (p * mu_yes + (1 - p) * mu_no,
            p * var_yes + (1 - p) * var_no + p * (1 - p) * (mu_yes - mu_no)**2)


def analyze(request, rows):
    as_of = cutoff(request.as_of)
    selected = [s for s in snapshot(rows, as_of) if s["outcome"] == request.outcome]
    if not selected:
        raise ValueError("No probability for this outcome on or before as_of")
    p = selected[0]["market_probability"]
    prices, markets = load()
    prices = prices[prices.date.le(as_of)].reset_index(drop=True)
    groups = {"yes": [], "no": []}
    for _, event in markets.groupby("event_id"):
        info = event_summary(event, as_of)
        meeting = pd.Timestamp(info["meeting_date"])
        # Exclude the selected event even when replaying it after settlement.
        if str(info["id"]) == request.event_id or meeting >= as_of or not info["realized_outcome"]:
            continue
        origin = prices[prices.date.le(meeting)]
        if origin.empty:
            continue
        pos = origin.index[-1]
        end = pos + request.horizon
        if end >= len(prices):
            continue
        value = prices.iloc[end].close / prices.iloc[pos].close - 1
        groups["yes" if info["realized_outcome"] == request.outcome else "no"].append(value)
    unconditional = (prices.close.shift(-request.horizon) / prices.close - 1).dropna().to_numpy()
    if not len(unconditional):
        raise ValueError("Insufficient price history at as_of for this horizon")
    assumptions = ["Cash has zero return; only SPY risk is modeled. Returns are decimal, losses are percent and USD."]
    samples, means, variances = {}, {}, {}
    for side in groups:
        samples[side] = np.array(groups[side]) if len(groups[side]) >= 3 else unconditional
        if len(groups[side]) < 3:
            assumptions.append(f"Assumption: {side.upper()} has fewer than 3 meetings; unconditional rolling SPY windows used.")
        means[side] = float(samples[side].mean())
        override = getattr(request.overrides, f"mu_{side}", None) if request.overrides else None
        if override is not None:
            means[side] = override
            assumptions.append(f"Assumption: {side.upper()} mean overridden by user.")
        variances[side] = float(samples[side].var())
    exposure = sum(h.weight for h in request.holdings if h.asset == "SPY")
    mean, variance = mixture(p, means["yes"], means["no"], variances["yes"], variances["no"])
    rng = np.random.default_rng(SEED)
    yes = rng.random(10000) < p
    simulated = np.empty(10000)
    for side, mask in (("yes", yes), ("no", ~yes)):
        residuals = samples[side] - samples[side].mean()
        simulated[mask] = (means[side] + rng.choice(residuals, int(mask.sum()))) * exposure
    losses = np.sort(-simulated)[::-1]
    var = max(0., float(np.quantile(losses, .95)))
    es = max(var, float(losses[:500].mean()))
    return {"probability": p, "probability_date": selected[0]["date"], "as_of": as_of.date().isoformat(),
            "sample_counts": {key: len(value) for key, value in groups.items()},
            "conditional_spy": {s: {"mean": means[s], "variance": variances[s], "effective_n": len(samples[s])} for s in groups},
            "mu_mix": mean * exposure, "sigma2_mix": variance * exposure**2,
            "horizon_volatility": float(np.sqrt(variance) * exposure),
            "var_95_pct": var * 100, "es_95_pct": es * 100,
            "var_95_usd": var * request.notional, "es_95_usd": es * request.notional,
            "scenario_returns": simulated.tolist(), "assumptions": assumptions,
            "evidence": "Assumption" if any(len(v) < 3 for v in groups.values()) else "Limited",
            "method": "10000 fixed-seed conditional bootstrap residual draws; empirical worst 500 losses for ES; positive loss metrics floored at zero."}
