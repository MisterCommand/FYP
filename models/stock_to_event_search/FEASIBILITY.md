# Round-six stock-to-event feasibility (no performance)

Reuse only the FOMC #8/#11 and macro #12 archives. No market collection and no ETH/crypto or forward-test data access. External assets and the feature panel live in `~/data/polymarket/stock_to_event_search/`, outside Git.

| Family | Archived releases | Usable releases | Development / holdout | Contracts | H1 daily windows | Missing H1 windows | H3 opportunities | t−1 quotes / missing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FOMC | 28 | 21 | 14 / 7 | 113 | 6,053 | 423 | 6,198 | 87 / 26 |
| CPI, pooled headline MoM + YoY | 22 | 22 | 15 / 7 | 297 | 5,128 | 1,229 | 5,597 | 281 / 16 |
| Payrolls | 23 | 23 | 16 / 7 | 140 | 1,729 | 811 | 2,026 | 137 / 3 |
| Unemployment | 21 | 21 | 14 / 7 | 142 | 1,798 | 1,062 | 2,185 | 131 / 11 |

**87 usable family-events at 67 distinct release timestamps**, 692 archived contracts, 14,708 fresh H1 contract windows and 636 t−1 contract snapshots. Of 18,233 candidate daily windows, **3,525** lack a trade in one or both adjacent PM intervals and are skipped for H1, never forward-filled. H3 instead requires only a fresh baseline at the current close, not future target availability: 16,006 opportunities, with **2,227** missing baseline days skipped. Of these opportunities, 2/28/0/2 in FOMC/CPI/payrolls/unemployment lack at least one possible entry side before release; a chosen missing side stays cash. Contracts without a fresh t−1 quote are separately counted above. These are availability counts, not fitted coefficients, ROI, accuracy or significance results.

The seven early FOMC meetings with no retained usable windows are excluded, rather than fabricated. Usability requires any daily or t−1 snapshot; hypothesis-specific informative counts can subsequently be smaller. CPI MoM and YoY contracts at the same release timestamp form one event before splitting. Binary contracts are retained separately; no assumption that overlapping contracts form a partition.

## Fixed chronological ranges

| Family | Development releases | Holdout releases |
|---|---|---|
| FOMC | 2023-12-13–2025-12-10 | 2026-01-28–2026-10-28 |
| CPI | 2024-12-11–2026-04-10 | 2026-05-12–2026-11-10 |
| Payrolls | 2024-10-04–2026-03-06 | 2026-05-08–2026-11-06 |
| Unemployment | 2024-12-06–2026-04-03 | 2026-05-08–2026-11-06 |

`registration.json` will pin every event, not just these ranges. The latest `ceil(.30 × usable_events)` releases are held out (minimum five; all four families have seven).

## Asset source and coverage

| Series | Public source | Available dates | Observations | Primary use |
|---|---|---|---:|---|
| SPY | Yahoo Finance chart, `SPY?range=5y&interval=1d` | 2021-11-26–2026-11-25 | 1,255 daily closes | Close-to-close price return |
| SHY | Yahoo Finance chart, `SHY?range=5y&interval=1d` | 2021-11-26–2026-11-25 | 1,255 daily closes | Sign-flipped close-to-close price return |
| DGS2 | FRED `fredgraph.csv?id=DGS2&cosd=2022-01-01&coed=2026-11-25` | 2022-01-03–2026-11-24 | 1,223 nonmissing daily yields | Coverage reference, not a third predictor |

SPY and SHY calendars match: 1,254 return windows, covering every retained event. Raw responses and URLs are retained and will be hash-pinned. Closes after 2026-11-25 are excluded; unadjusted closes avoid backward corporate-action revisions but include ex-dividend price effects. These are price returns, not total returns.

The Federal Reserve H.15 page (`https://www.federalreserve.gov/releases/h15/`, archived locally) states **“The release is posted daily Monday through Friday at 4:15pm.”** A same-date DGS2 observation is therefore not observable at the required **16:00 America/New_York** close (13:00 on early-close sessions). Use the explicitly permitted **inverse SHY return**, not future-published DGS2, as the rate-move proxy. SHY is not a pure 2-year yield instrument: duration, carry, dividends and other maturity exposures are limitations. No DGS2 alternative, extra asset or hourly test is added; no whole-sample hourly source has been established.

## Archive provenance

- FOMC: `wallet_backtest_cache/trades.sqlite3`, the existing settlement CSV, and the complete/exhausted October 2026 `strategy_search/fresh` archive. Fresh metadata/cache fingerprint agrees.
- Macro: `macro/trades.sqlite3`, discovery, BLS/BEA source schedules and registered #12 references. The archived build fingerprint was compared to `macro_coverage.raw_fingerprint(...)`: **matches**. No cache rebuild occurred.
- FOMC official decisions use 14:00 New York time on the registered decision dates; macro timestamps and post-release settlement validation reuse `macro_event_search.coverage.load_metadata`.
- Daily PM boundaries are the actual session close: 16:00 New York time normally, 13:00 on open July 3/December 24 sessions and the Friday after Thanksgiving. The available Yahoo sessions supply the holiday calendar; NYSE's published hours/calendar page is archived with the assets. These rules cover the bounded 2021–2026 asset sample. Weekend/holiday intervals run to the next session. Every forecast cutoff precedes release; H1's next-close target may reflect the release, using actual trades up to settlement rather than replacing missing trades with 0/1. H3 entries must precede release and do not depend on the existence of a future H1 endpoint. H2 uses release minus 24 hours and the last fully observable asset window, with a PM trade in the preceding 24 hours.

No stock-to-event performance has been calculated in this feasibility stage.
