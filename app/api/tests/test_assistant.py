import pytest

from data import ROOT

EVENT = "481717"
MARKETS = "datasets/forward_probabilities.csv"
PRICES = "datasets/index_daily.csv"
EVENT_SOURCES = [f"event:{EVENT}", MARKETS]


def ask(client, question, **context):
    response = client.post("/assistant/query", json={"question": question, "event_id": EVENT, **context})
    assert response.status_code == 200
    answer = response.json()
    assert answer["mode"] == "rule-based"
    return answer["answer"], answer["citations"]


@pytest.mark.parametrize(("question", "selected", "expected"), [
    ("What does the forecast say?", 20, 20),
    ("What does the forecast say?", 1, 1),
    ("What does the forecast say?", 5, 5),
    ("What is the 20-day volatility forecast?", 5, 20),
    ("Show the one trading day forecast.", 20, 1),
])
def test_forecast_matches_dashboard(client, question, selected, expected):
    result = client.get(f"/forecast?horizon={expected}").json()
    answer, sources = ask(client, question, horizon=selected, asset="SPY")
    assert f"SPY {expected}-trading-day" in answer
    assert result["as_of"] in answer
    for name, metrics in result["models"].items():
        assert f"{name} {metrics['latest_volatility']:.3%}" in answer
    assert sources == [PRICES, MARKETS]


@pytest.mark.parametrize(("question", "expected"), [
    ("What is the probability of the selected outcome?", "No change: 10.50%"),
    ("What were the odds of a 25 bps cut?", "25 bps decrease: 0.15%"),
    ("What are the chances the Fed raised rates by a quarter point?", "25 bps increase: 88.50%"),
    ("And what about leaving rates unchanged?", "No change: 10.50%"),
    ("What is the probability of a 25 bps increase on September 1?", "25 bps increase: 54.50% (observed 2026-09-01)"),
    ("What were the odds of a 25 bps increase on 2026-09-01?", "25 bps increase: 54.50% (observed 2026-09-01)"),
    ("What were the odds of a 25 bps increase on 2022-01-01?", "no market observation for 25 bps increase on 2022-01-01"),
])
def test_market_answer_uses_outcome_and_observation_date(client, question, expected):
    answer, sources = ask(client, question, outcome="No change")
    assert expected in answer
    assert sources == EVENT_SOURCES
    assert "Sep 2026" in answer and "88.50%" not in answer.replace(expected, "")


@pytest.mark.parametrize(("question", "expected"), [
    ("What is the volatility forecast for TSLA?", "No volatility forecast is available for TSLA"),
    ("What is the 10-day volatility forecast?", "Choose one supported forecast horizon"),
    ("What is the 1.5-day volatility forecast?", "Choose one supported forecast horizon"),
    ("What is the twenty-one-day volatility forecast?", "Choose one supported forecast horizon"),
    ("What is the forecast for twenty one trading days?", "Choose one supported forecast horizon"),
    ("What was the SPY forecast on September 1, 2026?", "can’t look up a forecast for a requested date"),
    ("What is the probability that it will rain tomorrow?", "I couldn’t match that"),
    ("What's the odds of a rate cut at the July 2026 meeting?", "Select the meeting you meant"),
    ("What is the variance of SPY returns?", "I couldn’t match that"),
    ("Why did the Fed raise rates?", "I couldn’t match that"),
    ("What were the chances of no change on February 31?", "That date isn’t valid"),
    ("What were the chances of no change yesterday?", "Give an exact observation date"),
    ("probability", "Select a Fed meeting"),
])
def test_declines_unsupported_requests_without_unrelated_evidence(client, question, expected):
    answer, sources = ask(client, question, **({"event_id": None} if question == "probability" else {}))
    assert expected in answer
    assert not sources


def test_mixed_market_and_forecast_question(client):
    answer, sources = ask(client, "What are the odds of a cut, and what does the SPY volatility forecast say?", horizon=20)
    assert "25 bps decrease: 0.15%" in answer
    assert "SPY 20-trading-day" in answer
    assert sources == [*EVENT_SOURCES, PRICES]


def test_event_facts_and_source_verification(client):
    answer, sources = ask(client, "When was this meeting and is it resolved?")
    assert "2026-09-16 (resolved)" in answer and "Recorded outcome: 25 bps increase." in answer
    assert sources[:2] == EVENT_SOURCES and "fomccalendars.htm" in sources[2]
    answer, sources = ask(client, "How much was traded?")
    assert "$208,022,818" in answer and "over their lifetime" in answer
    assert sources == EVENT_SOURCES
    assert "historical traded price, not the final outcome" in ask(client, "Why is the market probability not 100% if the meeting is resolved?")[0]
    assert f"event_id {EVENT}" in ask(client, "Where did these numbers come from? Can I verify them?")[0]


def test_saved_run_answers_agree_with_immutable_results(client):
    run = client.post("/analyses", json={
        "event_id": EVENT, "outcome": "25 bps increase", "as_of": "2026-09-01",
        "horizon": 20, "holdings": [{"asset": "SPY", "weight": 1}],
    }).json()
    answer, sources = ask(client, "What probability did this run use?", run_id=run["id"])
    assert f"{run['results']['probability']:.2%}, observed on 2026-09-01" in answer
    assert sources == [f"run:{run['id']}"]
    answer, sources = ask(client, "What volatility did this run estimate?", run_id=run["id"])
    assert f"{run['results']['horizon_volatility']:.3%} portfolio volatility over 20 trading days" in answer
    assert sources == [f"run:{run['id']}"]
    answer, sources = ask(client, "What is the VaR and ES for this run?", run_id=run["id"])
    assert f"VaR {run['results']['var_95_pct']:.3f}%, ES {run['results']['es_95_pct']:.3f}%" in answer
    assert sources == [f"run:{run['id']}"]
    assert "no market observation" in ask(client, "Probability of an increase on September 16?", run_id=run["id"])[0]
    assert client.post("/assistant/query", json={"question": "probability", "run_id": run["id"], "event_id": "287395"}).status_code == 422


@pytest.mark.parametrize("filename", ["forward_probabilities.csv", "index_daily.csv"])
def test_cited_csv_matches_shipped_data(client, filename):
    source = client.get(f"/assistant/sources/{filename}")
    assert source.content == (ROOT / filename).read_bytes()
    assert source.headers["content-type"].startswith("text/csv")
    assert filename in source.headers["content-disposition"]


def test_assistant_validation(client):
    assert client.post("/assistant/query", json={"question": "probability", "run_id": "missing"}).status_code == 404
    assert client.get("/assistant/sources/README.md").status_code == 422
    for request in ({"question": ""}, {"question": "  "}, {"question": "a" * 501}, {"question": "forecast", "horizon": 9}):
        assert client.post("/assistant/query", json=request).status_code == 422
