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

Actual preregistration/development/holdout provenance is added after each
phase. No statistical conclusion is made by the feasibility or synthetic tests.
