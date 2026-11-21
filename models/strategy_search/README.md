# Preregistered strategy search

See `PREREGISTRATION.md` and `registration.json` for the committed protocol,
and `RESULTS.md` / `results.csv` for the results. The historical holdout was
previously analyzed for wallet tilts only; g is descriptive, not confirmatory.

## Reproduction and the one-time lock

Python dependencies are reused from `models/wallet_backtest/requirements.txt`.
Run from the repository root with that environment activated. Defaults use
`~/data/polymarket/`; `--data-root` overrides the raw-data location.

The existing `wallet_backtest_cache/trades.sqlite3` and wallet-backtest panel /
settlements must already exist. The October collector delegates to the same
external `feasibility/collect_meetings.py` used for the historical data. It uses
the approved research User-Agent and request throttling. Collection must exhaust
before fresh data are eligible; raw pages and all SQLite caches stay outside Git.

```sh
python models/strategy_search/collect_fresh.py
python models/strategy_search/search.py develop
python models/strategy_search/search.py holdout
```

These are the original execution commands, **not instructions to rerun a
completed holdout**. Development creates an immutable screening manifest at
`~/data/polymarket/strategy_search/development.json`. Holdout checks hashes of the
code, committed registration and data, then exclusively claims
`holdout_lock.json` before evaluation. Re-entry is refused even after failure.
Do not delete locks, overwrite manifests, recollect inputs after freezing, or
use another work directory to bypass this study's one-run rule. A failed locked
run requires explicit review, not an automatic retry. Non-advanced strategies
have blank holdout cells rather than computed-but-suppressed results.

Derived `*_observations.csv` contain sleeve/window returns. `*_execution.csv`
audit cutoff and first-post-cutoff entry times; `study_manifest.csv` records
hashes and frozen coefficients. The external development manifest also records
input hashes, full development metrics and the seeded null-shuffle diagnostic.
The external `holdout_results.json` and retained lock record the single run.

```sh
python -m unittest discover -s models/strategy_search -p 'test_*.py' -v
python -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v
```

Those tests use synthetic data and do not consume or evaluate the actual holdout.
