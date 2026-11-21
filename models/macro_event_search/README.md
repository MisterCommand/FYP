# Macro event strategy search

Current stage: **feasibility only**. See [FEASIBILITY.md](FEASIBILITY.md) and the coverage CSVs. Four families pass the event-count screen; preregistration and evaluation remain pending.

```sh
PYTHON=~/data/polymarket/wallet_backtest_env/bin/python
$PYTHON models/macro_event_search/feasibility.py discover --data-root ~/data/polymarket/macro
$PYTHON models/macro_event_search/feasibility.py collect --data-root ~/data/polymarket/macro
$PYTHON models/macro_event_search/coverage.py ~/data/polymarket/macro
$PYTHON -m unittest discover -s models/macro_event_search -p 'test_*.py' -v
```

The collector dynamically reuses the existing external `~/data/polymarket/feasibility/collect_meetings.py` and its `collect_pilot.fetch`: User-Agent `EventLens-research/0.1 (HKUST FYP)`, shared 0.21-second request spacing, retry/backoff on 429/5xx, and four workers. It needs the original external collector and its dependencies. Raw data and caches must stay outside git. Discovery can use cached Gamma responses; collection resumes from cursor-checked compressed pages.

Release mapping additionally requires external `bls_batch_*.md` and `bea_schedules.md`, the archived official BLS monthly calendar and BEA schedule text, with `## Page ...` and `URL: ...` provenance headers. Python BLS requests were forbidden; these were obtained through the web content tool. `release_coverage.csv` records the official URL used for every mapped release.

The macro cache fingerprints raw inputs and mapping/build code. It refuses stale or incomplete caches rather than silently rebuilding them. Preserve the old cache separately and rebuild only after explaining any input/code change; never remove future development manifests or holdout locks to bypass a failed check.
