# Round eight: cross-market macro feasibility

This protocol is written **before the coverage audit and before any performance
calculation**. It reuses only the archived FOMC and macro markets. It does not
read crypto or forward-test data. Base: main after PR #16,
`783d1d3c2ed04915ae29e9a11da3e27715af7ebf`.

## Fixed inputs and timing

- Targets: the exact round-six payrolls (23) and unemployment (21) event lists
  and chronological development/holdout assignments (16/7 and 14/7).
- Optional PCE, GDP and core CPI must first have at least 15 distinct archived,
  officially mapped releases. Count distinct release timestamps when pooling
  core CPI MoM/YoY. This is an upper bound before testing quote eligibility;
  fewer than 15 means exclusion without any performance calculation.
- Sources: the FOMC archives used in round six, and the headline CPI MoM/YoY
  contracts in its pooled CPI population. Official announcement timestamps,
  not Gamma end dates, determine whether a source event is still in the future.
- Commodity candidates are **USO, GLD and CPER**, unadjusted daily ETF closes
  from `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5y&interval=1d`.
  No CL/HG futures rolls, adjusted-close substitution, alternative assets or
  hourly search. Intersect with the frozen round-six exchange-session calendar
  (2021-11-26 through 2026-11-25); missing closes are not filled.
- The candidate daily predictor window is `[previous session close, current
  session close]`. ETF closes are 16:00 America/New_York, or 13:00 on the
  calendar's early closes. The daily target decision is **five minutes later**
  (16:05/13:05). Thus predictor endpoints strictly precede decisions, rather
  than using the eventual commodity close at an earlier PM snapshot. H1's PM
  endpoint is the following session's decision; H3 enters strictly after the
  decision and before official release. H2 retains official release minus
  24 hours and uses only the latest completed predictor window whose end is
  strictly before that cutoff (normally the preceding session).
- At each window endpoint a Fed/CPI quote must be an actual normalized-YES
  participant print in `(previous session close, endpoint]`, not a stale
  carried-forward quote or a settlement value. Both endpoints must reference
  the **same contract and same source release**. Source release must be
  strictly later than the target decision. Source contracts resolving before
  the decision are not eligible. Deterministic quote ties use dedup-key order.
- H1 requires fresh target prints in both decision intervals. H2 requires a
  target print strictly within the preceding 24h. H3 requires only a current
  fresh target print, not an H1 future print. Actual entry availability can
  only reduce H3's coverage upper bound.

## Coverage-first stopping rule

First compute a deliberately **optimistic upper bound**: accept any archived
future Fed contract and any archived future headline CPI contract with fresh
quotes at both endpoints, even allowing every available future release instead
of committing to a particular source maturity. This can only overstate coverage
for a nearest-release probability or expected-path representation. Commodity
prices are provisionally assumed perfect in this screen. Record both the
joint availability and each missing source at every target t-minus-one-day
cutoff, and counts for daily H1/H3 opportunities. No returns, probability
changes, labels, ROI, Brier scores, regressions or p-values are computed.

The minimum for proceeding is **at least ten development and five holdout
source-covered events for at least one requested hypothesis in a target
family**, using the unchanged event split. This weak feasibility threshold is
not a power claim. The three prior-resolved-event training requirement would
further reduce informative coverage. If neither mandatory family clears even
this optimistic bound for any H1/H2/H3, stop: a commodity download, source
representation choice, preregistration and performance run cannot rescue it.
Do not relax freshness, substitute resolved source markets, use future quotes,
or silently test commodity-only as the answer to the combined-market question.

If the upper bound passes, audit actual commodity coverage and independently
document exchange closing-time evidence before preregistration. Fix the exact
Fed/CPI probability representation then, using availability only. The planned
confirmatory family is H1/H2/H3 for combined predictors plus one commodity-only
group ablation on the same complete-case population: **12 hypotheses** if only
the two mandatory families qualify. This is a design proposal, **not a
preregistration**. Final hypotheses, sources, code and data hashes must be
committed and pushed before any performance. Development gate is one-sided
p<.10, holdout one-sided Holm p<.01; nonadvanced holdout performance stays empty.

## Specific representation, fixed before the second-stage audit

The optimistic screen passes (daily upper bound 13/7 development/holdout
events in both families; H2 12/6). Optional-release upper bounds are PCE 4,
GDP 7, and pooled core CPI 6: all three optional families are dropped.

The actual Fed input is the one-session change in **P(no change)** for the
nearest future archived FOMC meeting. The CPI input is the one-session change
in the probability of the **highest-threshold upper-tail headline YoY CPI
bucket** for the nearest future archived headline-YoY release. Select the
largest numerical threshold among labels beginning with `>=`, `≥`, or `>`;
break any duplicate threshold tie by the smallest numerical market ID. This
does not sum overlapping CPI buckets or pretend they form a categorical
distribution. Its threshold can change between releases, a limitation to
report. Selection depends on metadata, never current/future prices or target
outcomes. Select the nearest source release before checking quote coverage:
do not switch to another meeting/release/contract to fill a gap.

For both sources require fresh actual prints at both fixed session endpoints
and an official source release strictly after the target decision. The three
commodity features are one-session log returns in USO, GLD and CPER. Fixed
numerical units: .01 probability change for Fed/CPI and .01 log return for
each ETF. All five features must exist: no zero-filling missing inputs.
The commodity-only ablation uses the identical complete-case opportunities,
not a larger commodity-only sample. Actual stage-two coverage must clear the
same ten-development/five-holdout-event threshold for at least one H1/H2/H3
in a family. If both families fail, stop with no preregistration/performance.

Exchange-time evidence: the archived NYSE `hours-calendars` page explicitly
lists **NYSE Arca Equities** core trading 09:30–16:00 ET, its 16:00 closing
auction, separate later trading, and 13:00 equity early closes (13:15 is for
eligible options, not these ETFs). Use Yahoo `indicators.quote.close`, never
post-market prints, and the frozen round-six trading calendar. The five-minute
decision buffer is a timestamp convention, not proof of historical Yahoo API
publication latency; these are retrospective exchange-close signals, not an
API-latency backtest. No final daily close is used at an intraday earlier
decision; H2's morning cutoffs use an earlier session's close.

## Stage-two results: sufficient for the daily tests, sparse H2

All three ETFs have **1,255/1,255** frozen calendar closes,
2021-11-26–2026-11-25, with no missing sessions. Yahoo identifies each as
an ETF on PCX (NYSE Arca); its current session metadata also confirms the
13:00 ET early equity close. That current metadata alone is not evidence
about all historical sessions; the archive's exchange calendar determines
historical dates and the NYSE page supplies core/early-close conventions.

| Target | H | Complete contract/days | Source-covered dev events | Source-covered holdout events |
|---|---|---:|---:|---:|
| Payrolls | H1 | 1,009 | 12 | 7 |
| Payrolls | H2 | 75 | 9 | 4 |
| Payrolls | H3 | 1,193 | 12 | 7 |
| Unemployment | H1 | 1,230 | 12 | 7 |
| Unemployment | H2 | 90 | 10 | 4 |
| Unemployment | H3 | 1,450 | 12 | 7 |

The unchanged base population is **44 family-events** (23 payrolls,
21 unemployment), not 44 independent releases. H1/H3 pass the predeclared
10/5 feasibility screen in both families, so the study proceeds. **H2 has
only four source-covered holdout events in each family**, below the carried
five-test-event inference minimum. Retain the requested H2 in the fixed
12-hypothesis family, disclose its inability to pass with this coverage,
and assign p=1 if it advances with fewer than five holdout events. Do not
relax timing, fill sources, or move events across the split to rescue it.
No H2 holdout scores are calculated unless its development test advances.

Among current fresh target contract-days, source gaps remove **835/2,028**
payroll and **739/2,189** unemployment opportunities. A further **184/1,193**
and **220/1,450** otherwise eligible H3 opportunities lack a following fresh
target quote and cannot enter H1; H3 does not condition on that future quote.
Accuracy drops **65/140** payroll and **52/142** unemployment contracts
because a source or fresh target quote is missing. See `source_cutoffs.csv`
for **every** mandatory target cutoff, including failures, and
`feasibility.csv`/`asset_coverage.csv` for machine-readable counts.

No target return, regression, Brier score, trading ROI, development p-value
or holdout p-value was calculated to make these choices. Predictor probability
changes and ETF returns were prepared as inputs only. **PCE (4), GDP (7)
and core CPI (6 even after pooling MoM/YoY) remain dropped.** No new historical
Polymarket market collection was performed; optional counts describe the
reused archive, not an exhaustive claim about all markets ever listed.
