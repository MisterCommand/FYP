from datetime import date
import re

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from analysis import analyze
from data import WATCHLIST, cutoff, default_event, default_outcome, event_rows, event_summary, load
from forecast import forecast
from schemas import (AnalysisRequest, Answer, Asset, AssistantRequest, Event,
                     EventDetail, Forecast, Run, RunTitle)
import store

app = FastAPI(title="EventLens research API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["*"])


def supported(asset):
    if asset != "SPY":
        raise HTTPException(422, detail=[{"loc": ["query", "asset"], "msg": f"Unsupported asset {asset}; only SPY price data exists", "type": "value_error"}])


def require_event(event_id):
    rows = event_rows(event_id)
    if rows.empty:
        raise HTTPException(404, "Event not found")
    return rows


def require_run(run_id):
    run = store.get(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@app.get("/assets", response_model=list[Asset])
def assets():
    return [{"asset": a, "supported": a == "SPY", "reason": None if a == "SPY" else "No price data ingested yet"} for a in WATCHLIST]


@app.get("/events", response_model=list[Event])
def events(asset: str = "SPY", as_of: date | None = None):
    supported(asset)
    return sorted([event_summary(rows, cutoff(as_of)) for _, rows in load()[1].groupby("event_id")], key=lambda e: e["meeting_date"])


@app.get("/events/{event_id}", response_model=EventDetail)
def event_detail(event_id: str, as_of: date | None = None):
    rows = require_event(event_id)
    day = cutoff(as_of)
    info = event_summary(rows, day)
    history = {}
    for outcome, group in rows[rows.date.le(day)].groupby("outcome"):
        history[outcome] = [{"date": r.date.date().isoformat(), "market_probability": float(r.market_probability)} for r in group.sort_values("date").itertuples()]
    return {**info, "history": history, "final_outcome": info["realized_outcome"],
            "wallet_informed": {"available": False, "reason": "No wallet/settlement data ingested yet"},
            "evidence": "Limited" if history else "Unavailable",
            "evidence_rule": "Limited when probability observations exist by as_of; otherwise Unavailable. No wallet-level evidence. Lifetime volume is not point-in-time."}


@app.get("/forecast", response_model=Forecast)
def get_forecast(asset: str = "SPY", horizon: int = 5):
    supported(asset)
    if horizon not in (1, 5, 20):
        raise HTTPException(422, "horizon must be 1, 5 or 20")
    return forecast(horizon)


@app.post("/analyses", response_model=Run)
def analyses(request: AnalysisRequest):
    try:
        event_id = request.event_id or default_event(cutoff(request.as_of))
        rows = require_event(event_id)
        outcome = request.outcome or default_outcome(rows, cutoff(request.as_of))
        request = request.model_copy(update={"event_id": event_id, "outcome": outcome})
        results = analyze(request, rows)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return store.save(request, results)


@app.patch("/analyses/{run_id}", response_model=Run)
def rename_analysis(run_id: str, request: RunTitle):
    run = store.rename(run_id, request.title)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@app.delete("/analyses/{run_id}", status_code=204)
def delete_analysis(run_id: str):
    if not store.delete(run_id):
        raise HTTPException(404, "Run not found")
    return Response(status_code=204)


@app.get("/runs", response_model=list[Run])
def runs():
    return store.all_runs()


@app.get("/runs/{run_id}", response_model=Run)
def run_detail(run_id: str):
    return require_run(run_id)


@app.post("/assistant/query", response_model=Answer)
def assistant(request: AssistantRequest):
    words = set(re.findall(r"\b[a-z]+\b", request.question.lower()))
    run = require_run(request.run_id) if request.run_id else None
    event_id = request.event_id or (run["request"]["event_id"] if run else None)
    event = event_detail(event_id) if event_id else None
    citations = ["datasets/forward_probabilities.csv", "datasets/index_daily.csv"]
    if run:
        citations.append(f"run:{run['id']}")
    if event:
        citations.append(f"event:{event_id}")
    if words & {"forecast", "forecasts", "volatility", "variance"}:
        horizon = request.horizon or (run["request"]["horizon"] if run else 5)
        result = get_forecast(asset=request.asset, horizon=horizon)
        answer = f"{result['asset']} {result['horizon']}-day horizon volatility at {result['as_of']}: " + "; ".join(f"{name} {m['latest_volatility']:.3%}, OOS MSE {m['mse']:.6g}, QLIKE {m['qlike']:.4f}, n={m['n']}" for name, m in result["models"].items()) + ". These are research estimates, not investment advice."
    elif words & {"wallet", "wallets", "differ", "why"}:
        answer = "Wallet-informed probabilities are unavailable: No wallet/settlement data ingested yet. Market probabilities are raw traded prices. Forecasts differ because augmented OLS also uses the next meeting's No change probability and its five-day change; scenario estimates instead use conditional historical returns."
        if run:
            answer += " Run assumptions: " + " ".join(run["results"]["assumptions"])
    elif words & {"var", "shortfall", "es"}:
        answer = "95% VaR is the loss threshold exceeded in approximately 5% of simulated scenarios, not a maximum loss. ES is the mean of the worst 5% of losses. Both are positive loss percentages (floored at zero)."
        if run:
            answer += f" This run: VaR {run['results']['var_95_pct']:.3f}%, ES {run['results']['es_95_pct']:.3f}%."
    elif words & {"probability", "probabilities", "odds"}:
        answer = ("Latest observations: " + "; ".join(f"{s['outcome']}: {s['market_probability']:.2%} on {s['date']}" for s in event["latest_snapshot"])) if event else "Supply an event_id to inspect the latest market probabilities."
    else:
        answer = "I can explain market probabilities, wallet data limitations, baseline versus augmented volatility forecasts, and saved-run VaR/ES. Supply an event_id or run_id for context. Research only; no trading or personalized advice."
    return {"mode": "rule-based", "answer": answer, "citations": citations}
