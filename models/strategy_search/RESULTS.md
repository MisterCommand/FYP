# Strategy-search results

**Verdict: No preregistered strategy established a holdout edge.**

No confirmatory candidate passed the development gate, so none was evaluated on
holdout. This is a failed screening search, not evidence that every candidate
would necessarily fail out of sample. Only the permitted descriptive g control
was evaluated on the historical holdout.

**HOLDOUT DISCLOSURE: the five historical holdout meetings were used in earlier analyses of wallet-tilt strategies only. Strategies a–f were never evaluated on them, so the holdout is untouched for those strategies. g is descriptive only and excluded from the Holm family.**

The preregistration was committed before any new strategy performance computation. No parameters were tuned and no candidates were added after screening or holdout. All primary metrics are higher-is-better. PM metrics are after-cost ROI per equal-dollar market sleeve, averaged within meeting then across meetings. f is a window-Sharpe difference; g is mean after-cost excess return. Their numerical units differ.

Development ranks are within each primary-metric family, not across incomparable units.

| Strategy | Dev rank | Dev n | Dev metric | Dev one-sided p | Holdout n | Holdout metric | Holdout p | Holm p | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| a_smart_pm | 4 | 9 | -0.091650 | 0.882812 | — | — | — | — | not advanced |
| b_contrarian_pm | 6 | 9 | -0.829246 | 0.998047 | — | — | — | — | not advanced |
| c_momentum_pm | 2 | 9 | 0.004108 | 0.437500 | — | — | — | — | not advanced |
| d_calibration_pm | 1 | 9 | 0.008192 | 0.125000 | — | — | — | — | not advanced |
| e_late_whale_pm | 5 | 9 | -0.176445 | 0.976562 | — | — | — | — | not advanced |
| f_uncertainty_spy | 1 | 9 | -0.030275 | 1.000000 | — | — | — | — | not advanced |
| g_wallet_control | 1 | 9 | 1.12711e-6 | 0.500000 | 5 | 1.00015e-7 | 0.500000 | — | descriptive only |
| h_placebo_pm | 3 | 9 | -0.082493 | 0.742188 | — | — | — | — | not advanced |

## Split, fresh data and controls

Development: 2024-09, 2024-11, 2024-12, 2025-01, 2025-07, 2025-09, 2025-10, 2025-12, 2026-01. Historical holdout: 2026-03, 2026-04, 2026-06, 2026-07, 2026-09. Fresh PM holdout: October 28, 2026, event 606422 / markets 2589810–2589814. Fresh October PM collection exhausted: 175,564 participant records, 12,842 wallets, 176 pages; SPY window unavailable.

Advanced IDs: none. Non-advanced holdout performance is deliberately not calculated. g is evaluated once descriptively regardless of screening and never enters Holm. h is a negative control; a pass would be a warning, not an edge.

Development-only shuffled-signal screening frequency (100 fixed shuffles, not selectable candidates): 0.0%. This is conditional on one tiny development sample, not a general false-positive-rate estimate.

Fresh PM data are available, but no PM strategy advanced, so no October strategy
return was computed. No fresh-corroboration claim is made.

A pass without positive fresh-meeting performance is **exploratory, not independently confirmed**. Even a fresh-positive single meeting supplies corroboration, not independent statistical confirmation. The SPY CSV ends October 7, so f/g have no fresh October execution window.

## SPY volatility-timing / descriptive control

Net event-window returns include 10 bp per side times exposure for strategy and comparator. Volatility is sample std and Sharpe is not annualized. Realized second moments are in the CSV. A mechanical reduction in volatility alone is not evidence of profitable timing.

| Strategy / sample | Net mean | Comparator mean | Vol | Comparator vol | Sharpe | Comparator Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| f_uncertainty_spy / dev | 0.001324 | 0.002016 | 0.022066 | 0.022335 | 0.059983 | 0.090257 |
| f_uncertainty_spy / holdout | — | — | — | — | — | — |
| g_wallet_control / dev | 0.002227 | 0.002226 | 0.021969 | 0.021968 | 0.101379 | 0.101328 |
| g_wallet_control / holdout | -0.004333 | -0.004333 | 0.008202 | 0.008201 | -0.528344 | -0.528362 |

## Execution coverage

| Sample | Markets | Both PM token entries available | Missing token entries |
|---|---:|---:|---:|
| development | 41 | 41 | 0 |
| holdout | 28 | 28 | 0 |

## Execution, lock and limitations

PM entries use the first chosen-token participant price strictly after cutoff, before decision-day midnight, plus $0.02/share. Both token entries must exist for common execution eligibility. SPY enters at the first close strictly after cutoff, not the prior close. Execution CSVs record timestamps and missingness. Calibration and β are frozen from development for holdout; online wallet skill and scenario history use only prior-resolved/observable meetings. Parameters and exact permutation/Holm rules are in PREREGISTRATION.md.

The exclusive external holdout lock was claimed before loading holdout evaluation data and remains in place. Code/data/preregistration hashes must match the frozen development manifest. Unknown or non-advanced strategies cannot be evaluated by the holdout runner. Reports can be inspected without rerunning evaluation.

Nine development and only five old/six potential PM holdout clusters give low power and coarse exact p-values. Sign-flip symmetry / paired-swap exchangeability may fail for skewed returns, and meetings may be dependent. API retention leaves incomplete early skill history. Maker/taker participant records are not independent fills, inventory or people; deduplication is imperfect. First trade prints plus assumed costs do not prove fillable liquidity, spread, depth or impact. Momentum prices may be stale. Multiple strategies and earlier wallet-tilt exposure limit confirmatory interpretation. The 100 dev shuffles are diagnostics only.

## Reproduce (single-use holdout)

```sh
~/data/polymarket/wallet_backtest_env/bin/python models/strategy_search/search.py develop
~/data/polymarket/wallet_backtest_env/bin/python models/strategy_search/search.py holdout
~/data/polymarket/wallet_backtest_env/bin/python -m unittest discover -s models/strategy_search -p 'test_*.py' -v
```

Default external work: `~/data/polymarket/strategy_search/`. `--data-root` is configurable. A second holdout invocation refuses to run; do not remove the lock to obtain another draw. Only small derived CSVs and source/docs are committed; raw data and frozen JSON manifests remain external.
