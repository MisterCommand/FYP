# Crypto event search (research round 4)

Feasibility precedes preregistration and all performance calculations. Raw Gamma
pages, participant histories, candle responses, databases and execution locks live
outside git at `~/data/polymarket/crypto/`.

## Feasibility reproduction

From the repository root, using the existing wallet-backtest environment:

```sh
PY=~/data/polymarket/wallet_backtest_env/bin/python
$PY models/crypto_event_search/feasibility.py discover
$PY models/crypto_event_search/feasibility.py collect
$PY models/crypto_event_search/spots.py
$PY models/crypto_event_search/audit.py
$PY -m unittest discover -s models/crypto_event_search -p 'test_*.py' -v
```

Discovery freezes an as-of timestamp, exhausts Gamma series with keyset pagination,
and takes at most 120 events per family by evenly spaced chronological ranks,
including both endpoints. This is deliberately below the suggested 400-event cap.
The family catalogue was identified using Gamma public search and series metadata;
the raw probes and catalogue are retained externally. Discovery asserts that the
series, closed and date filters are honored and that pagination does not repeat.
Gamma offset pagination is limited; keyset uses the documented `after_cursor`.
Pages use limit 50 because larger Gamma pages require compression negotiation.

The existing external `feasibility/collect_meetings.py` collector is reused, including
its `EventLens-research/0.1 (HKUST FYP)` User-Agent, shared 0.21-second request
spacing, four workers, 429/5xx retries, compressed pages and checkpoints. Histories
must exhaust with a terminal null cursor. The collector requests both participants
(`taker_only=false`) and its existing 0.01-token floor. Counts are **participant
records**, not independently identified exchange executions. The cache validates
condition/token mapping, amounts, cursor chains, counts and deduplicated rows.

Free Binance `data-api.binance.vision/api/v3/klines` supplies 1h trailing-history
candles and 1m cutoff/strike snapshots for BTCUSDT and ETHUSDT. Every response
archives its URL and request parameters. Daily observation times come from the
resolution description and timezone-aware ET title date, not Gamma's frequently
date-only/incorrect end time. A noon candle closes a minute after its start; a
candle explicitly *closing at* noon is different. Hourly titles specify the candle
start; observation is at its end. Oracle settlement timestamps are separately
retained as conservative label-availability proxies.

Chainlink TWAP rules are recorded but excluded from the common aligned-spot
sample: free Binance candles are not the specified Chainlink series. An hourly
object incorrectly assigned to a weekly Gamma series is also excluded. These are
coverage exclusions, not performance-dependent decisions. A family needs at least
60 usable events, with prior market probability, both strict post-cutoff entry
sides, 30 days of contiguous hourly spot coverage, minute snapshots, and at least
200 qualifying prior-history wallets. Feasibility only counts eligible wallets;
it does not calculate strategy performance.

Source fingerprints bind the external cache to selected Gamma metadata, every
raw page, collection configuration/summary, candle response and parser code.
Changed sources are rejected, never silently reused. Shared dependencies are the
unchanged strategy-search/wallet-backtest implementations and existing FOMC/macro
caches. No frontend or application behavior is changed.

## Registered search stages

Only after committing feasibility, generate `registration.json` with
`$PY models/crypto_event_search/register.py` and commit it with
`PREREGISTRATION.md` before any actual-data performance calculation. The runner
pins that commit. Then:

```sh
$PY models/crypto_event_search/run_search.py develop
# Commit implementation and the development CSV/manifest freeze before holdout.
$PY models/crypto_event_search/run_search.py holdout
```

Development and holdout artifacts/locks live in the external `crypto/study/`
directory; the small derived summaries and execution audits are committed here.
Re-running either completed stage is rejected. Do not delete locks or create a
fresh data root to retry this holdout. Reproduction of the locked study needs its
archived raw data; a new discovery date produces a different research population.

The primary metric, strict cutoff/entry/candle rules, seven fixed strategies,
single pooled test, development gate and round-four Holm alpha are specified in
the committed registration. Unadvanced strategy holdout returns are not computed.

The full requested verification comprises this new suite and the existing
`macro_event_search`, `strategy_search`, and `wallet_backtest` unittest suites,
each with `-m unittest discover -s models/<directory> -p 'test_*.py' -v`.
