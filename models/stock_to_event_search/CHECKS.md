# Round-six checks and execution evidence

## Order and hashes

1. Feasibility committed as `f4f3659`; no real performance was computed.
2. Preregistration, code, tests and exact splits committed and **pushed** as `3a2c03df383f79f4039dcdae9cdee108f179b5e9` before development. 24 hypotheses; only two assets. Synthetic fixture statistics are not study performance.
3. Development ran once. Full real/control results, source hashes and the sole advancement were frozen and committed as `02ecdd9` before holdout.
4. Holdout ran once under the exclusive retained `~/data/polymarket/stock_to_event_search/holdout_lock.json`. Only `fomc/spy/H2` and its descriptive placebo were evaluated. Lock is complete and retained; do not delete it.

Development SHA-256, unchanged after holdout:

```text
b532f99f4014439571889166468aadbdc31e86c15049370c53b0b622b038627a
```

`execution.json` records the preregistration/development commits, final artifact/lock hashes and audit output. `registration.json` contains the canonical pre-performance data/code pins. Existing archive databases and all pinned source code remain unchanged. No ETH/crypto or forward-test data was read, fetched or scored; forward-test files/worktree were not touched.

## Synthetic unit suite

Command (provisioned virtualenv Python, no new dependencies):

```sh
/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python -m unittest discover -s models/stock_to_event_search -p 'test_*.py' -v
```

Final output, after the last implementation edit and before real performance:

```text
Ran 18 tests in 0.041s

OK
```

Covers exact cutoff/next-close boundaries, timestamp ties, stale-day skip counts, nonoverlapping predictor/PM windows, separate current-only trading eligibility, first later-session entries, side prices/costs/cash, DST/early closes, prior-only dev sign fitting, walk-forward prior-resolved beta (including only already-resolved earlier holdout labels), exact market fallback, L2 gradient, event-clustered H1 SE/p, paired event Brier bootstrap, equal-event weighting, deterministic past-only placebo, chronological split, Holm/gate, empty/error cases, CRLF/binary hashing, committed/pinned inputs and completed/failed single-use claims. Network is disabled and state is temporary in all fixtures. The suite prints a synthetic holdout-pass message from its lock fixture; that is not the study result.

An initial integer-array demeaning error was caught by the regression fixture and fixed before registration; the final suite above is green. No implementation or test inputs changed afterward, so that pass is retained rather than rerunning unchanged checks. Existing FOMC/macro code was imported read-only and not edited; no wider suite was needed for changed code outside this directory because there is none.

## Real-data input audit (no fitting/scoring)

```text
Input timing audit passed: 14708 H1 windows; 636 H2 cutoffs; 16006 H3 opportunities; causal asset/PM/entry/donor bounds, current-only H3 eligibility and all chronological splits agree.
```

All asset moves/donors were compared to the pinned assets. Every baseline/target/entry timestamp was checked against its causal boundary. H3 records have no future probability target; event splits are disjoint and strictly chronological. The prior macro archive build fingerprint matched the raw source fingerprint during feasibility. Both scoring invocations independently verified the registered data/code hashes before execution.

## Actual execution

```text
Development frozen; advanced: fomc/spy/H2
Holdout evaluated once; lock retained. Passes: none
```

Artifact consistency audit (does not rerun holdout inference):

```text
Holdout artifact audit passed: sole advanced FOMC/SPY/H2 and matching placebo; 7 meetings / 32 binary cutoffs; raw p=Holm p=0.039696030396960305; strict .01 bar fails; 23 other holdout hypotheses uncomputed; committed development freeze and pinned code unchanged; retained lock complete.
```

The CSV has 24 development rows and only one populated real holdout row. All 23 nonadvanced rows have empty holdout metrics/p-values. Primary H2 improvement is positive, but it fails round six's stricter preregistered threshold. No strategy change, alternate p-value, additional asset or holdout rerun followed that finding. No UI or visual verification applies.
