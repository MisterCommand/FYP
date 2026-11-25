# Freeze and initial forward check

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

## Planning interpretation

N=762 counts eligible dates, **including cash**. At the observed 91/119 trade
rate, expect about 583 traded dates, not 762 trades. At daily eligible cadence
the nominal endpoint is December 26, 2028; allowing the historical 119/120 common
eligibility rate gives approximately January 2, 2029. Neither forecast is a
stopping rule. The full-effect N=191 calculation is not an alternative look.
No interim is registered. Cron is documented, **not installed**. Keep the
dedicated freeze worktree and the external archives/locks intact.
