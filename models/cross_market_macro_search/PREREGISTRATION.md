# Round 8: can Fed, CPI and commodity markets predict other macro markets?

This fixes **12 hypotheses before any performance calculation**:
two targets × two predictor configurations × H1/H2/H3. Targets are payrolls
and unemployment; configurations are the five-feature combined signal and
one **commodity-only group ablation**. No optional target or extra model is
registered. PCE/GDP/core CPI fail the 15-release screen before performance.

## Population and timing

Keep the exact round-six populations and chronological splits:
payrolls 23 events (16 development / 7 holdout), unemployment 21 (14/7).
The latest approximately 30% remain holdout. `registration.json` contains
the full event lists and hashes. Reused historical holdouts are **not fresh
independent confirmation** after earlier research rounds.

All exact source selections, URLs, windows, exchange clocks and exclusions
are frozen in FEASIBILITY.md. Signals use the change from the preceding
session close to the current close: Fed P(no change) for the nearest future
archived FOMC meeting; highest-threshold upper-bucket headline YoY CPI
probability for the nearest future archived CPI release; and USO, GLD, CPER
unadjusted close log returns. No alternative meeting, CPI bucket or source
fills missing data. Fed/CPI use fresh actual prints at **both** endpoints
for the same contract; each source announcement is strictly after decision.

The five features are scaled by **.01** each (one probability point or 1%
log return), not estimated standard deviations. Predictor close is 16:00 ET
or 13:00 on early closes; the daily decision is **16:05/13:05 ET**, so every
predictor endpoint is strictly before decision. H2 uses release-minus-24h
and the latest predictor window ending **strictly before** that cutoff.
The source must still be a future release at the actual H2 cutoff. No hourly
data, alternate lags, tuning, clipping of signals or extra thresholds.

Complete-case availability is shared by combined and ablation pipelines.
H1/H3 have 12/7 source-covered events per family. H2 has only 9/4 payroll
and 10/4 unemployment: its four-event holdout cannot satisfy the fixed five-
event inference minimum. This limitation is known before performance; H2
is retained as requested and gets p=1 if advanced with fewer than five events.
No future H1 quote is required for H3 eligibility.

## Causal development-only direction learning

For each feature and canonical target outcome class, learn the covariance
sign of the scaled feature and next-session target Δlogit(p), using only
**three or more strictly prior-resolved development events**. Every training
next-close timestamp must also precede the forecast. Exclude the current
event, including its other contracts; never use a held-out target for signs.
Canonicalization is round six's case/whitespace/comma/inequality mapping,
retaining numerical thresholds and original family subtype.

The signed feature vector is raw scaled features multiplied by these signs.
An untrained class has an all-zero vector. Exact zero covariance gives a
zero feature. The combined scalar signal is the **arithmetic mean of all
five signed features**; the commodity-only scalar is the mean of its three
signed commodity features. There is no fitted combination-weight search.
The ablation recomputes signs on the same data using only those three inputs.
Direction learning is expanding/as-of in development and frozen to development
sources in holdout; later-known development settlements enter only when causal.

## H1: lead-lag

Regress next-session target Δlogit(p) on the scalar combined signal (or the
ablation scalar), with canonical outcome fixed effects. Require fresh last
actual PM prints in each decision interval; skip missing intervals without
carry-forward. The last pre-release forecast may have a next-session target
that incorporates announcement news. Do not replace a missing print with its
realized label; no target print later than archived settlement.

Omit untrained classes. Clip probabilities to [1e-6, 1−1e-6] only for logit.
Test positive slope, with event-cluster CR1 SE and the round-six restricted-
null event wild-score sign-flip p after within-outcome demeaning. Enumerate
all signs at ≤16 events; otherwise 10,000 seed-42 draws with plus-one p.
Fewer than five test events gives p=1. Report slope/SE, not an H1 trading ROI.

## H2: walk-forward combined L2 logistic accuracy

`logit(p_adjusted) = logit(p_market) + beta · signed_feature_vector`.

Use **five separately fitted coefficients** for combined, three for ablation;
not merely a scalar calibration of an equal-weight index. Offset is market
logit; no intercept. L2 penalty is `||beta||²/2` (L2=1), the prior summed-
loss convention, with no tuning. Fit by deterministic Newton/backtracking.
Require three prior-resolved events with informative signed vectors. Training
vectors must themselves have been constructed as of their original cutoffs.
An earlier held-out event label may enter this deterministic online beta fit
only after settlement and before the current forecast; it never enters signs.
Unknown signs or insufficient training give the exact market probability,
including original 0/1 endpoints, rather than a clipped fallback.

Use a last target print strictly newer than cutoff−24h and at/before cutoff.
Score binary Brier per contract, average within event, then equal-weight events.
Primary improvement is market-minus-adjusted Brier (positive better); also
report adjusted-minus-market delta. Paired centered event bootstrap uses
10,000 seed-42 resamples and plus-one one-sided p; percentile 95% improvement
CI. Fewer than five test events gives p=1. No ROI substituted for accuracy.

## H3: after-cost trading

At a current fresh baseline, positive scalar signal buys YES, negative buys
NO, zero/untrained stays cash. Enter on the first actual selected-side print
**strictly after decision and before official release**. Hold to archived
settlement. Per-dollar ROI is `payout / (side_entry_price + .02) − 1`.
If cost-inclusive price is ≥1 or a selected-side entry is missing, stay cash.
Equal-weight opportunities including cash within event, then equal-weight
events. One-sided event sign-flip p is as in H1; fewer than five events gives
p=1. These overlapping participant-print bets are not a compounded portfolio.

## Descriptive placebo

Run each pipeline, including its own sign learning, with a common earlier
date's **whole five-feature vector**, subsetting for the ablation. Candidate
donors are strictly earlier source-complete daily windows. Index is
`int(SHA256(UTF8('42|'+family+'|'+str(asset_end_epoch))).hexdigest(),16)`
modulo the number of earlier eligible donor windows. No future donor; no prior
donor gives a zero vector (explicit uninformative control). This keeps the
cross-market group correlation of a donor date. Placebos never gate or enter
Holm; compute all development controls but only matching advanced holdout ones.

## Gates, single use and provenance

Advance only positive registered metrics with **one-sided development p<.10**.
Freeze every development result/control and exact advancement set in a committed
development.json before holdout. A retained exclusive lock is created before
any holdout scoring; failed claims block retries. Only advanced hypotheses and
their matching controls are evaluated. With no advancement, holdout results,
controls and Holm remain **empty**, not zero-valued failed tests.

Holm correction is across all advanced real hypotheses, with no target/group
reset. A pass requires positive metric and **one-sided Holm p<.01**. No pooled
claim is added. Co-released payroll/unemployment and overlapping exposures
create dependence; Holm tolerates dependence, but cannot fix invalid marginal
tests or turn a repeated historical search into independent confirmation.

Pin implementation, tests, dependency code, sources, raw ETF responses, full
input panel, exact lists and availability tables by SHA-256 before scoring;
normalize CRLF→LF for text and stream binary databases unchanged. Commit and
push preregistration before the real development invocation. Runtime verifies
committed preregistration bytes and every pin. No collector runs during scoring;
no ETH/crypto or forward-test files/data/worktrees are used.
