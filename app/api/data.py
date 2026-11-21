from functools import lru_cache
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from calendar_dates import MEETINGS

ROOT = Path(__file__).resolve().parents[2] / "datasets"
WATCHLIST = ("SPY", "QQQ", "DIA", "AAPL", "MSFT", "NVDA", "AMZN", "TSLA")


@lru_cache
def load():
    prices = pd.read_csv(ROOT / "index_daily.csv")
    markets = pd.read_csv(ROOT / "forward_probabilities.csv")
    for frame in (prices, markets):
        frame["date"] = pd.to_datetime(frame.date, utc=True).dt.tz_localize(None).dt.normalize()
    prices = prices[prices.ticker.eq("SPY")].sort_values("date").reset_index(drop=True)
    markets["outcome"] = markets.outcome.replace({"no change": "No change"})
    markets["meeting_date"] = pd.to_datetime(markets.meeting_month.map(MEETINGS))
    return prices, markets


@lru_cache
def version():
    digest = hashlib.sha256()
    for name in ("index_daily.csv", "forward_probabilities.csv"):
        digest.update((ROOT / name).read_bytes())
    for path in sorted((ROOT / "polymarket").rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def cutoff(value=None):
    return pd.Timestamp(value) if value else max(frame.date.max() for frame in load())


def event_rows(event_id):
    rows = load()[1]
    return rows[rows.event_id.astype(str).eq(str(event_id))]


def default_event(as_of):
    rows = load()[1]
    available = rows[rows.date.le(as_of)]
    meetings = available[["event_id", "meeting_date"]].drop_duplicates().sort_values("meeting_date")
    upcoming = meetings[meetings.meeting_date.ge(as_of)]
    if meetings.empty:
        raise ValueError("No event observations available on or before as_of")
    return str((upcoming.iloc[0] if not upcoming.empty else meetings.iloc[-1]).event_id)


def default_outcome(rows, as_of):
    available = snapshot(rows, as_of)
    changes = [s for s in available if s["outcome"] != "No change"]
    return max(changes or available, key=lambda s: s["market_probability"])["outcome"] if available else None


def snapshot(rows, as_of):
    available = rows[rows.date.le(as_of)].sort_values("date")
    latest = available.groupby("outcome", sort=True).tail(1)
    return [{"outcome": r.outcome, "market_probability": float(r.market_probability),
             "date": r.date.date().isoformat()} for r in latest.itertuples()]


def event_summary(rows, as_of):
    first = rows.iloc[0]
    resolved = first.meeting_date <= as_of
    winners = rows[rows.final_outcome.eq(1)].outcome.unique()
    return {"id": str(first.event_id), "title": f"FOMC rate decision — {first.meeting_date:%b %Y}",
            "meeting_month": first.meeting_month, "meeting_date": first.meeting_date.date().isoformat(),
            "status": "resolved" if resolved else "upcoming",
            "realized_outcome": str(winners[0]) if resolved and len(winners) == 1 else None,
            "latest_snapshot": snapshot(rows, as_of),
            "total_volume": float(rows.drop_duplicates("market_id").lifetime_volume.sum()),
            "volume_note": "Lifetime volume, not point-in-time volume"}


def feature_frame(horizon, prices=None, markets=None):
    """Adapt forecast_models nearest-horizon selection and lagged history inputs.

    Use raw No change probabilities; exclude already decided meetings. The
    change compares the same meeting to its observation at/before t-5 days.
    """
    if prices is None:
        prices, markets = load()
    frame = prices.sort_values("date").copy()
    returns = np.log(frame.close).diff()
    frame["history"] = returns.shift(1).pow(2).rolling(20).mean()
    frame["target"] = sum(returns.shift(-i).pow(2) for i in range(1, horizon + 1))
    frame["target_end"] = frame.date.shift(-horizon)
    eligible = markets[markets.outcome.eq("No change") & markets.date.le(markets.meeting_date)]
    # Same nearest-available-horizon rule as models/forecast_models.py.
    features = []
    for day in frame.date:
        available = eligible[eligible.date.le(day) & eligible.meeting_date.ge(day)]
        if available.empty:
            continue
        meeting = available.meeting_date.min()
        series = available[available.meeting_date.eq(meeting)].sort_values("date")
        previous = series[series.date.le(day - pd.Timedelta(days=5))]
        if previous.empty:
            continue
        latest = series.iloc[-1]
        features.append({"date": day, "probability": latest.market_probability,
                         "probability_change": latest.market_probability - previous.iloc[-1].market_probability,
                         "probability_date": latest.date})
    columns = ["date", "probability", "probability_change", "probability_date"]
    return frame.merge(pd.DataFrame(features, columns=columns), on="date", how="inner").dropna(subset=["history"])
