# Wallet selection variants

**Verdict unchanged: early_edge improves losses versus market but not versus its own placebo; no robust smart-wallet edge or economically material portfolio gain is established.**

On the frozen sample, early_edge's nominal 95% CIs favor it over market for both Brier and log loss, but its own placebo has still lower point-estimate losses and both paired intervals include zero. hit_rate also improves log loss versus market nominally, without separating from its placebo. None of the five new selectors beats its own placebo on either probability metric with a 95% CI wholly below zero. The largest new-selector t−3 mean-return gain versus market is strict's 0.0768 bp per window (mean-variance), before costs. All-six common-meeting results (13 meetings) preserve this interpretation; selector-specific sample sizes are 13–15 meetings.

## Probability accuracy (each selector's own usable meetings)

Differences are selector-calibrated probabilities minus the stated comparator. Negative loss differences are better. 95% paired percentile CIs use 10,000 draws, seed 42, resampling whole meetings and keeping all outcomes and three cutoff horizons together. The placebo has its own walk-forward β fit. Market probabilities are normalized. Different usable samples are not a head-to-head selector ranking.

| Selector | Meetings | ΔBrier vs market [CI] | ΔLog loss vs market [CI] | ΔBrier vs own placebo [CI] | ΔLog loss vs own placebo [CI] |
|---|---:|---|---|---|---|
| baseline | 14 | +0.00082 [-0.00015, +0.00232] | +0.00336 [+0.00008, +0.00756] | +0.00279 [+0.00065, +0.00536] | +0.00656 [+0.00273, +0.01093] |
| hit_rate | 14 | -0.00227 [-0.00533, +0.00004] | -0.00477 [-0.01034, -0.00011] | +0.00001 [-0.00095, +0.00078] | -0.00019 [-0.00234, +0.00186] |
| whale | 15 | -0.00196 [-0.00508, +0.00041] | -0.00342 [-0.00910, +0.00143] | +0.00074 [-0.00196, +0.00314] | +0.00407 [+0.00003, +0.00818] |
| strict | 13 | -0.00039 [-0.00372, +0.00289] | -0.00143 [-0.00625, +0.00264] | +0.00230 [-0.00356, +0.01023] | +0.00405 [-0.00376, +0.01343] |
| early_edge | 13 | -0.00449 [-0.00955, -0.00087] | -0.01198 [-0.02087, -0.00449] | +0.00210 [-0.00024, +0.00555] | +0.00090 [-0.00192, +0.00402] |
| recent | 14 | +0.00080 [-0.00030, +0.00239] | +0.00343 [-0.00008, +0.00781] | +0.00112 [+0.00018, +0.00254] | +0.00264 [+0.00093, +0.00458] |

## t−3 portfolios

Mean paired return differences in **basis points per event window** (1 bp = 0.01 percentage point), with 95% meeting-bootstrap CIs. Each selector uses its own usable sample. The portfolio rules and scenario estimates are unchanged from Part B, including the last-observable-close marking assumption.

| Selector | Vol-target vs market [CI] | Mean-variance vs market [CI] | Vol-target vs own placebo [CI] | Mean-variance vs own placebo [CI] |
|---|---|---|---|---|
| baseline | +0.0078 [+0.0031, +0.0134] | +0.0305 [+0.0000, +0.0721] | +0.0102 [+0.0032, +0.0198] | +0.0259 [-0.0181, +0.0921] |
| hit_rate | +0.0087 [-0.0064, +0.0243] | +0.0319 [-0.0844, +0.1854] | +0.0094 [-0.0005, +0.0219] | -0.0057 [-0.0309, +0.0130] |
| whale | +0.0092 [-0.0035, +0.0244] | +0.0393 [-0.0571, +0.1809] | +0.0068 [-0.0002, +0.0146] | +0.0190 [-0.0068, +0.0607] |
| strict | +0.0156 [+0.0045, +0.0281] | +0.0768 [+0.0000, +0.1695] | +0.0264 [+0.0027, +0.0542] | +0.0127 [-0.1696, +0.1776] |
| early_edge | +0.0066 [-0.0227, +0.0391] | +0.0148 [-0.1723, +0.2297] | +0.0083 [-0.0151, +0.0349] | +0.0368 [-0.1360, +0.2498] |
| recent | +0.0085 [+0.0032, +0.0147] | +0.0402 [+0.0000, +0.1010] | +0.0011 [-0.0013, +0.0034] | -0.0085 [-0.0417, +0.0144] |

## Common-meeting sensitivity

Intersection of usable meetings across all six selectors. Evaluate the existing out-of-sample forecasts on this intersection; do not retrain on the intersection or discard earlier selector-specific training history. The CSV includes both samples and all market/placebo accuracy and portfolio differences.

| Selector | Meetings | ΔBrier vs market [CI] | ΔBrier vs own placebo [CI] | t−3 vol-target vs market (bp) [CI] | t−3 mean-variance vs market (bp) [CI] |
|---|---:|---|---|---|---|
| baseline | 13 | +0.00089 [-0.00017, +0.00253] | +0.00300 [+0.00077, +0.00574] | +0.0084 [+0.0034, +0.0144] | +0.0329 [+0.0000, +0.0770] |
| hit_rate | 13 | -0.00245 [-0.00571, +0.00004] | +0.00001 [-0.00103, +0.00085] | +0.0093 [-0.0068, +0.0262] | +0.0343 [-0.0909, +0.1997] |
| whale | 13 | -0.00226 [-0.00579, +0.00046] | +0.00085 [-0.00224, +0.00357] | +0.0106 [-0.0039, +0.0273] | +0.0453 [-0.0659, +0.2064] |
| strict | 13 | -0.00039 [-0.00372, +0.00289] | +0.00230 [-0.00356, +0.01023] | +0.0156 [+0.0045, +0.0281] | +0.0768 [+0.0000, +0.1695] |
| early_edge | 13 | -0.00449 [-0.00955, -0.00087] | +0.00210 [-0.00024, +0.00555] | +0.0066 [-0.0227, +0.0391] | +0.0148 [-0.1723, +0.2297] |
| recent | 13 | +0.00086 [-0.00033, +0.00261] | +0.00121 [+0.00019, +0.00278] | +0.0092 [+0.0036, +0.0156] | +0.0432 [+0.0000, +0.1088] |

## Selector definitions and safeguards

- **baseline:** unchanged Part A PnL/notional × n/(n+20), at least five trades, floor(top 10%). The original `build_panel.py`, `backtest.py`, panel and Part B outputs are not modified. Recomputed baseline cohorts/flows must match the original panel, and rerun accuracy/portfolio results must match committed Part B results.
- **hit_rate:** winning-side notional / gross actual-token notional, shrunk toward 0.5 as `0.5 + (fraction - 0.5) * n/(n+20)`; at least five trades, top 10%. Positive YES direction wins on a YES settlement; negative direction wins on NO. Thus SELL YES is directional NO and SELL NO directional YES. This is a directional hit fraction, not token ownership or PnL.
- **whale:** top 10% by prior gross actual-token FOMC notional, with positive gross notional and at least one trade. No extra five-trade skill gate: this is deliberately size, not skill.
- **strict:** baseline shrunk PnL score with at least 20 trades; select floor(top 5%).
- **early_edge:** baseline PnL/notional formula, shrinkage and five-trade minimum, computed only from trades with `trade_ts <= individual_market_resolution_proxy - 7 calendar days`. Exactly seven days qualifies. Selection still requires the entire meeting to have resolved strictly before the target cutoff.
- **recent:** baseline score/minimum/shrinkage, using only the last four prior-resolved meetings, ranked by meeting resolution proxy descending (event ID ascending for ties). These are the last four meetings in the mapped FOMC universe, even if their retained trade histories are empty—not a later-active universe.
- Every selector uses only meetings resolved strictly before the target cutoff and trades strictly before it. No current-meeting positions or future labels enter selection. All require at least 20 **selected** wallets; cohorts are not padded. Score ties use ascending wallet address. Gross notional must be positive.
- Each selector has its own same-size placebo, sampled without replacement from its qualifying population, including possible overlap with selected wallets. New selector seeds are `Random("42:selector:event_id:cutoff_epoch")`; baseline retains its original seed unchanged.
- Signals remain net signed YES notional / gross notional in `[cutoff−7d, cutoff)`, with the same empty/unavailable conventions and coverage gates. On the immutable cache, score caching is allowed only when both the resolved-meeting set and latest eligible trade timestamp are identical; this proves the historical row subset is identical.
- The backtest is reused unchanged: pooled-horizon offset logistic regression, λ=1, β=0 with fewer than three prior usable meetings, normalization across outcomes; fixed 1% volatility target and γ=10. Scenario means/variances use fully observable historical same-horizon meeting windows, with pooled fallbacks. No selector hyperparameters are tuned after observing results.

## Limits and multiple testing

**Five new variants means multiple-testing risk**, in addition to two probability metrics, two portfolio rules and sample comparisons. CIs are nominal/unadjusted; the best observed row is not a validated discovery. Only a small number of meetings and one placebo realization per selector are available, with correlated horizons and related wallet populations. A size benchmark improving a loss does not show smart-wallet skill. Retrospective API retention gaps, ambiguous participant-record deduplication, metadata resolution proxies, unverified quote publication times and last-close execution bias remain as documented in BACKTEST.md. Returns are hypothetical event-window marks, not executable fills after the signal became known. Costs and slippage are excluded. Very small portfolio intervals may reflect nearly identical/clipped weights, not economic value. Bootstrap intervals condition on the fixed walk-forward fits rather than refitting them.

## Reproduce

```sh
~/data/polymarket/wallet_backtest_env/bin/python models/wallet_backtest/selection_variants.py --data-root ~/data/polymarket
~/data/polymarket/wallet_backtest_env/bin/python -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v
```

Uses Part A's external immutable SQLite cache after checking its complete source fingerprint. Raw data stays external. Per-selector panels, forecasts, losses and portfolios are retained under `~/data/polymarket/selection_variants/` by default (`--work-dir` overrides). Only the small summary, cohort-count and provenance CSVs are committed. No app behavior or original backtest parameters change.
