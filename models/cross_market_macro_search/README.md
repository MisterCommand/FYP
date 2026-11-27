# Cross-market → other macro indicators (round 8)

Tests whether Fed/CPI market probability changes plus oil/gold/copper ETF
moves predict Polymarket payrolls/unemployment probabilities. Exact design:
[FEASIBILITY.md](FEASIBILITY.md), [PREREGISTRATION.md](PREREGISTRATION.md).
Twelve hypotheses include one commodity-only group ablation. PCE, GDP and
core CPI are excluded before performance because their archived populations
are too small. H2 also has sparse pre-cutoff source coverage; see feasibility.

## Inputs and commands

Run from the repository root. The provisioned interpreter is:

```sh
PYTHON=/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python
```

Requires the existing round-six FOMC/macro SQLite and metadata archives plus
its frozen SPY calendar and NYSE-hours page, all under `~/data/polymarket/`.
The code opens those databases **read-only**. No crypto/forward-test sources
or worktrees are used. New ETF snapshots and all runtime state live under
`~/data/polymarket/cross_market_macro_search/` (created by setup).

Preparation, **before registration only**:

```sh
$PYTHON models/cross_market_macro_search/audit.py
$PYTHON models/cross_market_macro_search/inputs.py
$PYTHON -m unittest discover -s models/cross_market_macro_search -p 'test_*.py' -v
$PYTHON models/cross_market_macro_search/register_study.py
```

The first command is a label-blind optimistic coverage screen; the second
fetches only USO/GLD/CPER daily ETF responses and builds the specific-source
input panel, not performance. Both coverage artifacts and code/data hashes
must be committed in preregistration and **pushed before development**.
Never rerun input preparation after registration: any changed bytes fail
the scorer's pin checks. Raw Yahoo responses are rolling vintages: future
downloads cannot be assumed byte-identical. Reproduction of the registered
study requires the original retained snapshots, not changed hashes or an
unregistered new Yahoo vintage. Reuse of matching cached files makes no
network calls.

Registered execution:

```sh
$PYTHON models/cross_market_macro_search/study.py development
# Commit development.json and the exact advancement set before the next command.
$PYTHON models/cross_market_macro_search/study.py holdout
```

Development refuses an existing freeze. Holdout claims an exclusive retained
lock before evaluating **advanced hypotheses only**, and cannot be rerun even
after failure. With no advancement it writes empty results/controls/Holm and
does not invoke an evaluator. Do not delete locks or recreate registration
to retry. Synthetic tests use temporary data and no real network or scorer.

Outputs: `development.json`, `holdout.json`, `RESULTS.md`, `results.csv`,
execution provenance in `execution.json`, and verification in `CHECKS.md`.
The p-values are historical repeated-search diagnostics, not forward evidence
of a deployable trading edge. The terminal verdict and commit SHAs are recorded
after the registered run; no PR is opened by this workflow.
