from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from analysis import analyze
from assistant import SourceFile, answer_question
from data import ROOT, WATCHLIST, cutoff, default_event, default_outcome, event_rows, event_summary, load
from forecast import forecast
from schemas import (AnalysisRequest, Answer, Asset, AssistantRequest, Event,
                     EventDetail, Forecast, Run)
import store

app = FastAPI(title="EventLens research API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])


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


@app.get("/runs", response_model=list[Run])
def runs():
    return store.all_runs()


@app.get("/runs/{run_id}", response_model=Run)
def run_detail(run_id: str):
    return require_run(run_id)


@app.post("/assistant/query", response_model=Answer)
def assistant(request: AssistantRequest):
    run = require_run(request.run_id) if request.run_id else None
    event_id = request.event_id or (run["request"]["event_id"] if run else None)
    if run and event_id != run["request"]["event_id"]:
        raise HTTPException(422, "The selected event does not belong to this saved run.")
    as_of = date.fromisoformat(run["results"]["as_of"]) if run else None
    event = event_detail(event_id, as_of) if event_id else None
    return answer_question(request, event, run)


@app.get("/assistant/sources/{filename}")
def assistant_source(filename: SourceFile):
    return FileResponse(ROOT / filename, filename=filename, media_type="text/csv")
