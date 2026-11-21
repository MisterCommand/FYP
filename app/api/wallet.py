from functools import lru_cache

import numpy as np
import pandas as pd

from data import ROOT, snapshot

PILOT = ROOT / "polymarket/wallet_cluster_pilot/fed_20260531_v1"
WALLET_TILT_K = 0.5
METHOD = "Uncalibrated heuristic tilt from upstream wallet-cluster pilot (k=0.5); retrospective, not validated"


@lru_cache
def load_wallet():
    signals = pd.read_csv(PILOT / "daily_cluster_signals.csv",
                          dtype={key: "string" for key in ("event_id", "market_id", "cluster_id", "condition_id")},
                          true_values=["True"], false_values=["False"])
    for column in ("asof_utc", "interval_start_utc", "model_fit_cutoff_utc", "decision_cutoff_utc"):
        signals[column] = pd.to_datetime(signals[column], utc=True, errors="raise")
    mapping = pd.read_csv(ROOT / "polymarket/event_101772/market_tokens.csv", dtype="string")
    for frame in (signals, mapping):
        if not frame.event_id.str.fullmatch(r"\d+").all() or not frame.market_id.str.fullmatch(r"\d+").all():
            raise ValueError("Invalid wallet event/market ID")
    if signals.duplicated(["event_id", "market_id", "cluster_id", "asof_utc"]).any():
        raise ValueError("Duplicate wallet signal key")
    return signals, mapping.drop_duplicates("market_id")


def wallet_estimate(rows, as_of):
    signals, mapping = load_wallet()
    event_id = str(rows.iloc[0].event_id)
    mapping = mapping[mapping.event_id.eq(event_id)]
    if mapping.empty:
        return {"available": False, "reason": "No wallet data for this meeting"}
    day = pd.Timestamp(as_of)
    day = day.tz_localize("UTC") if day.tzinfo is None else day.tz_convert("UTC")
    eligible = signals[signals.event_id.eq(event_id) & signals.asof_utc.le(day)
                       & signals.forecast_input_allowed.eq(True)]
    if eligible.empty:
        return {"available": False, "reason": "No wallet signal at or before the as-of"}
    latest = eligible.sort_values("asof_utc").groupby(["market_id", "cluster_id"], sort=False).tail(1)
    observations = {s["outcome"]: s for s in snapshot(rows, as_of)}
    estimates = []
    for market in mapping.itertuples():
        local = rows[rows.market_id.astype(str).eq(market.market_id)]
        if local.empty or set(local.outcome) != {market.rate_outcome}:
            raise ValueError("Wallet market metadata does not match event outcomes")
        observation = observations.get(market.rate_outcome)
        if observation is None:
            return {"available": False, "reason": "No market probability at or before the as-of"}
        group = latest[latest.market_id.eq(market.market_id)]
        if group.empty:
            return {"available": False, "reason": "No wallet signal at or before the as-of for every outcome"}
        weights = group.active_wallet_count
        imbalance = float((group.aggregate_directional_imbalance.fillna(0) * weights).sum() / weights.sum()) if weights.sum() else 0.
        p = np.clip(observation["market_probability"], 1e-6, 1 - 1e-6)
        tilted = float(1 / (1 + np.exp(-(np.log(p / (1 - p)) + WALLET_TILT_K * imbalance))))
        estimates.append({"outcome": market.rate_outcome, "market_id": market.market_id,
                          "wallet_probability": tilted, "directional_imbalance": imbalance,
                          "signal_timestamp": group.asof_utc.max().isoformat(),
                          "active_wallets": int(weights.sum()),
                          "coverage_complete": bool(group.coverage_complete.all()),
                          "complete_wallets": int(group.complete_wallet_count.sum()),
                          "cluster_members": int(group.cluster_member_count.sum())})
    total = sum(e["wallet_probability"] for e in estimates)
    for estimate in estimates:
        estimate["wallet_probability"] /= total
    return {"available": True, "method": METHOD, "tilt_k": WALLET_TILT_K,
            "signal_timestamp": latest.asof_utc.max().isoformat(), "outcomes": estimates,
            "coverage_complete": bool(latest.coverage_complete.all()),
            "availability_basis": "trade_timestamp_only_retrospective"}
