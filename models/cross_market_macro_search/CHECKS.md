# Round-eight checks

## Before registration and performance

- Fetched origin/main and branched from PR #16 merge
  `783d1d3c2ed04915ae29e9a11da3e27715af7ebf`.
- Only new files under `models/cross_market_macro_search/`; existing study
  code/pins/results and forward-test files/worktree remain untouched.
- Feasibility protocol and optimistic source screen preceded the specific
  predictor audit. PCE/GDP/core CPI were excluded using release counts only.
- The exact original payroll/unemployment event lists/splits are retained.
  `source_cutoffs.csv` enumerates all 44 family-event H2 cutoffs, including
  missing source quotes. H2's four-event holdout coverage is disclosed before
  performance; its registered inference minimum is not relaxed.
- All three ETFs cover 1,255 frozen calendar sessions. Signals use regular
  exchange close, with an explicit five-minute daily decision buffer and
  the earlier completed window at morning H2 cutoffs. NYSE Arca hours and
  separate late trading/early equity closes are documented in FEASIBILITY.md.

## Synthetic tests

An initial test run exposed import-path pollution from the reused round-six
loader: generic `study` resolved to the old module. Before registration, the
new auditor was changed to restore `sys.path` after importing dependencies;
an explicit module-resolution regression test now protects this boundary.
No historical code was edited and no real scoring ran during this failure.

The 13 coverage tests passed as part of the then-complete 34-test suite:

```text
Ran 34 tests in 0.050s

OK
```

Three additional study regressions were then added (module resolution,
non-scalar H2 adjustment, successful joint-Holm advanced-only dispatch).
Latest study/input/registration/lock suite:

```text
Ran 24 tests in 0.057s

OK
```

The coverage-test dependencies did not change after their passing run. There
are now 37 synthetic tests in total; the two outputs above are the actual
runs, not a fabricated combined execution. Test progress messages about
development/holdout are from temporary synthetic fixtures, not real scoring.

Normal, empty and error cases cover source freshness and strict boundaries,
same-contract endpoints, missing-source exclusion, no source substitution,
vector Newton fit/gradient/invalid inputs, as-of development-only signs,
prior-resolved online beta fitting, market/cash fallbacks, after-cost side
entry, empty controls, event inference, gate/Holm, pin rejection, committed
development, exclusive/failure-retained lock and advanced-only dispatch.

No statistical conclusion is made by the feasibility or synthetic tests.

## Actual input timing audit

```text
Input audit passed: exact original event splits; 44 cutoff rows; 2239 H1 windows, 165 H2 cutoffs, 2643 H3 opportunities; strict predictor/source/entry/donor times and independent SQL source-delta checks agree.
Existing source hashes agree with original round-six pins; no target-performance calculation performed.
```

Final preparation after the import-isolation fix used the pinned code and
cached ETF snapshots; real network requests and performance calculations
were both zero. Its availability counts are unchanged. Sources are finite
and unfilled, all source release times follow the forecast, and independent
read-only SQL lookups reproduce Fed/CPI probability differences. The audit
checks actual selected source contracts, not only the optimistic upper bound.

## Registered execution

Preregistration **committed and pushed before real performance**:
`1d450b9343d3951a5116bd895e0a903ccab2c2b6`.
Runtime verified committed registration/preregistration and all code/data
pins before each scoring phase. No registered byte or source was changed
after registration; the preceding test passes remain applicable.

The sole real development invocation printed:

```text
Development frozen; advanced: unemployment/commodities/H1
```

All twelve results and twelve controls were frozen and committed at
`035f214ade959e0c6e286ef919ca31196764c27d` **before holdout**. Its external
freeze is byte-identical to the committed development artifact. The sole
real holdout invocation printed:

```text
Holdout evaluated once; lock retained. Passes: none
```

It evaluated **one** advanced main H1 pipeline and its matching descriptive
control: unemployment/commodities/H1. Raw/Holm p=.53125, slope
−.004783833264978504 (7 events / 376 rows), CR1 SE=.05223439872765325.
Matching placebo: slope +.021949557564610086, p=.3671875. Eleven unadvanced
holdout pipelines remain uncomputed (blank CSV fields, absent result keys),
including every combined rule, H2 and H3. No holdout ROI/Brier claim is made.

The retained external lock is
`~/data/polymarket/cross_market_macro_search/holdout_lock.json`, terminal
status `complete`; SHA-256
`a5d1fb46b13ba586d56e386362d723f8e1b05a77c38873fbebd9d0689a3826f4`.
`execution.json` links the frozen commits and result/lock hashes. No lock
was removed and no performance phase was retried. Results are null under
the registered criterion, not proof of absence of any market linkage.
