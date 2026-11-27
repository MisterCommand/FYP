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

## Post-study amendment: first-setup directory creation (PR #15)

After the study, review identified that running the archive command on a fresh setup fails when `~/data/polymarket/stock_to_event_search/` does not exist: `fetch_assets` tries to save `SPY.json` without creating its parent. A synthetic missing-nested-directory fixture reproduced `FileNotFoundError` with a mocked response and no network.

The only Python caller is `archive.py`'s own `__main__` entry point, which is hash-pinned along with `fetch_assets`. There is no existing unpinned caller in which to move directory creation. Per the approved documentation-only fallback, **keep the pinned code unchanged** and create the directory explicitly before the README's first archive command:

```sh
mkdir -p "$HOME/data/polymarket/stock_to_event_search"
/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python models/stock_to_event_search/archive.py
```

This corrects the fresh-setup procedure, not the registered model. Do not run these commands to refresh the completed study's retained snapshot or rerun its performance. The actual study already had this directory; with a pre-existing directory, the old fetch behavior remains unchanged. Synthetic verification first reproduced the failure, then created the directory outside `fetch_assets`, saved all five mocked downloads, and proved a cached rerun made no request and left all cached bytes unchanged.

Hash provenance (CRLF-normalized SHA-256):

- **Retained `archive.py`:** `03024d9b7a65b3b17b135b708f26991d6cec45dc6a9c7aef626d089e4d8d26cc`.
- The previously proposed internal `root.mkdir(parents=True, exist_ok=True)` patch would have produced **`56c03f22cd62aa47606e7bd6706a0b380a7a6153d7626853578f115771dc017e`**. That local patch was **reverted**, not committed or used to run the study. This is a candidate hash, not a replacement registered pin.
- `registration.json`, `development.json`, `execution.json`, `holdout.json`, `RESULTS.md`, `results.csv` and the retained external lock remain unchanged. No historical code/data pins were regenerated and no performance was recomputed.
- `execution.json`'s `CHECKS.md` hash intentionally describes the original study snapshot at `89699a8`, before this appended amendment. It is historical provenance, not a hash of this amended document. Git records the amendment and its new document bytes separately.
