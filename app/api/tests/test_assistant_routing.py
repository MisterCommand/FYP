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
    ("Why do estimates differ?", "Wallet-informed probabilities are unavailable"),
    ("What about wallets?", "Wallet-informed probabilities are unavailable"),
    ("A variety of research questions", "I can explain market probabilities"),
])
def test_assistant_intents_match_words(client, question, prefix):
    response = client.post("/assistant/query", json={"question": question})
    assert response.status_code == 200
    answer = response.json()
    assert answer["mode"] == "rule-based"
    assert answer["answer"].startswith(prefix)
    assert "datasets/index_daily.csv" in answer["citations"]
