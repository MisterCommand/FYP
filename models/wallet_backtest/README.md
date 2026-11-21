# Wallet backtest, part A: point-in-time signal panel

This is a retrospective **signal panel**, not an adjusted probability model or
evidence of incremental SPY performance. No app, forecast, or portfolio behavior
is changed. Python 3.11+ standard library only; no network requests.

```sh
python3 models/wallet_backtest/build_panel.py --data-root ~/data/polymarket
python3 -m unittest discover -s models/wallet_backtest -p 'test_*.py' -v
```

## Inputs and reproducibility

The data root is configurable. It contains `feasibility/gamma/{market_id}.json`,
`meeting_history/{event_id}/{summary,config}.json`, `page_*.json.gz` response
envelopes, and `meeting_history/SHA256SUMS`. These are the previously acquired
27-meeting Data API v2 histories, not the upstream June-only cluster sample.
The inputs were collected with `taker_only=false`, minimum size 0.01 shares.
No new collection or later-active-wallet backfill is performed here.

The default probability input is `datasets/forward_probabilities.csv`
(`--probabilities` overrides it). Decision dates come from
`app/api/calendar_dates.py::MEETINGS`. A source fingerprint covers code, calendar,
probability CSV, Gamma snapshots, collection configurations/summaries and the raw
checksum manifest. Every gzip page is verified against that manifest on ingestion;
cursor continuity, exhaustion and row/page counts are checked. Inputs are frozen:
if changing raw pages, regenerate their checksum manifest too.

The external SQLite cache defaults to
`~/data/polymarket/wallet_backtest_cache/trades.sqlite3` (`--cache` overrides it).
It is refused inside the repository. `trades` stores deduplicated participant
records; the `wallet_trades` view adds outcome/event labels. No wallet-level table
is committed. Cache reuse requires an identical source fingerprint; on intentional
input/code changes, specify a different cache path or remove the old external
cache. Incomplete `.building.sqlite3` files are never reused automatically.

The small derived outputs are:

- `panel.csv`: one row per outcome market × decision cutoff (324 expected).
- `cohorts.csv`: qualifying/selected counts, minimum selected skill, seed and
  status for each meeting/cutoff; no wallet identities.
- `settlements.csv`: CSV labels, cross-checked Gamma YES values and timestamp
  proxies, with IDs and resolution-time provenance.
- `build_manifest.csv`: source fingerprint, ingestion counts and settings.

`--output-dir` changes the derived-output directory; default is this folder.

## Definitions

**Deduplication.** SHA-256 of the canonical tuple `(market_id, transaction_hash,
wallet, token_id, side, timestamp, shares, raw_price)`, normalizing case and decimal
representations. Profile/name changes do not create new trades. Different
participants, tokens and sides remain distinct. The API supplies no log/fill ID:
identical same-wallet fills within one transaction/second cannot be distinguished
and may be collapsed. These are participant records, **not unique market fills**;
all-wallet gross notional can count both counterparties. This limitation also
affects trade-count shrinkage.

**YES-equivalent accounting.** BUY YES / SELL NO have positive signed YES
shares; SELL YES / BUY NO have negative shares. For NO trades, stored `price` is
`1 - raw_price`; for YES it is `raw_price`. Gross notional is always actual token
cost `shares * raw_price`, not synthetic YES cost. Thus the requested
`signed_yes_shares * (realized - price)` equals token-level realized trading PnL
for all four token/side combinations. Fees, inventory constraints and funding are
not modeled; this is not a reconstructed account return. Zero-cost trades count
toward trade count, but zero-total-notional wallets cannot receive a skill score.

**Settlement.** Every market must be closed in Gamma and the terminal YES/NO
prices must agree with the CSV's 0/1 label within `1e-4` (older AMM resolutions
have near-terminal prices). Each meeting must have exactly one winning outcome.
Conflicts fail the build. Resolution time is a **metadata proxy, not a verified
on-chain finalization time**: take the later of `closedTime` and `umaEndDate`,
then the latest such time across all outcome markets in that meeting. Legacy
date-only UMA values are conservatively assigned the next UTC midnight. A missing
resolution proxy fails the build. These metadata timestamps were acquired
retrospectively and their contemporaneous availability is unverified.

**Cutoffs and skill.** Decision-day UTC midnight minus 7, 3 or 1 calendar days.
For skill, both the **entire prior meeting's** resolution proxy and every included
trade must be strictly before the cutoff. No current/unresolved-meeting trade can
affect selection. Wallets need at least five deduplicated trades and positive
gross notional. Skill is

```
sum(signed_yes_shares * (realized - price)) / sum(notional) * n / (n + 20)
```

Select `floor(0.10 * n_qualifying)` wallets, highest score first; ties use wallet
address ascending. If this selects fewer than 20 (fewer than 200 qualifying
wallets), smart/placebo signals are unavailable, not expanded to 20. Scores need
not be positive. A placebo of the same size is sampled without replacement from
the **whole** qualifying population, including smart wallets, using Python's
`Random("42:event_id:cutoff_epoch")`; `--seed` overrides 42. Cohorts are shared by
all outcomes at a cutoff. The manifest records the Python version.

**Flow.** For each cohort and outcome, use only trades in
`[cutoff - 7 days, cutoff)`. Sum `sign(signed_yes_shares) * notional` divided by
gross actual-token notional. This is signed dollar flow in `[-1, 1]`, not holdings
or a probability. Each cohort has signal, net YES notional, gross notional,
deduplicated trade count and distinct active-wallet count. A covered window with
no flow has signal 0 and counts 0; unavailable smart/placebo cohorts have blank
flow fields. `n_smart` counts the selected cohort, not only active wallets.

**Market probability.** Latest CSV observation timestamp **at or before** the
cutoff (inclusive), independently per market; no interpolation or outcome
renormalization. Missing historical quotes stay blank. `probability_utc` records
the source time. `realized` is an evaluation label, never a signal input.

## Coverage and interpretation

Condition/event Data API requests serve a fixed three-year window, ignoring
requested bounds. Seven early-2023 meetings returned no served records; December
2023 is retention-clipped. A signal window starting before collection time minus
three calendar years has `window_covered=False` and **all** flow fields blank,
not a misleading zero. `window_covered` means inside the served retention range,
not independently proven complete chain history; it still excludes sub-0.01-share
trades. It does not assert complete history for skill estimation.

Historical skill is computed from available prior FOMC records, not an unbiased
full-history wallet universe. Incomplete 2023 history affects later scores too;
the first usable cohorts arrive only after enough qualifying wallets exist.
Retrospective API availability, immutable historical metadata and daily quote
publication times are unverified. Wallets are addresses, not independent people;
related wallets, market-making, fee effects, participant double-counting and
survivorship/retention bias remain limitations. Use meeting-level held-out
evaluation and market-only/placebo baselines in later parts; this panel alone
does not establish smart-wallet predictive value.
