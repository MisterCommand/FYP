# Round-seven checks and execution evidence

## Order and provenance

1. Fetched main after PR #15 merged: base
   `2973fe5d01cfea29d34c0fc3ac4de550e016b50d`.
2. Audited public option-index coverage without performance. The user approved
   official CBOE VIX/VIX9D, 16:15/13:15 ET boundaries, and exclusion of MOVE.
   Feasibility was committed as `acd295f`.
3. Ran the 23-test synthetic suite below. Preregistered all 24 hypotheses and
   the exact round-six events/split as
   `02ff97247f0f9961d127de61a2820f832419581e` and **pushed it before development**.
4. Ran development once; no real hypothesis advanced. Committed the complete
   development freeze as `d9fa3a39493d7673b2a457403b14e7271f32c7af`.
5. Invoked the terminal holdout command once. Its exclusive retained claim
   completed with empty results because no hypothesis advanced. **No real or
   placebo holdout performance was computed.** Holm's set is empty, not a set of
   nonsignificant p-values. Never delete/retry the retained lock.

The lock is `~/data/polymarket/options_to_event_search/holdout_lock.json`.
`execution.json` records final artifact/lock hashes and audits. All model/test
code, preregistration and registered source pins remain unchanged after the test
pass. No scoring rerun, extra predictor, alternative threshold or holdout
substitution followed the empty advancement set.

## Synthetic unit suite

```sh
/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python -m unittest discover -s models/options_to_event_search -p 'test_*.py' -v
```

```text
Ran 23 tests in 0.064s

OK
```

The 18 mirrored round-six tests cover causal signs, walk-forward labels/L2,
Brier/bootstrap, event-cluster inference, no-trade skips, entries and costs,
placebo dates, Holm/gates, pin checks, and completed/failed single-look claims.
Additional coverage checks parent creation and cached bytes, official log-change
formulas, missing/duplicate/invalid/empty index inputs, latest completed close at
a 16:10 H2 decision, and rejection of a changed round-six split. DST/early-close
assertions now require minute 15. All fixtures are synthetic, network-disabled
and temporary. Their printed holdout-pass message is not the study result.

The model and test inputs did not change after this pass; it is retained rather
than rerun after reporting-only edits. Existing research modules were used
read-only; no code outside this new directory changed.

## Availability/timing and method audit (no fitting or scoring)

```text
Input audit passed: 14737 H1 windows; 636 H2 cutoffs; 16024 H3 opportunities; causal approved-clock asset/PM/entry/donor bounds; exact round-six events/split and archive hashes; mirrored inference ASTs; no performance state.
```

Audited every real/donor feature against official index changes, all PM/entry
timestamp bounds, latest completed H2 window, and the absence of performance
state before the preregistration push. The exact split CSV is byte-identical to
round six. All reused FOMC/macro source hashes match its original registration.
AST comparison confirms unchanged population, quote/snapshot/missingness logic,
sign learning, logistic fit, regression, bootstrap, ROI, Holm and gate methods.
Only the approved predictors, fixed units, daily clock, source plumbing and
study-specific paths/reporting differ. Both scoring commands independently
validated the committed registration and current data/code pins.

## Actual execution

```text
Development frozen; advanced: none
Holdout evaluated once; lock retained. Passes: none
```

The second line is the runner's generic terminal message: with zero advanced
hypotheses it invoked no holdout evaluation pipeline and computed no performance.
All 24 holdout/control fields remain blank. No ETH/crypto data or forward-test
files/worktree were read or touched. No UI or visual verification applies.

## Post-study amendment: fresh-archive cross-check setup (PR #16)

Review at `1d536be` identified that the pinned `fetch_assets` downloads the CBOE
series and MOVE but not Yahoo `VIX.json` and `VIX9D.json`. The original study's
coverage collection had already saved both, and their hashes are in the frozen
manifest. On a fresh archive, the optional-file enumeration omits those keys;
the unchanged scoring preflight correctly rejects the incomplete source set.

The **code fix is outside the registered runner boundary**: new, unpinned
`setup_cross_checks.py`, with `test_setup_cross_checks.py`. Run it before the
archive command, as shown in README.md. It creates the directory, downloads only
missing cross-checks, verifies CRLF-normalized SHA-256 against the existing
registration, and preserves matching cached bytes. A changed cached or newly
downloaded snapshot is rejected; no historical hash is replaced. Current rolling
Yahoo responses are not guaranteed to reproduce the frozen vintage. If their
hashes differ, restore the original archived responses instead. This helper is
not a way to bypass any other pinned input or a completed study lock.

The synthetic regression reproduces the omission with the original fetcher and
the actual preflight, then demonstrates successful preflight after restoring
both exact fixture snapshots. All requests are mocked. Other fixtures cover
changed downloads/caches, network failure and missing pins. No real collector,
scorer, setup helper or study inference was run for this correction.

All pinned code bytes, `registration.json`, `development.json`, `holdout.json`,
`RESULTS.md`, `results.csv`, `execution.json`, original source snapshots and the
retained lock remain unchanged. The `CHECKS.md` hash in `execution.json` describes
the historical study document at `1d536be`, before this appended amendment;
it is intentionally not regenerated. The new setup helper and tests are not
retroactively added to the original execution's code pins.
