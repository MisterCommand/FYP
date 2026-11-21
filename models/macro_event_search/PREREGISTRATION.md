# Preregistered macro event strategy search

**This registration is committed after feasibility and before any strategy performance. Macro holdouts have never been analyzed for these strategies. No holdout result has been computed.**

## Population and fixed split

The committed `registration.json` lists every development and holdout reference period. Join its family/reference IDs to the committed `release_coverage.csv` for exact official BLS release timestamps, provenance URLs and per-horizon entry availability. Both registration files and that inventory are verified against this preregistration commit before execution. The feasibility snapshot precedes this commit.

| Family | Development events | Latest chronological holdout | SPY holdout events with available windows |
|---|---:|---:|---:|
| Headline CPI MoM | 13 | 7 | 5 |
| Headline CPI YoY | 14 | 7 | 5 |
| Payrolls | 15 | 8 | 7 |
| Unemployment | 14 | 7 | 6 |

Holdout = latest ceil(N/3), minimum five, within each family, ordered by official release timestamp. CPI holdouts are April–October 2026; payrolls additionally includes February 2026; unemployment is April–October 2026. Development includes December 2024 headline MoM at **t−1d only**, not t−3d. Thus 85 family-events qualify on at least one horizon, one more than the stricter original feasibility screen. Core CPI, PCE and GDP fail the 15-event threshold and are excluded. Single-threshold legacy inflation questions are excluded. Duplicate/extra-bracket Gamma objects share one family-release observation, although distinct binary contracts remain distinct contracts.

The cutoffs are exactly official release UTC minus 3 and 1 calendar days. Exclude a horizon with no eligible binary contracts or an unavailable smart set; never replace it with zero. Pool horizons within release, not as independent observations. No tuning or additional strategies will be performed.

## Fixed strategies and execution

Reuse `models/strategy_search` direction, binary return, prior-only ridge calibration, cohort, flow and price-selection functions where compatible. Strategy g is not included.

| ID | Fixed rule | Higher-is-better primary |
|---|---|---|
| a_smart_pm | Direction of smart-wallet net YES flow | Mean after-cost binary ROI |
| b_contrarian_pm | Opposite all-wallet net YES flow | Mean after-cost binary ROI |
| c_momentum_pm | Direction of pre-cutoff YES probability minus its value seven days earlier; missing lag means no trade | Mean after-cost binary ROI |
| d_calibration_pm | Prior-only Platt correction: buy YES if p≥0.5 and calibrated q>p; buy NO if p≤0.1 and q<p; otherwise flat | Mean after-cost binary ROI |
| e_late_whale_pm | Direction of signed YES notional from records ≥$1,000 during the final 24h before cutoff | Mean after-cost binary ROI |
| f_uncertainty_spy | Exposure 0.5 if mean binary entropy ≥0.5 OR smart/all disagreement fraction ≥0.5, otherwise 1; compare constant 1 | Window Sharpe difference |
| h_placebo_pm | Same as a using size-matched seeded random qualifying wallets | Mean after-cost binary ROI, negative control |

All signal windows are [cutoff−7d, cutoff); late whale uses [cutoff−1d, cutoff). Latest YES price is strictly before cutoff. PM eligibility requires a pre-cutoff YES price and both token entry prices strictly after cutoff and before release; a zero signal is a genuine flat, not missing. Buy the selected token at its first participant-record price after cutoff, add **$0.02/share**, hold to binary settlement. Entry plus cost ≥1 means flat. Use equal-dollar contract sleeves including flats, average contracts within horizon, horizons within family-release; do not overweight an event just because it has more contracts. Overlapping CPI contracts are treated as separate binary contracts, never normalized into one categorical vector.

For f, binary entropy is H(p)=−[p log p+(1−p)log(1−p)]/log(2), with endpoints H=0; take the arithmetic mean across the event's eligible contracts. Disagreement is the fraction of those contracts whose smart and all-wallet signals have opposite signs. No cross-contract normalization. Entry is the first SPY close strictly after cutoff, exit the close on the official release day. Require entry strictly before exit and before the release; otherwise mark missing. Use timezone-aware 16:00 ET closes. Net return = exposure×(SPY window return−2×0.001); benchmark uses exposure 1 with the same two-sided costs. Prices after **October 7, 2026** are unavailable, not zero. A family with fewer than five available SPY holdout release dates would be pooled-only for f. The pre-performance availability check gives 5/5/7/6, so **no included family is pooled-only**. SPY observations remain fewer than PM observations.

## Point-in-time wallet skill and calibration

Wallet score = sum signed YES shares×(settlement−YES-equivalent price)/sum actual token notional, shrunk by n/(n+20), minimum five records. Use only trades strictly before cutoff from markets resolved strictly before cutoff, from **the same macro family plus FOMC**. Smart = top floor(10%) by score, ties by wallet address; unavailable below 20 selected wallets. Placebo = same-size random sample among qualifying wallets using the inherited seed 42 and deterministic event/cutoff key. Signal = signed YES notional/gross notional, bounded [−1,1], zero when no flow. FOMC training uses the existing cache; macro training excludes dropped families and legacy thresholds.

Development cannot read holdout markets into fitting or skill; macro skill sources in development are restricted to registered development IDs. During the single chronological holdout pass, wallet scores may use already-resolved earlier holdout markets, as a preregistered point-in-time updating rule, never later ones. Strategy parameters remain fixed. Calibration d uses only same-family earlier resolved development events and pre-cutoff predictions, pools horizons, requires three distinct prior events, L2=1 toward intercept 0/slope 1. During development fit walk-forward. Freeze one map per family/horizon using eligible development records resolved before that horizon's **first holdout cutoff**; never refit on holdout outcomes. Other strategies have no fitted parameters.

## Inference, gate and one extra pooled test

Each family registers a–f and h: 28 tests. **One additional pooled test** is registered: a_smart_pm across the four families. Pooled equal-weights family-release averages within the **same official release UTC timestamp**, then averages timestamps; it does not treat co-released CPI or payroll/unemployment observations as independent. The same timestamp clustering is used per family. There are 29 registered hypotheses total. h is a negative control; a placebo pass is not a skill edge.

Primary PM statistic is mean net ROI vs zero. For f it is Sharpe(strategy)−Sharpe(constant SPY), using sample window standard deviations, nonannualized. Zero variance means Sharpe 0. Also report net mean return, benchmark mean and realized volatility for f. Average both horizons within each family-release before inference. Use exact one-sided sign-flip cluster permutation for ≤16 release clusters; otherwise 65,536 seeded Monte Carlo cluster sign flips with the (1+exceedances)/(1+draws) correction. For PM flip clustered returns about zero; for f swap strategy/benchmark paired cluster returns. Co-released families always share a permutation sign. p counts null statistics at least the observed statistic, tolerance 1e−12.

Development gate: primary >0 and one-sided p<0.10. Rank within comparable primary units; no parameters are tuned. Advance only gate-passing registered family×strategy hypotheses plus the one pooled hypothesis if it passes. Freeze results, fitted maps, exact advanced IDs, preregistration commit and CRLF-normalized input/code hashes **before** accessing holdout strategy returns. Holdout code must verify all hashes and the gate, reject unknown IDs, atomically create an exclusive single-use lock, then evaluate only advanced hypotheses once. No advance means no holdout performance is computed for that hypothesis. No manual lock deletion/retry after failure.

Holdout pass: primary >0, same positive sign as development, **one-sided Holm-adjusted p<0.05 across all advanced hypotheses (including the extra pooled test)**, and positive mean net return after costs. No unadjusted significant result counts as a pass. With five clusters, exact minimum p=1/32, so Holm may make discovery impossible; report this power limitation rather than relax the rule. Return windows may overlap across nearby release dates; timestamp clustering handles simultaneous families, not all serial dependence. Participant-record fills are proxies, not executable quotes; thin markets, retention, survivorship, proxy resolution timestamps and the single seeded placebo are limitations.

Report RESULTS.md and results.csv with development metric/p, holdout metric/raw p/Holm p and status for all registered hypotheses. Retain the external development manifest and holdout lock. No performance numbers are present in this registration.
