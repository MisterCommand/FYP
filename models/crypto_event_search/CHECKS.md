# Crypto research verification

All actual-data strategy performance followed preregistration commit
`93662d3c6bdf8ee271af9a2dfe3c788b12b56597`. Development was frozen and committed
in `042b8f3` before the only holdout invocation. No source, parameter, frozen
input, fitted calibration or development result changed afterward. The retained
lock and intermediate observations are external under
`~/data/polymarket/crypto/study/`.

## Unit suites

Interpreter: `/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python`.

New suite, after the final implementation edit and before actual-data execution:

```sh
$PY -m unittest discover -s models/crypto_event_search -p 'test_*.py' -v
```

```text
Ran 29 tests in 0.042s

OK
```

Coverage includes future/boundary/old volatility candles, cutoff-available spot,
known hourly open rather than its later close, missing/gapped/invalid spot,
strict model threshold, prior-only calibration independent of numeric ID order,
prior skill excluding future resolutions/trades and other crypto families,
strict cutoff/entry timing and costs, deterministic sampling/splits, ET/DST rule
mapping, incompatible oracle exclusions, normalized CRLF versus binary hashes,
stale-cache rejection, cache preparation before hashing, committed development
freeze checks, unknown/unadvanced holdout rejection and exclusive one-use locks.

The three existing suites ran during feasibility. Their files and dependencies
were unchanged by this work, so their successful runs were not repeated:

```sh
$PY -m unittest discover -s models/macro_event_search -p 'test_*.py' -v
```

```text
Ran 23 tests in 0.060s

OK
```

```sh
$PY -m unittest discover -s models/strategy_search -p 'test_*.py' -v
```

```text
Ran 13 tests in 0.021s

OK
```

```sh
$PY -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v
```

```text
Ran 32 tests in 0.077s

OK
```

Full logs: `crypto/*tests*.log`, outside git. Feasibility-only checks and source
coverage are recorded in `FEASIBILITY.md`.

## Ordered execution and freeze checks

```sh
$PY models/crypto_event_search/run_search.py develop
```

```text
Development frozen; advanced hypotheses: btc_updown_daily/h_placebo_pm, eth_updown_daily/e_late_whale_pm
```

Before the implementation/freeze commit and before any holdout execution, an
independent CSV/SQL cross-check reconstructed event/family/date weighting,
all seeded sign-flip p-values, advancement, strict first-entry prices and prior
market prices. It checked every frozen input digest and calibration freeze
cutoff against registration, without evaluating holdout strategies:

```text
Independent development audit passed: 43 metrics and seeded date-permutation p-values; 1663 strict post-cutoff binary entry pairs / 474 development events; all frozen inputs and committed-registry membership agree; no holdout lock or strategy returns exist.
```

After committing implementation and development freeze, the holdout command was
invoked **once**, with no retries, lock deletion or data-root substitution:

```sh
$PY models/crypto_event_search/run_search.py holdout
```

```text
Holdout evaluated once; lock retained. Passes: none
```

The independent holdout audit read persisted observations and execution marks,
not rerun signals/cohorts. It checked binary payoff/cost arithmetic, raw first
post-cutoff prices, membership in the advanced registered hypotheses, seeded
p-values, Holm, unadvanced blanks, and the frozen inputs/code/commit/lock hashes:

```text
Independent holdout audit passed: 80 after-cost binary ROI records / 40 dates per advanced hypothesis; first post-cutoff entry pairs, both seeded p-values and two-test Holm correction agree; other 41 hypotheses have no holdout returns; committed development freeze, all input/code hashes and retained exclusive lock agree.
```

External logs are `development.log`, `holdout.log`,
`independent_development_audit.log` and `independent_holdout_audit.log` under
the crypto data root. `development_manifest.csv` binds the external full freeze;
`study_manifest.csv` binds preregistration, freeze, retained lock and runner code.
No raw histories, wallet lists, candles, SQLite or locks were added to git.

## Placebo seed clarification

The executed event identifier is the qualified `registration.json.events` key
`family:Gamma_event_ID`, also stored as `Market.event_id` by the feasibility
mapper. `prepare` passes this key to `select_cohorts`, whose exact seed expression
is `random.Random(f"{seed}:{event_id}:{cutoff}")`. Thus the actual seed string is
`f"42:{family}:{gamma_event_id}:{cutoff}"`, not a bare-Gamma-ID-only encoding.
Sampling is without replacement from sorted qualified wallet addresses, with
the same cohort size as strategy a. This is a retrospective encoding clarification,
not a change to the pinned registration, study artifacts, seed or random draw.

Strategy h is a negative control. Its cohort cannot change a–g signals or ROIs.
It does participate in the Holm family, so changing its advancement could change
adjusted p-values; nevertheless it cannot change the a–g verdict in this study.
ETH daily late-whale is the only advanced non-control and its raw p=0.025650
exceeds the registered 0.01 threshold even before adjustment. No cohort or
holdout was recomputed for this clarification.
