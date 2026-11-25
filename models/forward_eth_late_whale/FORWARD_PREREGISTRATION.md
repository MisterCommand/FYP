# Forward ETH daily late-whale test — round 5

**Exactly one hypothesis, one fixed terminal look at N=762 eligible resolved
dates, one-sided alpha 0.01. No interim look, tuning, resizing, alternate
cutoff, replacement rule, placebo, subgroup test or second attempt.** Round 4
did not establish an edge. Its ETH late-whale estimate motivates this new,
genuinely prospective test; it is not independent evidence of an edge.

## Freeze and eligible population

The freeze is the **committer Unix timestamp** of the unique Git commit first
adding this directory's `registration.json`. This definition avoids a circular
self-hash: the runner obtains that immutable commit and timestamp from full Git
history and compares this Markdown and JSON with their blobs in that commit.
No forward data may be scored before that commit. Only markets with **cutoff
strictly greater than** that timestamp qualify; equality and everything earlier
are refused before trade collection or features. Later implementation/evidence
commits do not move the freeze. Rule, scorer, imported implementation and the
approved external collector are pinned by normalized SHA-256 in the JSON.

Take all resolved Ethereum daily Up/Down events in Gamma series 40, without
sampling. Only the original Binance ETHUSDT daily-noon resolution specification
is admitted, never Chainlink TWAP or a new oracle. Derive expiry from the title,
ET/DST and contract description, not Gamma endDate: a noon-start one-minute
candle closes at 12:01 ET; an explicitly noon-closing candle ends at noon.
Cutoff is expiry minus 12 hours. Require closed binary Up/Down settlement and
a conservative settlement proxy no earlier than observation and available by
collection time. Currently unavailable settlement timestamps are pending, not
losses or cash. Contracts unmappable by the original timing/source parser are
metadata exclusions, never replaced by a different rule. Metadata and exclusion
reasons are archived.

Retain the original common data gates: a last Up price strictly before cutoff,
first prints for **both** sides strictly after cutoff and before expiry, and
the original completed Binance minute/strike and 720-hour coverage screen.
Complete exhausted histories must be collected and validated; collection errors,
gaps or changed archives stop the run rather than deleting an unfavorable date.
No-entry exclusions are permitted only after the full history is exhausted.
Multiple admitted events on one observation date are equally averaged, never
treated as independent dates. The first N eligible UTC observation dates in
chronological order available at the terminal look comprise the sample; dates
after N are not tested. Nontrading eligible dates count toward N with ROI zero.

## Exactly the old e_late_whale_pm rule

Using the original normalization and deduplication, sum signed Up notional
over all-wallet participant records with **notional >= $1,000** and timestamp
**cutoff-24h <= t < cutoff**. Divide by gross notional in that same set. Positive
means buy Up; negative means buy Down; zero/no qualifying records means cash.
Use the original deterministic first-print entry for the selected side;
ties use the deduplication fingerprint. Hold to binary settlement. Pay entry
plus **$0.02/share**. If that is >=1, remain in cash. ROI is
`payout/(entry+0.02)-1`, or zero for cash. No thresholds or risk sizing are fitted.
The pinned `rule.py` delegates execution/ROI and inference to the original code.

The wallet-skill definition remains prior settlement PnL/gross times n/(n+20),
minimum five records, top floor(10%), minimum 20, lexicographic ties. Sources
are existing FOMC (including October), macro and the same daily ETH family,
with trade and resolution strictly before cutoff, never other crypto families.
**Rule e uses all-wallet whales, not smart-wallet scores or ranks.** We do not
change that definition or add a wallet filter. Common >=200 qualified-wallet
eligibility is guaranteed by the pinned historical corpus: 137,897 already
qualified before the historical November 18 cutoff. Minimum-five/positive-gross
qualification is monotone as records accumulate. No future wallet score can
alter e's signal; there is no need to rescore wallets to establish this gate.

## Power, sample size and calendar

Historical inputs are the persisted round-four development and holdout
observations, filtered to ETH daily/e only. Hashes are registered; no study
is rerun. Each historical date appears once, including cash dates:

| Dates | n | Traded | Trade rate | Mean ROI | Sample variance (ddof=1) |
|---|---:|---:|---:|---:|---:|
| Development | 79 | 66 | .835443 | .1437944231 | .5194610821 |
| Holdout | 40 | 25 | .625000 | .1708451202 | .3018568830 |
| Pooled | 119 | 91 | .764706 | .1528870944 | .4433035079 |

Use the **half-pooled-mean planning effect**, delta=.07644354721. The normal
approximation is `ceil((Phi^-1(.99)+Phi^-1(.80))^2*s^2/delta^2)`:
**N=762 eligible dates**, approximately 583 traded dates. At the full observed
effect .1528870944, the same calculation gives **N=191**, about 146 traded
dates. That second calculation is descriptive, **not** an alternative stopping
rule. Pooled variance and both effects include cash dates, so dividing N by
the trade rate again would double-count nontrading. This is approximate 80%
power under stable variance, effect, cadence and date independence, not a
guarantee; effect selection, fat tails, dependence and nonstationarity can
make it optimistic. The selected historical sample is only 119 dates.

At one eligible daily date per day, N requires 762 calendar dates. If the freeze
is November 25, 2026 before the November 26 cutoff, the first date is November
26 and the nominal final date is **December 26, 2028**. Applying the historical
119/120 eligibility rate gives about 769 daily opportunities, **January 2,
2029**. These are planning forecasts, not alternate stops. The realized horizon
depends on listing, settlement and data availability. There is **no interim
date**, no N/2 look and no O'Brien–Fleming option.

## Primary metric, inference and lock

Primary metric is mean equal-date after-cost ROI, averaging contracts within
event and events within date exactly as in crypto_event_search. Single
hypothesis H0: nonpositive mean versus positive mean. Use the original one-sided
date-cluster sign-flip test: 65,536 draws, seed 42, plus-one correction (exact
through 16 dates). Pass only if mean >0 and p<.01. There is no Holm adjustment
for a single hypothesis. Sign exchangeability is a null-model assumption;
this is not an exact distribution-free test for every asymmetric return law.

Before N, expose only eligible/traded/candidate counts and data-quality reasons,
not returns, running means, p-values, confidence intervals or performance plots.
Do not call the ROI or inference code at all. At n>=N, atomically claim a
retained exclusive `single_look.json` **before ROI or test evaluation**, binding
the freeze, first N dates and selected input hash. A completed lock prevents
recollection/retesting. A failed claimed evaluation also prevents retry: retain
the lock and report the failure, never delete it or use another data root.
An operational SQLite exclusive lock serializes scheduled invocations and
releases automatically on process exit. Only after the look write
`FORWARD_RESULTS.md`, and seal its statistics in the retained lock.

## Collection, reporting and limitations

Use the existing collector and shared <=4.77 requests/second limiter with
`EventLens-research/0.1 (HKUST FYP)`. Exhaust Gamma keyset pagination, preserving
responses; refuse duplicate/cyclic cursors and off-series events. Do not trust
endDate to exclude prospective candidates. Raw histories, caches, progress,
source fingerprints and locks live in `~/data/polymarket/forward_eth_late_whale/`,
never Git. Freeze the existing prior corpus as hashed in the JSON. Collector,
parser or registration changes cause refusal rather than silent protocol drift.

Run from a dedicated checkout of the freeze, not a checkout reused for unrelated
branches. The runner has no N, alpha, freeze-time, strategy or data-root override.
No report exists before N. Publish a failure as well as a pass. Round-five
selection, only 119 planning dates, changing trade rates, fees and market rules,
participant records rather than executable quotes, capacity, dependence and
uncertain variance limit interpretation. Nothing here guarantees profitability.
