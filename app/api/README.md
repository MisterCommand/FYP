# EventLens research API

From this directory:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
.venv/bin/pytest -q
```

OpenAPI: `/docs`. SQLite defaults to `runs.sqlite3` here; set `EVENTLENS_DB`
to an alternate file. Data paths resolve from the source, not the working
directory. Dataset SHA-256 prefix, request, seed and results are saved per run.

Only SPY has price data. Cash earns zero. Probabilities are raw (not normalized)
and snapshots carry their observation dates; lifetime volume is not historical
point-in-time liquidity. Events are grouped by the CSV event_id/meeting_month.
Official scheduled FOMC decision dates are in `calendar_dates.py`, sourced from
https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (including its
historical calendars). Research scripts have no exact decision dates.

The nearest available undecided meeting rule and lagged 20-day history input
adapt `models/forecast_models.py`. Unlike its return targets, volatility uses
**log** returns. Five-day probability change is for the same meeting relative
to the last observation at/before five calendar days earlier. Expanding OLS
uses only labels whose full horizon ended before each test date. Both models
use identical complete-feature test dates. Overlapping horizons are retained;
scores are descriptive, not independent-sample significance tests. Latest
forecast means latest date with both features, which can precede price coverage.

Scenario groups use only prior, settled meetings with complete post-decision
price windows observable by as_of, excluding the selected event. Windows start
at the decision-day close and end H trading days later; simple holding-period
returns (not volatility targets). Groups with fewer than three meetings use
all available unconditional rolling windows, explicitly flagged Assumption.
Overrides shift conditional SPY means. Residual shapes come from all historical
overlapping H-day SPY returns available by as_of, demeaned. When a group has
at least three meetings, these residuals are scaled to its conditional standard
deviation; otherwise the unconditional scale is retained. Mixture moments are
analytical; VaR/ES use 10,000 fixed-seed bootstrap draws.
Reported loss percentages are percentage points, returns are decimal, horizon
volatility is not annualized. All results are hypothetical research, not advice.

Event status and final labels are gated by decision date, not a settlement
timestamp (none is supplied). Dataset final labels are used only for historical
scenario grouping, never forecast features. No wallet data is available.

Omitting event_id selects the next upcoming meeting with observations by as_of,
or the latest observed meeting if none is upcoming. Omitting outcome selects
its most likely non-"No change" outcome (falling back to the most likely outcome
if no change outcomes exist). Explicitly selected historical events retain their
dated probability snapshot; this is not a claim that the probability is current.

Forecast floors are pre-specified as max(1e-12, 1% of training mean RV), computed
separately at each expanding fit, not tuned on test outcomes. Each model reports
its out-of-sample floor_hits, latest_floor_hit and shared per-date series floors.
