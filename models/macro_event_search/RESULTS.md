# Macro event search results

**Verdict: No preregistered strategy established a holdout edge.**

Preregistration commit: `c431fac`. Macro holdouts were untouched before registration. No tuning or additional strategies were introduced. The exclusive holdout lock is retained outside git.

Only smart-wallet PM in payrolls passed development: mean after-cost ROI **+34.22%**, p=0.01263 over 15 release clusters. On its eight-release holdout the mean reversed to **−7.79%**, one-sided raw and Holm p=0.91016. It fails both the sign and significance requirements. The other 28 registered hypotheses did not advance; their holdout performance remains uncomputed. This is a failure to establish an edge, not proof that no economically useful edge exists.

| Family | Strategy | Dev clusters | Dev metric | Dev p | Holdout clusters | Holdout metric | Holdout p | Holm p | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| cpi_headline_mom | a_smart_pm | 13 | -0.200545 | 0.983398 | — | — | — | — | not advanced |
| cpi_headline_mom | b_contrarian_pm | 13 | -0.482637 | 0.999634 | — | — | — | — | not advanced |
| cpi_headline_mom | c_momentum_pm | 13 | -0.0474837 | 0.724854 | — | — | — | — | not advanced |
| cpi_headline_mom | d_calibration_pm | 13 | -0.0223828 | 0.814453 | — | — | — | — | not advanced |
| cpi_headline_mom | e_late_whale_pm | 13 | 0.00512042 | 0.125 | — | — | — | — | not advanced |
| cpi_headline_mom | f_uncertainty_spy | 13 | 0.00180849 | 0.495117 | — | — | — | — | not advanced |
| cpi_headline_mom | h_placebo_pm | 13 | -0.102525 | 0.938477 | — | — | — | — | not advanced |
| cpi_headline_yoy | a_smart_pm | 14 | -0.0372625 | 0.706421 | — | — | — | — | not advanced |
| cpi_headline_yoy | b_contrarian_pm | 14 | -0.0558363 | 0.503235 | — | — | — | — | not advanced |
| cpi_headline_yoy | c_momentum_pm | 14 | -0.21474 | 0.994263 | — | — | — | — | not advanced |
| cpi_headline_yoy | d_calibration_pm | 14 | 0.00229386 | 0.414062 | — | — | — | — | not advanced |
| cpi_headline_yoy | e_late_whale_pm | 14 | 0.0124595 | 0.257812 | — | — | — | — | not advanced |
| cpi_headline_yoy | f_uncertainty_spy | 14 | -0.077694 | 0.867188 | — | — | — | — | not advanced |
| cpi_headline_yoy | h_placebo_pm | 14 | -0.129028 | 0.976379 | — | — | — | — | not advanced |
| payrolls | a_smart_pm | 15 | 0.342184 | 0.0126343 | 8 | -0.0779392 | 0.910156 | 0.910156 | fail |
| payrolls | b_contrarian_pm | 15 | 0.168639 | 0.31131 | — | — | — | — | not advanced |
| payrolls | c_momentum_pm | 15 | -0.109034 | 0.778015 | — | — | — | — | not advanced |
| payrolls | d_calibration_pm | 15 | 0 | 1 | — | — | — | — | not advanced |
| payrolls | e_late_whale_pm | 15 | -0.0189633 | 0.765625 | — | — | — | — | not advanced |
| payrolls | f_uncertainty_spy | 15 | 0 | 0.500031 | — | — | — | — | not advanced |
| payrolls | h_placebo_pm | 15 | 0.0791646 | 0.269043 | — | — | — | — | not advanced |
| unemployment | a_smart_pm | 14 | -0.0890295 | 0.784302 | — | — | — | — | not advanced |
| unemployment | b_contrarian_pm | 14 | -0.00188024 | 0.50293 | — | — | — | — | not advanced |
| unemployment | c_momentum_pm | 14 | -0.0305814 | 0.598022 | — | — | — | — | not advanced |
| unemployment | d_calibration_pm | 14 | -0.00593447 | 1 | — | — | — | — | not advanced |
| unemployment | e_late_whale_pm | 14 | -0.00425787 | 0.625 | — | — | — | — | not advanced |
| unemployment | f_uncertainty_spy | 13 | 0.0109597 | 0.444336 | — | — | — | — | not advanced |
| unemployment | h_placebo_pm | 14 | 0.0732925 | 0.264526 | — | — | — | — | not advanced |
| pooled | a_smart_pm | 31 | 0.0404957 | 0.314555 | — | — | — | — | not advanced |

## Interpretation and feasibility

PM primary metrics are after-cost mean ROI; f is the nonannualized window-Sharpe difference. Units are not comparable across those two primary classes. Detailed net means and realized volatilities are in results.csv. Rows that did not pass development have no holdout performance computed; dashes are not zeros. h is a negative control, never evidence of smart-wallet skill. The pooled hypothesis is the one registered extra test, smart PM across families.

The original common-two-horizon feasibility screen found 19/21/23/21 usable headline MoM/headline YoY/payroll/unemployment events. Per the registered exception, December 2024 MoM contributes t−1d only: the final counts are **20/21/23/21**, 85 family-events across 46 distinct release timestamps. Family raw participant rows / distinct wallets: MoM 173,861 / 11,708; YoY 401,695 / 24,338; payrolls 109,366 / 8,480; unemployment 84,407 / 7,512. Core CPI, PCE and GDP were dropped for fewer than 15 releases; see FEASIBILITY.md for market counts and gaps.

## Protocol and limitations

- Both horizons are averaged within release, then co-released families within UTC timestamp. Inference uses exact cluster permutation through 16 timestamps, otherwise 65,536 seeded draws with a plus-one correction.
- Development gate: positive primary and p<0.10. Holdout pass: positive primary and after-cost mean, Holm-adjusted one-sided p<0.05 across all advanced hypotheses. Small holdouts and multiple testing severely limit power.
- SPY ends October 7, 2026; later windows are missing, never zero. SPY holdout availability before performance was 5/5/7/6 events, so none of the included families required pooled-only SPY status. Zero-duration or post-announcement entry windows are excluded. Binary entropy is averaged over contracts, not normalized across overlapping buckets.
- Separate binary contracts can overlap. CPI extra-bracket objects are grouped as one release cluster, not independent events. Timestamp clustering does not remove dependence between nearby, overlapping SPY windows.
- Collection exhausted 128 Gamma objects / 1,041 pages / 973,256 participant records. Participant records and first-trade marks are not executable order-book quotes; $0.02/share PM and 10bp/side SPY costs are proxies.
- Gamma settlement timestamps are conservative metadata proxies; retention, keyword-search completeness, survivorship, shutdown cancellations/fallback resolutions, and a single seeded placebo limit generality.
- Calibration is frozen on development; wallet skill updates chronologically using only prior-resolved same-family markets plus FOMC. No out-of-family macro skill or future outcomes enter features.
