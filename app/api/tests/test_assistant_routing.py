import pytest


@pytest.mark.parametrize("question,prefix", [
    ("What is the variance forecast?", "SPY 5-day horizon volatility"),
    ("Compare the forecast and VaR/ES.", "SPY 5-day horizon volatility"),
    ("How is risk estimated?", "I can explain market probabilities"),
    ("estimated", "I can explain market probabilities"),
    ("What is the estimated probability?", "Supply an event_id"),
    ("What is ES?", "95% VaR is the loss threshold"),
    ("ES", "95% VaR is the loss threshold"),
    ("Explain VaR/ES.", "95% VaR is the loss threshold"),
    ("What is expected shortfall?", "95% VaR is the loss threshold"),
    ("Why do estimates differ?", "Wallet-informed estimate unavailable"),
    ("What about wallets?", "Wallet-informed estimate unavailable"),
    ("A variety of research questions", "I can explain market probabilities"),
])
def test_assistant_intents_match_words(client, question, prefix):
    response = client.post("/assistant/query", json={"question": question})
    assert response.status_code == 200
    answer = response.json()
    assert answer["mode"] == "rule-based"
    assert answer["answer"].startswith(prefix)
    assert "datasets/index_daily.csv" in answer["citations"]


@pytest.mark.parametrize("horizon", [1, 5, 20])
def test_assistant_uses_selected_forecast_context(client, horizon):
    expected = client.get(f"/forecast?asset=SPY&horizon={horizon}").json()
    response = client.post("/assistant/query", json={
        "question": "What does the forecast say?", "asset": "SPY", "horizon": horizon,
    })
    assert response.status_code == 200
    answer = response.json()["answer"]
    assert answer.startswith(f"SPY {horizon}-day horizon volatility")
    for name, metrics in expected["models"].items():
        assert f"{name} {metrics['latest_volatility']:.3%}" in answer


def test_assistant_run_horizon_fallback_and_explicit_override(client):
    run = client.post("/analyses", json={"horizon": 20, "holdings": [{"asset": "SPY", "weight": 1}]}).json()
    request = {"question": "What does the forecast say?", "run_id": run["id"]}
    assert client.post("/assistant/query", json=request).json()["answer"].startswith("SPY 20-day")
    assert client.post("/assistant/query", json={**request, "horizon": 1}).json()["answer"].startswith("SPY 1-day")


@pytest.mark.parametrize("context", [{"horizon": 2}, {"asset": "QQQ"}])
def test_assistant_rejects_unsupported_forecast_context(client, context):
    response = client.post("/assistant/query", json={"question": "forecast", **context})
    assert response.status_code == 422
