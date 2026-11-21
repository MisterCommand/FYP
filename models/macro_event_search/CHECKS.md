# Completed study checks

All three suites were run after the last implementation edit, before the locked holdout. No implementation or test code changed afterward.

```text
$ python -m unittest discover -s models/macro_event_search -p 'test_*.py' -v
Ran 21 tests in 0.066s

OK

$ python -m unittest discover -s models/strategy_search -p 'test_*.py' -v
Ran 13 tests in 0.032s

OK

$ python -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v
Ran 32 tests in 0.147s

OK
```

Interpreter: `~/data/polymarket/wallet_backtest_env/bin/python`.

Execution output:

```text
Development frozen; advanced hypotheses: payrolls/a_smart_pm
Holdout evaluated once; lock retained. Passes: none
```

Independent development audit reconstructed contract → horizon → family-event → timestamp aggregation and exact/Monte Carlo permutation p-values, without calling the search's metrics/permutation functions. It checked eight frozen calibration ridge gradients, all 629 development execution marks, the December 2024 MoM t−1-only exception, and the committed development manifest hash:

```text
Independent development audit passed: 29 metrics and permutation p-values; 8 frozen calibration gradients; 629 strict post-cutoff entry marks; December 2024 t-1-only exception; committed freeze hash and sole advancement agree.
```

The holdout audit independently recomputed only the executed smart-payroll hypothesis's binary-contract ROIs and eight release-cluster means, enumerated its 256 sign flips, and checked the input/development/lock hashes. It did not evaluate any additional strategy, alter the lock, or rerun the holdout command.

```text
Independent holdout audit passed: 108 binary ROI records / 8 release clusters; metric=-0.07793920519707356; exact p=Holm p=0.91015625; only the sole advanced hypothesis evaluated; frozen inputs, committed development hash and retained lock agree.
```
