# Crypto feasibility — no strategy performance in this screen

**Six families qualify. This coverage-only audit precedes preregistration and
all actual-data strategy performance. Weekly families are dropped.**

Discovery as of **2026-11-25 11:32:12 UTC**; three-year floor
**2023-11-25 11:32:12 UTC**. Raw pages, probes, series catalogues, request
parameters, candles, checkpoints and SQLite remain under
`~/data/polymarket/crypto/`, outside git.

## Counts

Resolved counts describe the identified Gamma recurring production series, not
every crypto question ever listed. Contracts, participant records and wallets in
the final columns refer to the deterministic collected sample, not extrapolated
full-universe trade counts. Exact per-event counts are in `event_coverage.csv`.

| Family | Resolved Gamma events | All-series contracts | Sampled events | Sample contracts (range/event) | Usable | Raw participant records | Distinct sample wallets |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTC above-date | 492 | 4,932 | 120 | 1,200 (1–15) | 120 | 3,481,989 | 168,457 |
| ETH above-date | 493 | 4,907 | 120 | 1,191 (1–14) | 120 | 1,082,848 | 90,382 |
| BTC daily up/down | 619 | 619 | 120 | 120 (1) | 119 | 826,817 | 34,882 |
| ETH daily up/down | 610 | 610 | 120 | 120 (1) | 119 | 375,906 | 19,495 |
| BTC weekly up/down | 3 | 3 | 3 | 3 (1) | 2 — drop | 705 | 179 |
| ETH weekly up/down | 2 | 2 | 2 | 2 (1) | 2 — drop | 409 | 90 |
| BTC hourly up/down | 13,074 | 13,074 | 120 | 120 (1) | 117 | 537,448 | 21,598 |
| ETH hourly up/down | 12,747 | 12,747 | 120 | 120 (1) | 118 | 208,019 | 8,753 |

Totals: **725 sampled event objects / 2,876 contracts / 6,857 exhausted pages /
6,514,141 participant records / 6,376,497 normalized, deduplicated rows**.
The six included families contribute **713 usable family-events**, not 713
independent outcomes. Wallet counts overlap across families and are not additive.
`family_coverage.csv` also gives deduplicated row counts per family.

## Discovery and sampling

Gamma public search identified the regular series; the series catalogue was
exhausted (2,810 default/open catalogue records; closed catalogue empty).
Production IDs: above-price BTC 45 / ETH 42; daily up/down BTC 41 / ETH 40;
weekly BTC 10094 / ETH 10095; hourly BTC 10110+10114 / ETH 10117. New daily
multi-strike series 12043/12044 had no resolved events. PolyV2 soak/test series,
5m/15m, 4h, monthly and hourly multi-strike ladders are outside the requested
production families. Identified series histories were exhausted with Gamma
keyset pagination, using its documented `after_cursor` and explicit date/closed
filters. Pagination was checked for repeats and mismatched filters.

For each family, sort by Gamma endDate then numeric event ID. When N>120 select
indices `floor(i*(N-1)/119)`, i=0..119; otherwise collect all. Endpoints are
included. **120** is a fixed collection-budget cap below the suggested 400,
not a performance or wallet-activity filter. The full inventories, selected
event objects and precise rule are archived in external `inventory.json`,
`discovery.json` and `discovery_config.json`. Actual rule-derived observation
times, rather than Gamma endDate, govern subsequent chronology and eligibility.

The above-price series were historically labelled weekly and include early
weekly/single-strike versions before expanding into daily ladders; these are
the same fixed-date, noon above-price binary family. Contract-count variation
is explicit, and events—not individual ladder strikes—receive equal weight.
The earliest sampled above-price events are January 2025; daily up/down begins
March 2025, hourly May/June 2025. No earlier recurring histories in these
identified series were found in the three-year window. Series discovery and
survivorship remain coverage limitations, not proof that no other market exists.

## Resolution, spot and eligibility

`contract_resolution.csv` records **every sampled contract's** resolution source,
source URL, underlying observation timestamp, cutoff, threshold/reference time,
and separate oracle-settlement proxy. The descriptions are archived in the raw
Gamma inventories. Older Gamma endDate values can be 12:00 UTC even though the
rule specifies noon ET. Those fields are not used as the observation clock.
ET uses `America/New_York`; hourly candle titles specify their start. A noon
1m candle closes one minute later; an explicitly noon-closing candle does not.

Free public Binance klines (`data-api.binance.vision/api/v3/klines`) provide
**17,359 BTCUSDT + 17,191 ETHUSDT contiguous hourly candles**, covering the
trailing windows and observations from December 2024 through November 2026,
plus **7,260 1m snapshot candles across 725 objects** for cutoff spot and prior
up/down references. URL, symbol, interval, start/end and limit are archived per
request. All OHLC values were independently checked positive/finite, with exact
candle durations and contiguous hourly timestamps. No API key or paid source
was used. Feasibility checks availability only; volatility/model performance is
not calculated at this stage.

A usable event has a validated terminal binary contract, reliable rule time,
pre-cutoff YES/Up probability, strict post-cutoff/pre-observation trades on
both sides, aligned minute spot/reference snapshots, 720 contiguous completed
hourly closes in the trailing 30 days, and at least 200 qualified prior-history
wallets (the existing 20-smart-wallet minimum). Daily cutoff is 12h before the
observation; hourly is 30m. Weekly would use half its stated interval. Skill
eligibility here counts records only: no wallet ranking PnL or strategy return
is computed. FOMC/macro plus same-family history must have oracle resolution
and trade times strictly before cutoff.

Gaps/exclusions were fixed before any performance:

- Daily BTC/ETH November 24, 2026 use Chainlink TWAP, not Binance spot: one
  excluded event per daily family.
- Hourly BTC/ETH November 20 and November 25, 2026 also use Chainlink TWAP:
  two excluded events per hourly family. Their source/time are retained, but
  Binance is not silently substituted for a different oracle or TWAP payoff.
- BTC hourly event 25006 (May 23, 2025) has no common eligible binary-entry
  contract at the registered cutoff; it is excluded.
- BTC weekly object 25776 is actually an hourly June 4, 8PM ET contract, despite
  its weekly series assignment. It is mapped but excluded from weekly coverage.
- Remaining weekly counts are only two per asset, well below 60. Both drop.
- No other sampled object has an unmapped resolution rule or unexhausted history.

## Validation and limitations

The existing approved collector and its User-Agent/rate limits were reused.
Every raw page was checked against the event's condition/token set, cursor
continuity, page and participant counts. Normalization validates addresses,
timestamps, sides, finite prices and positive sizes. Cache fingerprints bind
raw metadata, trade histories, summaries/configuration, candles and parsers;
stale caches are rejected. The separate cross-check agreed with the SQLite
build counts, terminal cursors, per-family distinct wallets and source hash.

Participant records are not unique exchange executions; normalization may merge
indistinguishable records, and wallets need not be independent people. Sampled
histories do not establish full-universe trade/wallet totals. Oracle settlement
metadata is a conservative availability proxy, not an audited on-chain timestamp.
Ladders overlap, nearby observation windows overlap, source regimes change, and
free candles do not supply historical order books, fill capacity or fee schedules.

Feasibility tests:

```text
Ran 13 tests in 0.018s

OK
```

```text
Independent feasibility audit passed: 725 exhausted event objects / 6,857 pages / 6,514,141 raw participant records / 6,376,497 normalized deduplicated rows; terminal cursors, family wallet counts and source fingerprint agree.
```

```text
Independent spot archive audit passed: 34,550 contiguous hourly candles; 7,260 minute snapshot candles across 725 event objects; positive finite OHLC and exact candle durations.
```
