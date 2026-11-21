import numpy as np
import pandas as pd
import pytest

from analysis import mixture
from data import feature_frame, load


def body(client, **kwargs):
    event = client.get("/events").json()[0]
    return {"event_id": event["id"], "horizon": 5,
            "holdings": [{"asset": "SPY", "weight": .5}, {"asset": "Cash", "weight": .5}], **kwargs}


def test_assets_events(client):
    assets = client.get("/assets").json()
    assert len(assets) == 8
    assert [a["asset"] for a in assets if a["supported"]] == ["SPY"]
    events = client.get("/events").json()
    assert events and len({e["id"] for e in events}) == len(events)
    event = events[0]
    detail = client.get(f"/events/{event['id']}").json()
    assert detail["history"] and not detail["wallet_informed"]["available"]
    assert detail["evidence"] == "Limited"
    early = client.get(f"/events/{event['id']}?as_of=2022-01-01").json()
    assert early["history"] == {} and early["final_outcome"] is None
    assert early["evidence"] == "Unavailable"
    assert client.get("/events/missing").status_code == 404
    assert client.get("/events?as_of=bad").status_code == 422
    assert client.get("/events?asset=QQQ").status_code == 422


@pytest.mark.parametrize("event_id", ["901498", "901497"])
def test_overview_expectations_snapshot(client, event_id):
    raw = client.get(f"/events/{event_id}").json()
    response = client.get(f"/events/{event_id}?expectations=true")
    assert response.status_code == 200
    detail = response.json()
    assert detail["history"] == raw["history"]
    assert any(s["date"] > raw["meeting_date"] for s in raw["latest_snapshot"])
    for snapshot in detail["latest_snapshot"]:
        expected = max((p for p in raw["history"][snapshot["outcome"]]
                        if p["date"] <= raw["meeting_date"]), key=lambda p: p["date"])
        assert snapshot["date"] == expected["date"]
        assert snapshot["market_probability"] == expected["market_probability"]
    assert client.get(f"/events/{event_id}").json() == raw


def test_overview_expectations_upcoming_empty_and_errors(client):
    path = "/events/901493?as_of=2023-01-30"
    latest = client.get(path).json()
    upcoming = client.get(path + "&expectations=true").json()
    assert upcoming["status"] == "upcoming"
    assert upcoming["latest_snapshot"] == latest["latest_snapshot"]
    early = client.get("/events/901493?as_of=2022-01-01&expectations=true").json()
    assert early["latest_snapshot"] == [] and early["history"] == {}
    assert client.get("/events/missing?expectations=true").status_code == 404
    assert client.get(path + "&expectations=invalid").status_code == 422


@pytest.mark.parametrize("horizon", [1, 5, 20])
def test_forecast(client, horizon):
    response = client.get(f"/forecast?asset=SPY&horizon={horizon}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["series"]) == data["models"]["baseline"]["n"] == data["models"]["augmented"]["n"] > 0
    assert all(m["latest_variance"] >= data["forecast_floor"] and m["qlike"] >= 0 for m in data["models"].values())
    for name, metrics in data["models"].items():
        assert metrics["floor_hits"] == sum(point[name] == point["floor"] for point in data["series"])
    assert client.get("/forecast?asset=QQQ").status_code == 422
    assert client.get("/forecast?horizon=2").status_code == 422


def test_no_lookahead():
    prices, markets = load()
    day = pd.Timestamp("2025-06-02")
    original = feature_frame(5, prices, markets)
    changed_prices, changed_markets = prices.copy(), markets.copy()
    changed_prices.loc[changed_prices.date.gt(day), "close"] *= 2
    changed_markets.loc[changed_markets.date.gt(day), "market_probability"] = .123
    changed_markets["final_outcome"] = 1 - changed_markets.final_outcome
    changed = feature_frame(5, changed_prices, changed_markets)
    cols = ["date", "history", "probability", "probability_change", "probability_date"]
    pd.testing.assert_frame_equal(original.loc[original.date.le(day), cols], changed.loc[changed.date.le(day), cols])
    assert original.probability_date.le(original.date).all()
    row = original[original.date.eq(day)].iloc[0]
    position = prices.index[prices.date.eq(day)][0]
    logs = np.log(prices.close).diff()
    assert row.target == pytest.approx(sum(logs.iloc[position + 1:position + 6]**2))
    assert row.history == pytest.approx(logs.iloc[position - 20:position].pow(2).mean())


def test_analysis_runs(client):
    assert client.get("/runs").json() == []
    response = client.post("/analyses", json=body(client))
    assert response.status_code == 200
    run = response.json()
    result = run["results"]
    assert result["es_95_pct"] >= result["var_95_pct"] >= 0
    assert len(result["scenario_returns"]) == 10000
    assert len(set(result["scenario_returns"])) >= 500
    assert result["es_95_pct"] > result["var_95_pct"] * 1.1
    assert run["seed"] == 42 and run["data_version"]
    assert client.get(f"/runs/{run['id']}").json() == run
    assert len(client.get("/runs").json()) == 1
    repeated = client.post("/analyses", json=body(client)).json()
    assert repeated["results"] == result
    assert client.get("/runs/missing").status_code == 404


@pytest.mark.parametrize("holdings", [[], [{"asset": "SPY", "weight": -.1}], [{"asset": "SPY", "weight": .9}], [{"asset": "QQQ", "weight": 1}]])
def test_weight_validation(client, holdings):
    response = client.post("/analyses", json=body(client, holdings=holdings))
    assert response.status_code == 422
    assert response.json()["detail"]


def test_analysis_empty_and_overrides(client):
    assert client.post("/analyses", json=body(client, as_of="2022-01-01")).status_code == 422
    assert client.post("/analyses", json=body(client, outcome="missing")).status_code == 422
    assert client.post("/analyses", json=body(client, event_id="missing")).status_code == 404
    result = client.post("/analyses", json=body(client, holdings=[{"asset": "Cash", "weight": 1}], overrides={"mu_yes": .1, "mu_no": -.1})).json()["results"]
    assert result["horizon_volatility"] == result["var_95_usd"] == result["es_95_usd"] == 0
    early = client.post("/analyses", json=body(client, as_of="2023-01-30")).json()["results"]
    assert early["sample_counts"] == {"yes": 0, "no": 0}
    assert early["evidence"] == "Assumption"
    assert any("unconditional" in message for message in early["assumptions"])


def test_saved_run_event_evidence_cutoff(client):
    event = client.get("/events").json()[-1]
    day = "2026-06-01"
    run = client.post("/analyses", json=body(client, event_id=event["id"], as_of=day)).json()
    saved = client.get(f"/runs/{run['id']}").json()
    assert saved["results"]["as_of"] == day
    evidence = client.get(f"/events/{event['id']}?as_of={saved['results']['as_of']}").json()
    assert evidence["status"] == "upcoming"
    assert evidence["realized_outcome"] is None
    assert all(s["date"] <= day for s in evidence["latest_snapshot"])
    assert all(p["date"] <= day for history in evidence["history"].values() for p in history)
    selected = next(s for s in evidence["latest_snapshot"] if s["outcome"] == saved["request"]["outcome"])
    assert selected["market_probability"] == saved["results"]["probability"]
    assert selected["date"] == saved["results"]["probability_date"]
    latest = client.get(f"/events/{event['id']}").json()
    assert latest["status"] == "resolved"
    assert max(s["date"] for s in latest["latest_snapshot"]) > day
    empty = client.get(f"/events/{event['id']}?as_of=2022-01-01").json()
    assert empty["latest_snapshot"] == [] and empty["history"] == {}
    assert client.get(f"/events/{event['id']}?as_of=invalid").status_code == 422


def test_default_event_outcome(client):
    request = {"holdings": [{"asset": "SPY", "weight": 1}]}
    response = client.post("/analyses", json=request)
    assert response.status_code == 200
    run = response.json()
    latest = client.get("/events").json()[-1]
    assert run["request"]["event_id"] == latest["id"]
    change = max((s for s in latest["latest_snapshot"] if s["outcome"] != "No change"), key=lambda s: s["market_probability"])
    assert run["request"]["outcome"] == change["outcome"]
    upcoming = client.post("/analyses", json={**request, "as_of": "2023-01-30"}).json()
    assert upcoming["request"]["event_id"] == client.get("/events").json()[0]["id"]
    assert client.post("/analyses", json={**request, "as_of": "2022-01-01"}).status_code == 422


def test_mixture():
    assert mixture(.25, .1, -.1, .04, .01) == pytest.approx((-.05, .025))
    assert mixture(1, .1, -.1, .04, .01) == pytest.approx((.1, .04))
    assert mixture(0, .1, -.1, .04, .01) == pytest.approx((-.1, .01))


@pytest.mark.parametrize("weight", [0, .5, 1])
def test_bounded_override_losses(client, weight):
    response = client.post("/analyses", json=body(
        client, notional=100000,
        holdings=[{"asset": "SPY", "weight": weight}, {"asset": "Cash", "weight": 1 - weight}],
        overrides={"mu_yes": -1, "mu_no": -1}))
    assert response.status_code == 200
    result = response.json()["results"]
    assert min(result["scenario_returns"]) >= -weight
    assert 0 <= result["var_95_pct"] <= result["es_95_pct"] <= 100
    assert result["es_95_usd"] <= 100000
    assert result["evidence"] == "Assumption"
    assert all(side["status"] == "Assumption" for side in result["conditional_spy"].values())


def test_override_evidence_and_context(client):
    for overrides in ({}, {"mu_yes": .01}, {"mu_no": 0}):
        result = client.post("/analyses", json=body(client, overrides=overrides)).json()["results"]
        assert result["evidence"] == ("Assumption" if overrides else "Limited")
    assert client.get("/analyses/context").json() == {"as_of": str(load()[0].date.max().date())}
    assert client.post("/analyses", json=body(client, overrides={"mu_yes": -1.01})).status_code == 422
