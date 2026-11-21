# Macro event strategy search

The historical [FEASIBILITY.md](FEASIBILITY.md) snapshot was committed first; [PREREGISTRATION.md](PREREGISTRATION.md) and `registration.json` were committed separately before performance. See [RESULTS.md](RESULTS.md) and `results.csv` for the completed fixed search. December 2024 headline MoM is retained at t−1d only, as preregistered after the original feasibility snapshot.

```sh
PYTHON=~/data/polymarket/wallet_backtest_env/bin/python
$PYTHON models/macro_event_search/feasibility.py discover --data-root ~/data/polymarket/macro
$PYTHON models/macro_event_search/feasibility.py collect --data-root ~/data/polymarket/macro
$PYTHON models/macro_event_search/coverage.py ~/data/polymarket/macro
$PYTHON models/macro_event_search/run_search.py develop --data-root ~/data/polymarket/macro
$PYTHON models/macro_event_search/run_search.py holdout --data-root ~/data/polymarket/macro
$PYTHON -m unittest discover -s models/macro_event_search -p 'test_*.py' -v
```

The collector dynamically reuses the existing external `~/data/polymarket/feasibility/collect_meetings.py` and its `collect_pilot.fetch`: User-Agent `EventLens-research/0.1 (HKUST FYP)`, shared 0.21-second request spacing, retry/backoff on 429/5xx, and four workers. It needs the original external collector and its dependencies. Raw data and caches must stay outside git. Discovery can use cached Gamma responses; collection resumes from cursor-checked compressed pages.

Release mapping additionally requires external `bls_batch_*.md` and `bea_schedules.md`, the archived official BLS monthly calendar and BEA schedule text, with `## Page ...` and `URL: ...` provenance headers. Python BLS requests were forbidden; these were obtained through the web content tool. `release_coverage.csv` records the official URL used for every mapped release.

The macro cache fingerprints raw inputs and mapping/build code. It refuses stale or incomplete caches rather than silently rebuilding them. Preserve the old cache separately and rebuild only after explaining any input/code change; never remove future development manifests or holdout locks to bypass a failed check.

The last two commands are **single-use stages**, not commands to rerun on a completed study. External state is in `~/data/polymarket/macro/strategy_search/`: development JSON, full derived observations, holdout lock and results. The committed `development_manifest.csv` binds the pre-holdout development JSON hash; `development_results.csv` and `development_execution.csv` are small development audit artifacts. Holdout execution marks and `study_manifest.csv` bind the completed result to the lock. Source hashes normalize CRLF for text and remain byte-exact for binary caches.

Wallet skill reuses both the baseline FOMC cache and the available exhausted October 2026 fresh-FOMC cache from the earlier strategy search, with strict prior-resolution filtering. Macro skill is same-family only. During development all macro holdout IDs are excluded from skill/calibration sources. During holdout earlier resolved holdout markets can update wallet skill, but calibration maps remain frozen from development. Only gate-passing hypotheses have holdout returns evaluated.

## Tests

```sh
$PYTHON -m unittest discover -s models/macro_event_search -p 'test_*.py' -v
$PYTHON -m unittest discover -s models/strategy_search -p 'test_*.py' -v
$PYTHON -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v
```
