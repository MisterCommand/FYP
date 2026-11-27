# Round-seven options-to-event feasibility

No option-predictor performance was computed for this feasibility audit. The user
approved the timing adjustment below before implementation or preregistration.

## Base and fixed population

Fetched `origin/main` at `2973fe5d01cfea29d34c0fc3ac4de550e016b50d`
(PR #15's squash merge). Its round-six study matches the reviewed branch bytes.
Branch: `devin/1795744531-options-to-event-search`.

The existing round-six population and exact split, to be retained:

| Family | Archived | Usable | Development | Holdout | Contracts |
| --- | ---: | ---: | ---: | ---: | ---: |
| FOMC | 28 | 21 | 14 | 7 | 113 |
| CPI pooled MoM/YoY | 22 | 22 | 15 | 7 | 297 |
| Payrolls | 23 | 23 | 16 | 7 | 140 |
| Unemployment | 21 | 21 | 14 | 7 | 142 |

The rebuilt 16:15/13:15 panel independently reproduces the exact original event
lists and split; `register_study.py feasibility` rejects any mismatch.

| Family | H1 windows | Missing H1 windows | H2 cutoffs | H3 opportunities | Missing fresh H3 baseline |
| --- | ---: | ---: | ---: | ---: | ---: |
| FOMC | 6,059 | 417 | 87 | 6,201 | 275 |
| CPI | 5,131 | 1,233 | 281 | 5,601 | 763 |
| Payrolls | 1,735 | 807 | 137 | 2,030 | 512 |
| Unemployment | 1,812 | 1,048 | 131 | 2,192 | 668 |

There are 87 usable family-events at 67 distinct release timestamps. H2 skips
26/16/3/11 missing fresh contract cutoffs, respectively. H3 uses current-only
eligibility independently of a future H1 endpoint. Quote counts differ slightly
from round six because the approved boundary moves by 15 minutes, not because
events or missingness rules were selected by performance.

## Price coverage (no fitting or scoring)

Public raw downloads are outside Git in
`~/data/polymarket/options_to_event_search/`. Download setup explicitly creates
the parent directory before writing. Sources: Yahoo chart endpoints for `^VIX`,
`^VIX9D`, `^MOVE` (`range=5y&interval=1d`) and CBOE's public
`https://cdn.cboe.com/api/global/us_indices/daily_prices/{VIX,VIX9D}_History.csv`.

| Input | Round-six calendar closes present (2021-11-26 to 2026-11-25) | Actual feature-window dates present (2023-11-21 to 2026-11-09) |
| --- | ---: | ---: |
| VIX | 1,255 / 1,255 | 723 / 723 |
| VIX9D | 1,255 / 1,255 | 723 / 723 |
| MOVE | 1,246 / 1,255 | 718 / 723 |

Drop MOVE under the requested full-coverage rule: missing required dates are
2024-10-14, 2024-11-11, 2025-10-13, 2025-11-11 and 2026-10-12. This leaves
24 potential hypotheses (4 families x 2 predictors x 3 hypotheses).

CBOE VIX9D closes match Yahoo on all 723 required dates. VIX matches on 722;
2026-02-06 differs. Prefer the official CBOE series for both mandatory indices
before registering or evaluating anything.

## Approved timing adjustment

Round six's `archive.close_stamp` uses 16:00 ET (13:00 on early closes).
However, CBOE calculates VIX through 15:15 CT / 16:15 ET, and Yahoo's VIX
metadata also identifies 16:15 ET as the regular-session end. The selected
daily closing values cannot safely be treated as known at the earlier round-six
PM snapshot. The ratio predictor also depends on this VIX close.

Evidence:

- `https://www.cboe.com/tradable_products/vix/vix_futures/specifications`:
  "The VIX Index is calculated ... between 8:30 a.m. CT and 3:15 p.m. CT."
- `https://datashop.cboe.com/main-channel-end-of-day-summary` states that the
  closing time is index-specific, not universally 16:00 ET.
- Yahoo/CBOE closing-value comparisons above checked whether the Yahoo series
  might supply a different equity-close snapshot; it essentially matches the
  official closing series instead. Daily Yahoo bar timestamps are not evidence
  that a completed daily bar was available at its start.

The user approved moving the daily predictor/PM clock to the option-index close:
16:15 ET normally, 13:15 on sample early-close sessions. H2 keeps its original
release-minus-24-hours decision and uses only an already completed index window.
Use official CBOE data for both indices and exclude MOVE. No lag, cutoff or
source alternatives will be searched. Both predictors use fixed 1% log-change
units. All inference, gates, placebo encoding and lock behavior mirror round six.

No ETH/crypto data or forward-test files/worktree were read or modified.
