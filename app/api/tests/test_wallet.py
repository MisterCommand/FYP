import numpy as np
import pandas as pd
import pytest

from data import event_rows
import wallet


def test_wallet_available(client):
    result = client.get("/events/101772?as_of=2026-06-10").json()["wallet_informed"]
    assert result["available"]
    assert "Uncalibrated heuristic" in result["method"]
    assert result["signal_timestamp"] == "2026-06-10T00:00:00+00:00"
    assert len(result["outcomes"]) == 5
    assert {r["market_id"] for r in result["outcomes"]} == {str(i) for i in range(906972, 906977)}
    assert sum(r["wallet_probability"] for r in result["outcomes"]) == pytest.approx(1)
    assert all(0 < r["wallet_probability"] < 1 and r["coverage_complete"] for r in result["outcomes"])
    signals, _ = wallet.load_wallet()
    signals = signals[signals.asof_utc.eq(pd.Timestamp("2026-06-10", tz="UTC"))]
    raw = {s["outcome"]: s["market_probability"] for s in wallet.snapshot(event_rows("101772"), pd.Timestamp("2026-06-10"))}
    tilted = {}
    for outcome in result["outcomes"]:
        group = signals[signals.market_id.eq(outcome["market_id"])]
        n = group.active_wallet_count.sum()
        imbalance = (group.aggregate_directional_imbalance.fillna(0) * group.active_wallet_count).sum() / n if n else 0
        assert outcome["directional_imbalance"] == pytest.approx(imbalance)
        assert outcome["active_wallets"] == n
        p = np.clip(raw[outcome["outcome"]], 1e-6, 1 - 1e-6)
        tilted[outcome["outcome"]] = 1 / (1 + np.exp(-(np.log(p / (1 - p)) + .5 * imbalance)))
    for outcome in result["outcomes"]:
        assert outcome["wallet_probability"] == pytest.approx(tilted[outcome["outcome"]] / sum(tilted.values()))


def test_wallet_unavailable(client):
    assert client.get("/events/481717").json()["wallet_informed"] == {
        "available": False, "reason": "No wallet data for this meeting"}
    assert client.get("/events/101772?as_of=2026-05-30").json()["wallet_informed"] == {
        "available": False, "reason": "No wallet signal at or before the as-of"}


def test_wallet_no_lookahead(monkeypatch):
    signals, mapping = wallet.load_wallet()
    assert str(signals.event_id.dtype) == "string"
    assert str(signals.asof_utc.dtype) == "datetime64[ns, UTC]"
    rows = event_rows("101772")
    day = pd.Timestamp("2026-06-10")
    expected = wallet.wallet_estimate(rows, day)
    changed = signals.copy()
    future = changed.asof_utc.gt(day.tz_localize("UTC"))
    changed.loc[future, "aggregate_directional_imbalance"] = 1
    changed.loc[future, "active_wallet_count"] = 10000
    monkeypatch.setattr(wallet, "load_wallet", lambda: (changed, mapping))
    changed_rows = rows.copy()
    changed_rows.loc[changed_rows.date.gt(day), "market_probability"] = .99
    assert wallet.wallet_estimate(changed_rows, day) == expected
    changed.loc[changed.asof_utc.eq(day.tz_localize("UTC")), "forecast_input_allowed"] = False
    assert wallet.wallet_estimate(rows, day)["signal_timestamp"] == "2026-06-09T00:00:00+00:00"


def test_wallet_missing_ratio(monkeypatch):
    signals, mapping = wallet.load_wallet()
    changed = signals.copy()
    changed["aggregate_directional_imbalance"] = np.nan
    monkeypatch.setattr(wallet, "load_wallet", lambda: (changed, mapping))
    rows = event_rows("101772")
    result = wallet.wallet_estimate(rows, pd.Timestamp("2026-06-10"))
    raw = {r["outcome"]: r["market_probability"] for r in wallet.snapshot(rows, pd.Timestamp("2026-06-10"))}
    total = sum(np.clip(p, 1e-6, 1 - 1e-6) for p in raw.values())
    for outcome in result["outcomes"]:
        assert outcome["directional_imbalance"] == 0
        assert outcome["wallet_probability"] == pytest.approx(np.clip(raw[outcome["outcome"]], 1e-6, 1 - 1e-6) / total)


def test_wallet_bad_mapping(monkeypatch):
    signals, mapping = wallet.load_wallet()
    mapping = mapping.copy()
    mapping.loc[:, "rate_outcome"] = "wrong"
    monkeypatch.setattr(wallet, "load_wallet", lambda: (signals, mapping))
    with pytest.raises(ValueError, match="metadata"):
        wallet.wallet_estimate(event_rows("101772"), pd.Timestamp("2026-06-10"))
