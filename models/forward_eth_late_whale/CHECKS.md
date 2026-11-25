# Freeze and initial forward check

**Current target: N=191, about June 2027 (amendment 3).** The logs and hashes
below describe the original zero-eligible run, before that pre-scoring choice.

Freeze commit: `9b37511a6b9446c6ba8cae7a1ec06e76710429b8`.
Committer time: **2026-11-25T13:24:22Z**, Unix **1795613062**.
This commit contains the complete registration, rule, scorer and tests, before
the first real forward invocation. Later evidence commits do not move it.

Pinned `rule.py` SHA-256:
`0c41a7c3b5bdd18bc602544033223260891a330e50f30ab5ae57440752f8a9fc`.
Additional transitive implementation/collector hashes are in `registration.json`.

## Tests

```text
Ran 21 tests in 0.038s

OK
```

Coverage includes strictly-after-freeze enrollment; cutoff/expiry entry and
whale-window boundaries; notional threshold, tie-breaking and costs; zero/cash
dates; no ROI/test before N; first-N selection; exclusive claim before ROI;
completed/failed-claim retry refusal; incomplete/mismatched caches; CRLF and
registration/code changes; and historical power including cash-date variance.

## First real invocation

Dedicated detached freeze worktree:
`/home/ubuntu/repos/FYP-eth-late-whale-forward`.
Invocation as-of: **2026-11-25T13:24:45+00:00**, after the freeze.
Command:

```sh
/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python /home/ubuntu/repos/FYP-eth-late-whale-forward/models/forward_eth_late_whale/score_forward.py
```

Exit 0:

```text
Progress: n eligible=0; n traded=0; N=762; no interim look.
Test not computed; forward ROI and p-value remain undisclosed.
```

Gamma discovery archived 610 metadata-only rejected/pending events. No forward
trade histories, single-look lock or `FORWARD_RESULTS.md` exist. Persistent
progress and raw Gamma responses are under
`~/data/polymarket/forward_eth_late_whale/`. Historical crypto study files are
unchanged; no earlier market was scored as forward data.

## Current planning interpretation

N=191 counts eligible dates, **including cash**. At the observed 91/119 trade
rate, expect about 146 traded dates. The nominal endpoint is June 4, 2027;
allowing the historical 119/120 common eligibility rate gives approximately
June 6, 2027. Anthony selected this before any post-freeze data was scored to
fit his FYP, rather than the original approximately January 2029 endpoint.
Approximate power is 80% only at the full observed effect and 23% at half.
Neither calendar forecast is a stopping rule. No interim is registered.
Cron is documented, **not installed**. The original operational checkout has
not been updated or executed for this amendment; see `SCHEDULING.md` before
enabling a job. Keep the external archives/locks intact.
