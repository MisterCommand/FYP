# Stock-to-event search, round 6

Question: do SPY and close-observable rate-proxy moves predict event-market probabilities, accuracy or binary trading returns?

Read [FEASIBILITY.md](FEASIBILITY.md) and [PREREGISTRATION.md](PREREGISTRATION.md). This directory is self-contained except for read-only FOMC/macro archive loaders. Raw public asset responses and canonical feature panel live outside Git in `~/data/polymarket/stock_to_event_search/`. No crypto/forward-test data or worktree is involved.

Using `/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python`:

```sh
python models/stock_to_event_search/archive.py
python models/stock_to_event_search/register_study.py feasibility
# Commit feasibility files before registration.
python models/stock_to_event_search/register_study.py preregister
# Commit and push the preregistration and all hash-pinned code before performance.
python models/stock_to_event_search/study.py development
# Commit development.json before proceeding; do not rerun development.
python models/stock_to_event_search/study.py holdout
# Exclusive lock retained outside Git. Never delete it or rerun the holdout.
```

The first two commands are availability-only; do not refresh the registered asset snapshot or rebuild a different panel after registration. The runner validates its code/data hashes and committed preregistration. It also requires the development freeze to match Git HEAD before claiming the holdout.

Synthetic tests, with network disabled and temporary fixture state only:

```sh
python -m unittest discover -s models/stock_to_event_search -p 'test_*.py' -v
```

24 confirmatory hypotheses; exact event splits in `event_split.csv`; one-sided development gate .10; one-sided Holm holdout threshold .01. Placebos are controls, not gate/correction members. DGS2 is coverage-only because of its 16:15 publication; negative SHY is the registered second predictor. H2 is prior-settlement walk-forward (including earlier holdout labels for beta only), while outcome signs are always development-only. H3 never selects its current-day opportunities on a future PM quote.

No UI deliverable or visual verification is applicable.
