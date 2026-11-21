# EventLens research prototype

First working app: Next.js App Router + React/TypeScript + TanStack Query +
Recharts, backed by FastAPI/Pydantic, pandas/NumPy and SQLite. No API keys needed.
Only SPY has price data; the remaining seven watchlist assets are unavailable.
Cash earns zero. All scenarios are hypothetical and do not place orders.

## Setup

Requires Python 3.11+, Node.js 20.9+ and npm. From the repository root:

```sh
python3 -m venv app/api/.venv
app/api/.venv/bin/pip install -r app/api/requirements.txt
cd app/web
npm ci
npm run build
cd ../..
./app/start.sh
```

Visit http://localhost:3000. The launcher starts uvicorn on `${API_PORT:-8000}`
and `next start` on `${PORT:-3000}`. Build first; use unoccupied ports when
launching. Ctrl-C stops both services started by that launcher. Run the launcher
from any directory.

The browser calls only same-origin `/api/*`. Next rewrites those requests to
`http://127.0.0.1:8000/*` by default. Set `API_PORT` when building to change the
local backend port, or override the full target with `API_URL` (without a trailing
slash). Rewrites are embedded in the production build; changing only the launcher
environment does not retarget an existing build:

```sh
npm run build # API_URL and API_PORT unset: backend 8000, frontend build .next
```

To run an additional production pair without replacing or stopping the default
3000/8000 services, from `app/`:

```sh
cd web
PORT=3001 API_PORT=8001 API_URL=http://127.0.0.1:8001 npm run build
cd ..
PORT=3001 API_PORT=8001 ./start.sh
```

Visit http://localhost:3001. Non-default frontend ports use separate build
directories (`.next-3001` in this example); use the same `PORT` for build and
launch. The default port 3000 still uses `.next`. This keeps alternate builds
from overwriting files used by the default running frontend. For a custom
`API_URL`, also supply the same value when launching.

SQLite defaults to `app/api/runs.sqlite3`; override with `EVENTLENS_DB` when
launching. Data paths resolve relative to the backend, independently of the
working directory. SQLite, virtualenvs, node_modules and all `.next*` build
directories are ignored.

## Development and checks

In one terminal, from `app/api`:

```sh
.venv/bin/uvicorn main:app --reload --port 8000
.venv/bin/pytest -q
```

In another, from `app/web`:

```sh
npm run dev
npm run typecheck
npm run build
```

There is no configured lint command. TypeScript is strict, and production builds
also check types. OpenAPI documentation is at http://localhost:8000/docs.

## Screens and research conventions

- **Overview:** SPY watchlist, meeting/outcome selection, raw probability history,
  wallet-data limitation, expanding-window volatility forecasts and deterministic
  research assistant with citations.
- **Events:** dataset meetings and per-outcome histories; no invented wallet data.
- **Scenarios:** paper weights entered as percentages summing to 100; optional
  conditional SPY mean overrides also entered as percentages. Run outputs save
  automatically; VaR/ES are positive loss percentages and USD amounts.
- **Saved research:** immutable run inputs, outputs, assumptions, seed and dataset
  version. Runs made before methodology updates retain their original outputs.

Default meeting is the next upcoming meeting with observations as of the latest
dataset date, or the latest meeting with data when none is upcoming. The default
YES outcome is its most likely non-"No change" outcome; users can select any
outcome. Probabilities prominently show their observation date, not a live quote.
At shipped coverage (prices to 2026-10-07), the default is the September 2026
meeting. Research details and limitations are in [api/README.md](api/README.md).

Scenario residuals come from all overlapping historical H-day SPY returns,
demeaned and shifted by conditional means, scaled to conditional std only with
at least three prior meeting samples. Sparse groups fall back to unconditional
history and are flagged Assumption. ES averages the worst 500 of 10,000 draws.
Volatility floors are fixed by policy before testing: 1% of each expanding
training sample's mean target RV (absolute numerical minimum 1e-12); floor hits
are reported, never hidden. Forecast comparisons use identical test dates.

The interface is a monochrome implementation of the proposal UI concepts.
Charts are horizon, not annualized, quantities; evidence remains limited.
This local research prototype is not an authenticated multi-user deployment.
