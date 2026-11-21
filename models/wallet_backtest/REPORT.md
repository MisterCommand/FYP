# Frozen panel build results

Built on branch `devin/1795232715-wallet-backtest`, based on `origin/main`
(`f223a56`, which contains `app/api/wallet.py`). No push requested or performed.

## Counts and availability

- **324 rows**, 108 outcome markets, 27 meetings, three cutoffs per meeting.
- **14 meetings / 42 meeting-cutoff cohorts** have a usable smart set, starting
  September 2024. The other 13 meetings / 39 cohorts are unavailable.
- 6,257,537 raw participant records → **6,218,003 deduplicated trades**;
  39,534 duplicate records removed.
- All 108 CSV settlement labels passed the Gamma terminal-price cross-check.
  No cutoff is missing a market probability.
- The four committed derived CSVs total **118,508 bytes**. Raw pages and the
  approximately 1.7 GB SQLite trade cache remain outside the repository.

Rows at t−7 / t−3 / t−1 and selected cohort size (identical at all three cutoffs
within each meeting in this build):

| Meeting | Rows t−7 | Rows t−3 | Rows t−1 | Smart wallets per cutoff |
|---|---:|---:|---:|---:|
| 2023-02 | 4 | 4 | 4 | unavailable |
| 2023-03 | 4 | 4 | 4 | unavailable |
| 2023-05 | 4 | 4 | 4 | unavailable |
| 2023-06 | 4 | 4 | 4 | unavailable |
| 2023-07 | 3 | 3 | 3 | unavailable |
| 2023-09 | 2 | 2 | 2 | unavailable |
| 2023-11 | 2 | 2 | 2 | unavailable |
| 2023-12 | 2 | 2 | 2 | unavailable |
| 2024-01 | 3 | 3 | 3 | unavailable |
| 2024-03 | 4 | 4 | 4 | unavailable |
| 2024-05 | 4 | 4 | 4 | unavailable |
| 2024-06 | 4 | 4 | 4 | unavailable |
| 2024-07 | 4 | 4 | 4 | unavailable |
| 2024-09 | 4 | 4 | 4 | 32 |
| 2024-11 | 6 | 6 | 6 | 230 |
| 2024-12 | 6 | 6 | 6 | 937 |
| 2025-01 | 5 | 5 | 5 | 1,467 |
| 2025-07 | 4 | 4 | 4 | 2,490 |
| 2025-09 | 4 | 4 | 4 | 2,867 |
| 2025-10 | 4 | 4 | 4 | 3,507 |
| 2025-12 | 4 | 4 | 4 | 4,415 |
| 2026-01 | 4 | 4 | 4 | 5,735 |
| 2026-03 | 4 | 4 | 4 | 7,351 |
| 2026-04 | 4 | 4 | 4 | 9,044 |
| 2026-06 | 5 | 5 | 5 | 10,226 |
| 2026-07 | 5 | 5 | 5 | 10,857 |
| 2026-09 | 5 | 5 | 5 | 11,643 |

**Smart-set size distribution:** each of the 14 positive sizes above occurs at
exactly three cutoffs; 39 cutoffs have no cohort (`n_smart=0`). Among the 42 usable
cutoffs: minimum 32, median 3,961, maximum 11,643. Selection is the floor of the
top decile; it is not padded up to 20. Placebo selection uses seed 42 and the
same-size rule. Selected counts do not imply all selected wallets trade during
the target window.

## Example panel rows

All examples are the **No change** outcome at t−3; rounded for display only.
Blank flow is unavailable, not zero.

| Meeting | Market | p_market | Smart flow | Placebo flow | All flow | Smart trades / active wallets | n_smart | Realized |
|---|---|---:|---:|---:|---:|---|---:|---:|
| 2023-02 | 248206 | 0.0100 | — | — | — | — | 0 | 0 |
| 2024-09 | 504071 | 0.0160 | -0.646529 | -0.039947 | -0.814734 | 217 / 9 | 32 | 0 |
| 2026-06 | 906974 | 0.9955 | 0.658972 | 0.849638 | 0.481773 | 2,272 / 106 | 10,226 | 1 |

## Checks

`python3 -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v`:

```text
Ran 12 tests in 0.011s

OK
```

Tests cover all four YES/NO × BUY/SELL PnL cases, shrinkage and minimum history,
unresolved/current meetings, whole-meeting resolution, trades exactly at and
after the cutoff, inclusive signal-window start, future-trade invariance, seeded
cohort selection, empty/unavailable/zero-activity cases, deduplication, invalid
trades, strict timestamps, day-only resolution bounds, Gamma rounding/conflicts,
and inclusive market-quote cutoff selection.

Full build:

```text
Panel: 324 rows; trades: 6,257,537 raw -> 6,218,003 deduplicated
```

An independent CSV audit compared every panel quote to the original probability
CSV and every cutoff to the app's calendar, and checked uniqueness, bounds,
cohort counts and missingness:

```text
Panel audit passed: 324 unique rows / 108 markets / 27 meetings; exact UTC cutoffs and latest eligible probabilities; cohort counts, missingness and signal bounds valid.
```

## Qualifications

This establishes a reproducible retrospective panel, **not** proof of added SPY
portfolio value or a calibrated probability adjustment. See README for the
participant-level deduplication ambiguity, actual-token-notional convention,
strict skill/signal cutoffs and coverage definitions. In particular, Gamma
resolution timestamps are conservative metadata proxies, not independently
verified finalization times; contemporaneous API availability is unverified.
Seven empty early-2023 histories and retention-clipped December 2023 history
limit historical skill. No missing early trades were synthesized or backfilled
from a later-active wallet universe.
