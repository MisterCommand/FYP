# No preregistered cross-market hypothesis established a holdout edge.

Round 8; 12 hypotheses; dev gate p<.10; one-sided holdout Holm p<.01. These reused historical markets are not fresh independent confirmation.

| Hypothesis | Dev events | Dev metric | Dev p | Holdout events | Holdout metric | Raw p | Holm p | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| payrolls/combined/H1 | 6 | -0.0540491 | 0.734375 | — | — | — | — | not advanced |
| payrolls/combined/H2 | 9 | 0.0045972 | 0.111689 | — | — | — | — | not advanced |
| payrolls/combined/H3 | 12 | 0.0280142 | 0.234375 | — | — | — | — | not advanced |
| payrolls/commodities/H1 | 6 | -0.0692623 | 0.859375 | — | — | — | — | not advanced |
| payrolls/commodities/H2 | 9 | -0.000759541 | 0.774123 | — | — | — | — | not advanced |
| payrolls/commodities/H3 | 12 | 0.0249062 | 0.296875 | — | — | — | — | not advanced |
| unemployment/combined/H1 | 9 | 0.0174349 | 0.310547 | — | — | — | — | not advanced |
| unemployment/combined/H2 | 10 | -0.0443167 | 0.929307 | — | — | — | — | not advanced |
| unemployment/combined/H3 | 12 | -0.0141146 | 0.617188 | — | — | — | — | not advanced |
| unemployment/commodities/H1 | 9 | 0.1134 | 0.078125 | 7 | -0.00478383 | 0.53125 | 0.53125 | FAIL |
| unemployment/commodities/H2 | 10 | -0.0211474 | 0.960404 | — | — | — | — | not advanced |
| unemployment/commodities/H3 | 12 | -0.0432064 | 0.857422 | — | — | — | — | not advanced |

H1 metric is the signed-move slope (outcome fixed effects; event-cluster CR1 SEs in CSV; one-sided cluster wild-score sign-flip p). H2 metric is market-minus-adjusted binary Brier (positive improves); CSV also gives adjusted-minus-market Brier delta. H3 is mean equal-event after-cost ROI, including cash.

## Placebo controls (descriptive only; excluded from gate and Holm)

| Pipeline | Dev metric | Dev p | Holdout metric | Holdout p |
|---|---:|---:|---:|---:|
| payrolls/combined/H1 | -0.0264163 | 0.9375 | — | — |
| payrolls/combined/H2 | 0.00864684 | 0.256574 | — | — |
| payrolls/combined/H3 | -0.00188959 | 0.546875 | — | — |
| payrolls/commodities/H1 | 0.0230983 | 0.28125 | — | — |
| payrolls/commodities/H2 | 0.00366071 | 0.111689 | — | — |
| payrolls/commodities/H3 | -0.0041461 | 0.5625 | — | — |
| unemployment/combined/H1 | -0.0368187 | 0.785156 | — | — |
| unemployment/combined/H2 | -0.00528029 | 0.70443 | — | — |
| unemployment/combined/H3 | -0.0637725 | 0.953125 | — | — |
| unemployment/commodities/H1 | 0.000991795 | 0.496094 | 0.0219496 | 0.367188 |
| unemployment/commodities/H2 | -0.0058088 | 0.920608 | — | — |
| unemployment/commodities/H3 | -0.0516061 | 0.923828 | — | — |

## Limitations

- Round 8 of a repeated research sequence; prior study use means the historical holdout is not independent fresh confirmation.
- Only seven held-out releases per family, and sometimes fewer informative H1 events. Exact event sign-flip tests have coarse minimum p-values; Holm further limits power.
- H1 CR1 SEs/wild-score inference and paired Brier bootstrap assume adequate event-level independence. Serial/overlapping exposure and co-released families remain dependent; Holm tolerates dependence but does not repair invalid marginal p-values.
- Fed is change in P(no change) at the nearest future archived meeting, not a complete expected rate path. Missing archived meetings can change its maturity. CPI is change in the highest-threshold upper YoY bucket, whose threshold changes between releases; it is not expected inflation. Sources are selected before checking availability, without replacement.
- USO/GLD/CPER are unadjusted ETF prices, not spot commodity or continuously rolled futures prices. Fees, rolls, carry and distributions affect these proxies. Historical Yahoo vintages and publication latency are not point-in-time verified.
- Signals end at 16:00/13:00 ET; daily PM decisions are 16:05/13:05, with early closes and DST. H2 uses only an earlier completed session. See source_cutoffs.csv for every release-minus-24h availability check.
- Complete-case source coverage: H1/H3 12 development and 7 holdout events per family. H2 only 9/4 payroll and 10/4 unemployment events: below the five-event test minimum in holdout, so any advanced H2 would receive p=1. Causal training further reduces informative observations. The registered H2 is retained rather than silently changing the cutoff or source.
- Missing outcome-class histories cause H1 omissions and market/cash fallbacks for H2/H3. The commodity-only ablation uses the same complete-case opportunities, not a larger standalone commodity population.
- H1 includes the final pre-release forecast interval when next-session prices exist: its target may incorporate release news, using actual trades no later than settlement rather than substituting the realized label. H3 eligibility uses only the current fresh baseline, never future target availability.
- Trades are participant-print execution proxies, not executable quotes. Holding many daily entries to resolution produces overlapping positions; ROI is an equal-event diagnostic, not a deployable compounded portfolio. The flat $0.02 cost proxy ignores changing fees and capacity.
- Historical asset-price revisions and point-in-time archive availability limit real-world replication. No crypto data enters this study.
