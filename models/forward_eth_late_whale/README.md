# Frozen forward ETH late-whale test

Read `FORWARD_PREREGISTRATION.md` and `registration.json`. There is one rule,
one fixed N=191 and no interim, expected about June 2027. Anthony chose this
before any post-freeze data was scored, to fit his FYP; see `AMENDMENTS.md`.
Power is approximately 80% at the full observed effect, only 23% at half.
Normalized source hashes and the original Git eligibility freeze are
checked before any network collection. Historical power calculation only:

```sh
~/data/polymarket/wallet_backtest_env/bin/python models/forward_eth_late_whale/register_forward.py
```

That generator refuses to overwrite a committed registration. Never regenerate
or resize this test again. The scorer accepts only explicitly committed
amendments and refuses other changes to frozen sources/registration.

Schedule only after updating the dedicated detached worktree to the approved
N=191 amendment commit (see `SCHEDULING.md`), not the original N=762 checkout.
The worktree remains stable when the development repository switches branches.
Exact command on this machine:

```sh
/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python /home/ubuntu/repos/FYP-eth-late-whale-forward/models/forward_eth_late_whale/score_forward.py
```

For example, once daily at 21:15 UTC (set the scheduler timezone to UTC):

```cron
15 21 * * * /home/ubuntu/data/polymarket/wallet_backtest_env/bin/python /home/ubuntu/repos/FYP-eth-late-whale-forward/models/forward_eth_late_whale/score_forward.py >> /home/ubuntu/data/polymarket/forward_eth_late_whale/schedule.log 2>&1
```

This documents scheduling; it does not install a cron job. The first actual run
creates the persistent data root. Before N, `progress.json` and stdout contain
counts, never forward ROI or p-values. Missing/inconsistent archives fail closed.
Both the approved external collector and the original study archives must remain
available. At N, the exclusive retained lock is claimed before evaluation and
`FORWARD_RESULTS.md` is written in the frozen worktree. After a claimed failure,
do not delete locks, move roots or retry. A completed run is not evaluated again.

Tests (network-free):

```sh
~/data/polymarket/wallet_backtest_env/bin/python -m unittest discover -s models/forward_eth_late_whale -p 'test_*.py' -v
```
