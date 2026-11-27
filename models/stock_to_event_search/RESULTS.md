# No preregistered stock-to-event hypothesis established a holdout edge.

Round 6; dev gate p<.10; one-sided holdout Holm p<.01. Historical markets were used in earlier wallet studies; this is a locked new-strategy holdout, not fresh independent data.

Only **FOMC × SPY × H2 accuracy** advanced. Adjusted-minus-market Brier delta improved from **−0.00000211311** in development (p=.0517948) to **−0.0000439414** over seven holdout meetings (32 binary cutoffs), but **raw p = Holm p = .0396960 fails the registered .01 threshold**. The holdout placebo worsened Brier by +.000444263 (p=.958204). No lead-lag or trading hypothesis advanced; their holdout performance, and all other nonadvanced holdout metrics (**23 real hypotheses**), remains uncomputed. No holdout ROI claim is made.

| Hypothesis | Dev events | Dev metric | Dev p | Holdout events | Holdout metric | Raw p | Holm p | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| cpi/spy/H1 | 9 | -0.0357952 | 0.630859 | — | — | — | — | not advanced |
| cpi/spy/H2 | 15 | -4.47412e-05 | 0.871513 | — | — | — | — | not advanced |
| cpi/spy/H3 | 15 | -0.0781319 | 0.998047 | — | — | — | — | not advanced |
| cpi/rates/H1 | 9 | -0.00802 | 0.734375 | — | — | — | — | not advanced |
| cpi/rates/H2 | 15 | -0.0010525 | 0.910609 | — | — | — | — | not advanced |
| cpi/rates/H3 | 15 | -0.0811879 | 0.998047 | — | — | — | — | not advanced |
| fomc/spy/H1 | 10 | 0.00329632 | 0.449219 | — | — | — | — | not advanced |
| fomc/spy/H2 | 14 | 2.11311e-06 | 0.0517948 | 7 | 4.39414e-05 | 0.039696 | 0.039696 | FAIL |
| fomc/spy/H3 | 14 | -0.184318 | 0.996094 | — | — | — | — | not advanced |
| fomc/rates/H1 | 10 | 0.00502421 | 0.271484 | — | — | — | — | not advanced |
| fomc/rates/H2 | 14 | -1.12312e-05 | 0.776322 | — | — | — | — | not advanced |
| fomc/rates/H3 | 14 | -0.149932 | 0.992188 | — | — | — | — | not advanced |
| payrolls/spy/H1 | 10 | -0.0496903 | 0.837891 | — | — | — | — | not advanced |
| payrolls/spy/H2 | 16 | 0.00129165 | 0.214179 | — | — | — | — | not advanced |
| payrolls/spy/H3 | 16 | 0.0232546 | 0.3125 | — | — | — | — | not advanced |
| payrolls/rates/H1 | 10 | 0.0172113 | 0.399414 | — | — | — | — | not advanced |
| payrolls/rates/H2 | 16 | -0.010664 | 0.884612 | — | — | — | — | not advanced |
| payrolls/rates/H3 | 16 | -0.006643 | 0.549805 | — | — | — | — | not advanced |
| unemployment/spy/H1 | 11 | -0.0943697 | 0.868652 | — | — | — | — | not advanced |
| unemployment/spy/H2 | 14 | -0.00151424 | 0.859414 | — | — | — | — | not advanced |
| unemployment/spy/H3 | 14 | 0.0776337 | 0.484375 | — | — | — | — | not advanced |
| unemployment/rates/H1 | 11 | -0.106931 | 0.767578 | — | — | — | — | not advanced |
| unemployment/rates/H2 | 14 | -0.00250601 | 0.732727 | — | — | — | — | not advanced |
| unemployment/rates/H3 | 14 | 0.0225836 | 0.401367 | — | — | — | — | not advanced |

H1 metric is the signed-move slope (outcome fixed effects; event-cluster CR1 SEs in CSV; one-sided cluster wild-score sign-flip p). H2 metric is market-minus-adjusted binary Brier (positive improves); CSV also gives adjusted-minus-market Brier delta. H3 is mean equal-event after-cost ROI, including cash.

## Placebo controls (descriptive only; excluded from gate and Holm)

| Pipeline | Dev metric | Dev p | Holdout metric | Holdout p |
|---|---:|---:|---:|---:|
| cpi/spy/H1 | 0.00837431 | 0.369141 | — | — |
| cpi/spy/H2 | 0.000170352 | 0.416558 | — | — |
| cpi/spy/H3 | -0.0675056 | 0.998047 | — | — |
| cpi/rates/H1 | 0.00613502 | 0.25 | — | — |
| cpi/rates/H2 | -0.000418172 | 0.749725 | — | — |
| cpi/rates/H3 | -0.0693103 | 0.998047 | — | — |
| fomc/spy/H1 | -0.0233368 | 0.912109 | — | — |
| fomc/spy/H2 | -6.57201e-05 | 0.80372 | -0.000444263 | 0.958204 |
| fomc/spy/H3 | -0.20844 | 1 | — | — |
| fomc/rates/H1 | 0.00542185 | 0.257812 | — | — |
| fomc/rates/H2 | -5.38425e-06 | 0.794921 | — | — |
| fomc/rates/H3 | -0.171942 | 0.995117 | — | — |
| payrolls/spy/H1 | 0.0578856 | 0.0585938 | — | — |
| payrolls/spy/H2 | 0.000659024 | 0.282872 | — | — |
| payrolls/spy/H3 | 0.0384563 | 0.220703 | — | — |
| payrolls/rates/H1 | 0.0270493 | 0.267578 | — | — |
| payrolls/rates/H2 | -0.00411601 | 0.910209 | — | — |
| payrolls/rates/H3 | 0.0321337 | 0.288086 | — | — |
| unemployment/spy/H1 | -0.0182412 | 0.631836 | — | — |
| unemployment/spy/H2 | -0.000341161 | 0.685631 | — | — |
| unemployment/spy/H3 | 0.0654142 | 0.381836 | — | — |
| unemployment/rates/H1 | -0.0634159 | 0.922852 | — | — |
| unemployment/rates/H2 | -0.00497025 | 0.932907 | — | — |
| unemployment/rates/H3 | -0.0133617 | 0.57666 | — | — |

## Limitations

- Round 6 of a repeated research sequence; prior wallet-study use means the historical holdout is not independent fresh confirmation.
- Only seven held-out releases per family, and sometimes fewer informative H1 events. Exact event sign-flip tests have coarse minimum p-values; Holm further limits power.
- H1 CR1 SEs/wild-score inference and paired Brier bootstrap assume adequate event-level independence. Serial/overlapping exposure and co-released families remain dependent; Holm tolerates dependence but does not repair invalid marginal p-values.
- DGS2 is archived for coverage only: the H.15 release is 16:15 ET, too late for a 16:00 ET decision. The permitted inverse SHY return is a duration/carry/dividend-affected proxy, not the 2-year yield itself. SPY/SHY use unadjusted daily close prices.
- Session boundaries use New York time: normally 16:00, or 13:00 on the published NYSE early-close sessions in this sample. Weekend/holiday horizons run to the next exchange session. No full-sample hourly source is used.
- Fresh trades are required in each PM interval; skipped gaps are counted in FEASIBILITY.md. Retention removes seven early FOMC meetings. Missing outcome-class histories cause H1 omissions and market/cash fallbacks for H2/H3.
- H1 includes the final pre-release forecast interval when next-session prices exist: its target may incorporate release news, using actual trades no later than settlement rather than substituting the realized label. H3 eligibility uses only the current fresh baseline, never future target availability.
- Trades are participant-print execution proxies, not executable quotes. Holding many daily entries to resolution produces overlapping positions; ROI is an equal-event diagnostic, not a deployable compounded portfolio. The flat $0.02 cost proxy ignores changing fees and capacity.
- Historical asset-price revisions and point-in-time archive availability limit real-world replication. No crypto data enters this study.
