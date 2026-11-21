# Macro market feasibility — no strategy performance evaluated

**Four bucket families clear the 15-usable-release screen: headline CPI MoM (19), headline CPI YoY (21), payrolls (23), and unemployment (21). Preregistration and performance evaluation have not begun.**

Gamma discovery as of **2026-11-21 18:26 UTC** searched `inflation`, `CPI`, `jobs added`, `unemployment`, `PCE`, and `GDP`, exhausting public-search pagination. Only closed event candidates within the three-year window were collected. This is search-based discovery, not proof that every historical macro market was indexed. All raw Gamma responses, official-source page text, compressed trade pages, summaries, and SQLite databases remain under `~/data/polymarket/macro/`.

## Coverage

| Family | Gamma event objects | Official distinct releases | Usable releases | Terminal markets/release, min/median/max | Raw participant rows | Distinct raw wallets | Decision |
|---|---:|---:|---:|---|---:|---:|---|
| Headline CPI MoM | 21 | 20 | 19 | 3 / 5 / 9 | 173,861 | 11,708 | Include |
| Headline CPI YoY | 24 | 21 | 21 | 4 / 5 / 18 | 401,695 | 24,338 | Include |
| Core CPI MoM | 5 | 5 | 5 | 7 / 7 / 10 | 22,752 | 2,306 | Drop: fewer than 15 |
| Core CPI YoY | 6 | 6 | 6 | 10 / 10 / 10 | 22,670 | 3,232 | Drop: fewer than 15 |
| Nonfarm payrolls | 24 | 24 | 23 | 0 / 6 / 8 | 109,366 | 8,480 | Include |
| Unemployment | 22 | 22 | 21 | 0 / 6 / 9 | 84,407 | 7,512 | Include |
| Core PCE, MoM and YoY combined for screening | 8 | 4 | 4 | 14 / 14 / 14 | 22,119 | 1,955 | Drop: fewer than 15 even combined |
| GDP, advance/initial release | 8 | 7 | 7 | 6 / 7 / 12 | 133,013 | 12,525 | Drop: fewer than 15 |

Ten older single-threshold inflation event objects (3,373 rows, 800 distinct wallets) were collected during broad discovery but excluded from the bucket families. Wallet counts are distinct **within** each family, not additive across families. Event-wallet count sums are separately labeled in `family_coverage.csv`; they are not distinct family wallet counts. Market ranges refer to officially mapped releases, including unusable ones; canceled CPI releases have no official release row.

The collection exhausted **128 event objects / 1,041 pages / 973,256 participant records**. These are participant records, not independent trades or independent observations. Duplicate Gamma objects for the same family/reference period count as one release. Higher/lower CPI bracket event objects are grouped at the release level, as are GDP duplicates and PCE MoM/YoY objects. Individual market IDs and deduplication keys prevent duplicated participant records from entering the normalized cache twice.

## Eligibility and timing

- An official BLS/BEA reference-period mapping is required. ET timestamps are converted with `America/New_York`, respecting daylight saving; Gamma `endDate` is **not** the release timestamp.
- A valid market must be closed, binary Yes/No, terminal within 0.001 of its settlement, and have a conservative Gamma resolution timestamp no earlier than the official release. Resolution timestamps remain metadata proxies, not verified on-chain finalization.
- At **both** t−3d and t−1d there must be at least one valid market with a pre-cutoff YES price and strictly post-cutoff, pre-release entries for **both** YES and NO. Entry eligibility is per market/horizon; not all markets necessarily qualify.
- Both cutoffs must have at least 200 qualifying wallets, giving a top-decile smart set of at least 20. Qualification combines prior-resolved **same-family** macro markets and FOMC, requires at least five pre-cutoff records and positive gross notional. Feasibility counts qualification only: it does not rank wallets or evaluate strategies. The sweep uses `max(trade timestamp, resolution timestamp) < cutoff` and is tested against the direct SQL skill query.
- Raw page count, row count, cursor continuity and final exhaustion are checked before normalization; records outside the requested Gamma event are rejected. Text fingerprints reuse the existing CRLF-normalized digest; binary pages remain byte-exact.

## Gaps and constraints for preregistration

1. **October 2025 CPI was canceled.** Gamma annual/monthly events `67280` and `67929` have no official release mapping and are excluded. September 2025 CPI maps to the delayed October 24 release, not Gamma's originally scheduled date.
2. September 2025 payroll/unemployment event objects `42245` and `42244` have no terminal markets resolving after the delayed official release. They cannot represent that official release and are excluded; their raw records remain in coverage totals only.
3. December 2024 headline CPI MoM has no eligible t−3d market, although t−1d is covered; it fails the common-two-cutoff screen.
4. Recurring headline CPI buckets start in late 2024. MoM lacks April 2025 and January/February 2026; YoY lacks November 2024 and February 2026. Other months absent from discovery are missing, not fabricated zero-flow observations.
5. Payrolls lack March 2026; unemployment lacks February 2026. Both lack October 2025 event objects. Do not infer a scheduled release where none was observed or where the official schedule differs.
6. Core CPI only has May–October 2026 observations (MoM also lacks June). PCE has only four distinct 2026 release dates; GDP only seven quarters. Splitting PCE more finely cannot rescue the sample-size gate.
7. **The SPY CSV ends October 7, 2026.** Later release-day closes are unavailable; strategy f must leave those windows missing rather than substitute prices. This constraint needs an explicit preregistered availability rule before evaluation.
8. Headline CPI MoM/YoY share release dates; payroll/unemployment also share release dates. There are **84 usable family×release observations, not 84 independent macro dates**. The pooled test must cluster co-released families by official release timestamp/date and avoid training on another family's held-out event. A global holdout firewall should exclude all families' holdout IDs from every development skill/calibration input, including the FOMC-plus-same-family rule if future development cutoffs could overlap earlier holdouts.
9. Official BLS pages returned HTTP 403 through Python. The archived schedule text was fetched with the web content tool and parsed from monthly calendar pages; official source URLs are recorded per release. Reproduction requires those externally archived page-text files, not only the repository.
10. **Do not normalize every grouped market into one categorical probability vector.** January and March 2026 headline CPI YoY combine original and extra-bracket Gamma events and each has two YES-settled markets. They are legitimate overlapping binary contracts, not one mutually exclusive partition. They can support direct PM strategies with release-clustered inference, but entropy sizing needs a preregistered coherent partition or an explicitly binary-entropy aggregation. PCE and duplicate GDP also exhibit multiple winners, though those families fail the event-count screen anyway.
11. SPY t−1d entries can coincide with the release-day exit when the intervening close is unavailable (for example a holiday). Preregister how such zero-duration windows are handled, rather than silently treating them as invested event windows.

## Derived artifacts

- `event_inventory.csv`: one row per collected Gamma candidate, original title/end date, official mapping, valid market count, raw rows/wallets/pages and trade range.
- `release_coverage.csv`: one row per officially mapped family/reference, source URL, UTC release timestamp, per-cutoff entry and cohort availability.
- `family_coverage.csv`: event/release totals and inclusion screen.
- `raw_coverage.csv`: exact family-distinct wallets and participant counts, including excluded candidates.

No strategy returns, development metrics, rankings, holdout metrics, or pass/fail results have been computed. The holdouts are still unassigned; preregistration must be committed before performance work.
