# Scheduling the amended N=191 test

**N=191 resolved eligible dates; one terminal look; no interim.** Expected
completion is about **June 2027** (nominal June 4, approximately June 6 allowing
historical eligibility). About 146 dates are expected to trade. Anthony chose
this before any post-freeze data was scored to fit his FYP, instead of the
approximately January 2029 half-effect-powered design. Approximate power is
80% only if the full observed effect is real, and 23% if it is half.

The eligibility freeze remains `9b37511a6b9446c6ba8cae7a1ec06e76710429b8`,
2026-11-25T13:24:22Z. Do not move it to an amendment commit's timestamp.

## Before enabling collection

The existing dedicated worktree is still at the original freeze. It was not
updated or run during this synthetic-only amendment. After approval, update it
to the reviewed amendment commit containing N=191, keeping it detached and
preserving the external data root and locks. Check its registration says 191;
do not run the superseded original-code checkout. No cron job is installed.

## Exact command

Once the dedicated worktree contains the approved amendment:

```sh
/home/ubuntu/data/polymarket/wallet_backtest_env/bin/python /home/ubuntu/repos/FYP-eth-late-whale-forward/models/forward_eth_late_whale/score_forward.py
```

Example daily schedule at 21:15 UTC (configure the scheduler timezone to UTC):

```cron
15 21 * * * /home/ubuntu/data/polymarket/wallet_backtest_env/bin/python /home/ubuntu/repos/FYP-eth-late-whale-forward/models/forward_eth_late_whale/score_forward.py >> /home/ubuntu/data/polymarket/forward_eth_late_whale/schedule.log 2>&1
```

Keep `~/data/polymarket/forward_eth_late_whale/` persistent, outside Git. Before
191 dates the runner reports counts only, never forward ROI or p-values. At
191 it claims the retained single-look lock before evaluation. Never delete or
replace locks, resize, retry a failed claim or add an interim look.
