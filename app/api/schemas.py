from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Horizon = Literal[1, 5, 20]


class Asset(BaseModel):
    asset: str
    supported: bool
    reason: str | None = None


class Snapshot(BaseModel):
    outcome: str
    market_probability: float
    date: str


class Event(BaseModel):
    id: str
    title: str
    meeting_month: str
    meeting_date: str
    status: Literal["resolved", "upcoming"]
    realized_outcome: str | None
    latest_snapshot: list[Snapshot]
    total_volume: float
    volume_note: str


class EventDetail(Event):
    history: dict[str, list[dict[str, Any]]]
    final_outcome: str | None
    wallet_informed: dict[str, Any]
    evidence: str
    evidence_rule: str


class ForecastMetrics(BaseModel):
    mse: float
    qlike: float
    n: int
    floor_hits: int
    latest_floor_hit: bool
    latest_variance: float
    latest_volatility: float


class Forecast(BaseModel):
    asset: str
    horizon: Horizon
    target: str
    forecast_floor: float
    as_of: str
    floor_policy: str
    models: dict[str, ForecastMetrics]
    series: list[dict[str, Any]]
    notes: str


class Holding(BaseModel):
    asset: str
    weight: float = Field(ge=0, le=1, allow_inf_nan=False)

    @field_validator("asset")
    @classmethod
    def supported(cls, value):
        if value not in ("SPY", "Cash"):
            raise ValueError(f"Unsupported asset {value}; only SPY and Cash have an available return model")
        return value


class Overrides(BaseModel):
    mu_yes: float | None = Field(default=None, ge=-1, allow_inf_nan=False)
    mu_no: float | None = Field(default=None, ge=-1, allow_inf_nan=False)


class AnalysisRequest(BaseModel):
    event_id: str | None = None
    outcome: str | None = None
    as_of: date | None = None
    horizon: Horizon = 5
    holdings: list[Holding] = Field(min_length=1)
    notional: float = Field(default=100000, gt=0, allow_inf_nan=False)
    overrides: Overrides | None = None

    @model_validator(mode="after")
    def weights_sum(self):
        if abs(sum(h.weight for h in self.holdings) - 1) > 1e-6:
            raise ValueError("holdings weights must sum to 1 (±1e-6)")
        return self


class Run(BaseModel):
    id: str
    title: str | None = None
    request: AnalysisRequest
    results: dict[str, Any]
    data_version: str
    seed: int
    created_at: str


class RunTitle(BaseModel):
    title: str | None = Field(max_length=160)

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1)
    event_id: str | None = None
    run_id: str | None = None
    asset: Literal["SPY"] = "SPY"
    horizon: Horizon | None = None


class Answer(BaseModel):
    mode: Literal["rule-based"] = "rule-based"
    answer: str
    citations: list[str]
