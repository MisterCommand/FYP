# No option-index hypothesis passed development; no holdout performance was evaluated.

Round 7; dev gate p<.10; one-sided holdout Holm p<.01. Historical markets were used in earlier wallet studies; this is a locked new-strategy holdout, not fresh independent data.

All **24 real hypotheses failed to advance**. Consequently the retained terminal
lock is complete with empty real/control holdout results and an empty Holm set.
Every holdout metric, p-value and Holm field below is **uncomputed / not
applicable**, not zero and not a failed holdout test. No hypothesis was substituted.
The same historical events were used in earlier FOMC/macro and round-six searches;
this is not independent forward confirmation.

Preregistration was committed and pushed as
`02ff97247f0f9961d127de61a2820f832419581e` before any real performance.
Development was committed as `d9fa3a39493d7673b2a457403b14e7271f32c7af`
before the one terminal holdout call. Exact round-six events and split are retained.

| Hypothesis | Dev events | Dev metric | Dev p | Holdout events | Holdout metric | Raw p | Holm p | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| cpi/vix/H1 | 9 | -0.00105208 | 0.595703 | — | — | — | — | not advanced |
| cpi/vix/H2 | 15 | 7.03388e-06 | 0.206179 | — | — | — | — | not advanced |
| cpi/vix/H3 | 15 | -0.0739472 | 0.998047 | — | — | — | — | not advanced |
| cpi/term/H1 | 9 | -0.0082561 | 0.923828 | — | — | — | — | not advanced |
| cpi/term/H2 | 15 | -0.00288887 | 0.753925 | — | — | — | — | not advanced |
| cpi/term/H3 | 15 | -0.077589 | 0.996094 | — | — | — | — | not advanced |
| fomc/vix/H1 | 10 | 8.78304e-05 | 0.449219 | — | — | — | — | not advanced |
| fomc/vix/H2 | 14 | -2.15334e-06 | 0.754425 | — | — | — | — | not advanced |
| fomc/vix/H3 | 14 | -0.169289 | 0.996094 | — | — | — | — | not advanced |
| fomc/term/H1 | 10 | 6.87697e-05 | 0.484375 | — | — | — | — | not advanced |
| fomc/term/H2 | 14 | -8.17873e-06 | 0.89641 | — | — | — | — | not advanced |
| fomc/term/H3 | 14 | -0.182494 | 0.99707 | — | — | — | — | not advanced |
| payrolls/vix/H1 | 10 | -0.00873095 | 0.935547 | — | — | — | — | not advanced |
| payrolls/vix/H2 | 16 | 0.0013335 | 0.249075 | — | — | — | — | not advanced |
| payrolls/vix/H3 | 16 | 0.0300472 | 0.275391 | — | — | — | — | not advanced |
| payrolls/term/H1 | 10 | -0.00449684 | 0.947266 | — | — | — | — | not advanced |
| payrolls/term/H2 | 16 | -0.01323 | 0.819518 | — | — | — | — | not advanced |
| payrolls/term/H3 | 16 | 0.0186534 | 0.363281 | — | — | — | — | not advanced |
| unemployment/vix/H1 | 11 | -0.0048588 | 0.649902 | — | — | — | — | not advanced |
| unemployment/vix/H2 | 14 | -0.0069357 | 0.968403 | — | — | — | — | not advanced |
| unemployment/vix/H3 | 14 | 0.0742263 | 0.403809 | — | — | — | — | not advanced |
| unemployment/term/H1 | 11 | -0.00652992 | 0.828613 | — | — | — | — | not advanced |
| unemployment/term/H2 | 14 | -0.00571662 | 0.777622 | — | — | — | — | not advanced |
| unemployment/term/H3 | 14 | 0.031337 | 0.411133 | — | — | — | — | not advanced |

H1 metric is the signed-move slope (outcome fixed effects; event-cluster CR1 SEs in CSV; one-sided cluster wild-score sign-flip p). H2 metric is market-minus-adjusted binary Brier (positive improves); CSV also gives adjusted-minus-market Brier delta. H3 is mean equal-event after-cost ROI, including cash.

## Placebo controls (descriptive only; excluded from gate and Holm)

| Pipeline | Dev metric | Dev p | Holdout metric | Holdout p |
|---|---:|---:|---:|---:|
| cpi/vix/H1 | 0.00468594 | 0.302734 | — | — |
| cpi/vix/H2 | -0.0108081 | 0.769323 | — | — |
| cpi/vix/H3 | -0.0861983 | 0.998047 | — | — |
| cpi/term/H1 | 0.00837285 | 0.136719 | — | — |
| cpi/term/H2 | -0.000529917 | 0.742226 | — | — |
| cpi/term/H3 | -0.0731082 | 0.992188 | — | — |
| fomc/vix/H1 | -0.000206298 | 0.59668 | — | — |
| fomc/vix/H2 | -0.0105659 | 0.854915 | — | — |
| fomc/vix/H3 | -0.207666 | 1 | — | — |
| fomc/term/H1 | -0.00237695 | 0.959961 | — | — |
| fomc/term/H2 | -0.00894976 | 0.912609 | — | — |
| fomc/term/H3 | -0.188023 | 0.998047 | — | — |
| payrolls/vix/H1 | -0.0111497 | 0.857422 | — | — |
| payrolls/vix/H2 | -0.00303921 | 0.912909 | — | — |
| payrolls/vix/H3 | 0.0197202 | 0.399414 | — | — |
| payrolls/term/H1 | 0.0142281 | 0.316406 | — | — |
| payrolls/term/H2 | -0.000924284 | 0.719428 | — | — |
| payrolls/term/H3 | 0.0307189 | 0.320312 | — | — |
| unemployment/vix/H1 | 0.00150353 | 0.383789 | — | — |
| unemployment/vix/H2 | -0.00498317 | 0.741826 | — | — |
| unemployment/vix/H3 | 0.0713384 | 0.348145 | — | — |
| unemployment/term/H1 | 0.00515249 | 0.335938 | — | — |
| unemployment/term/H2 | -0.00841087 | 0.908209 | — | — |
| unemployment/term/H3 | 0.0653932 | 0.412109 | — | — |

## Limitations

- Round 7 of a repeated research sequence; prior wallet-study use means the historical holdout is not independent fresh confirmation.
- Only seven held-out releases per family, and sometimes fewer informative H1 events. Exact event sign-flip tests have coarse minimum p-values; Holm further limits power.
- H1 CR1 SEs/wild-score inference and paired Brier bootstrap assume adequate event-level independence. Serial/overlapping exposure and co-released families remain dependent; Holm tolerates dependence but does not repair invalid marginal p-values.
- VIX and VIX9D are official CBOE closes, scaled as 1% log changes. MOVE was dropped before performance for missing sample dates and unclear close timing. The two VIX-derived predictors are dependent.
- Approved session boundaries use New York time: normally 16:15, or 13:15 on early-close sessions. This differs from round six by 15 minutes to avoid using a later VIX close at an earlier PM decision. Weekend/holiday horizons run to the next exchange session. No hourly analysis is used.
- Fresh trades are required in each PM interval; skipped gaps are counted in FEASIBILITY.md. Retention removes seven early FOMC meetings. Missing outcome-class histories cause H1 omissions and market/cash fallbacks for H2/H3.
- H1 includes the final pre-release forecast interval when next-session prices exist: its target may incorporate release news, using actual trades no later than settlement rather than substituting the realized label. H3 eligibility uses only the current fresh baseline, never future target availability.
- Trades are participant-print execution proxies, not executable quotes. Holding many daily entries to resolution produces overlapping positions; ROI is an equal-event diagnostic, not a deployable compounded portfolio. The flat $0.02 cost proxy ignores changing fees and capacity.
- Historical asset-price revisions and point-in-time archive availability limit real-world replication. No crypto data enters this study.
