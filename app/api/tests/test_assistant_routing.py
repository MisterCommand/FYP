import pytest


PRICES = "datasets/index_daily.csv"
MARKETS = "datasets/forward_probabilities.csv"


@pytest.mark.parametrize("question,prefix,sources", [
    ("What is the variance forecast?", "SPY 5-trading-day volatility", [PRICES, MARKETS]),
    ("Compare the forecast and VaR/ES.", "SPY 5-trading-day volatility", [PRICES, MARKETS]),
    ("How is risk estimated?", "I couldn’t match that", []),
    ("estimated", "I couldn’t match that", []),
    ("What is the estimated probability?", "Select a Fed meeting", []),
    ("What is ES?", "95% VaR is the loss threshold", []),
    ("ES", "95% VaR is the loss threshold", []),
    ("Explain VaR/ES.", "95% VaR is the loss threshold", []),
    ("What is expected shortfall?", "95% VaR is the loss threshold", []),
    ("Why do estimates differ?", "The baseline model uses past SPY returns", [PRICES, MARKETS]),
    ("What about wallets?", "Wallet-informed estimates are unavailable", [MARKETS]),
    ("A variety of research questions", "I couldn’t match that", []),
])
def test_assistant_intents_match_words(client, question, prefix, sources):
    response = client.post("/assistant/query", json={"question": question})
    assert response.status_code == 200
    answer = response.json()
    assert answer["mode"] == "rule-based"
    assert answer["answer"].startswith(prefix)
    assert answer["citations"] == sources
    if question == "Compare the forecast and VaR/ES.":
        assert "Expected shortfall" in answer["answer"]


def test_assistant_run_horizon_fallback_and_explicit_override(client):
    run = client.post("/analyses", json={"horizon": 20, "holdings": [{"asset": "SPY", "weight": 1}]}).json()
    request = {"question": "What does the forecast say?", "run_id": run["id"]}
    assert client.post("/assistant/query", json=request).json()["answer"].startswith("SPY 20-trading-day")
    assert client.post("/assistant/query", json={**request, "horizon": 1}).json()["answer"].startswith("SPY 1-trading-day")


@pytest.mark.parametrize("context", [{"horizon": 2}, {"asset": "QQQ"}])
def test_assistant_rejects_unsupported_forecast_context(client, context):
    response = client.post("/assistant/query", json={"question": "forecast", **context})
    assert response.status_code == 422
