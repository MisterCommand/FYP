# EventLens wallet pilot subset

Copied unchanged from https://github.com/SunnySze0000/FYP, branch
`codex/polymarket-fed-wallet-dataset`, commit
`b7f26821d10c12fdb747ad13a9db03ed672e639c`.
Only daily signals, their schema/configuration/report/target coverage and guide,
and the June market/token mapping are included. No raw trades or model binaries.
The upstream guide also describes artifacts intentionally omitted here.

EventLens applies an **uncalibrated heuristic**, not a trained probability model:
add 0.5 times the active-wallet-weighted cluster directional imbalance to each
raw market logit, then normalize across policy outcomes. Missing imbalance gives
zero tilt. Zero/one market probabilities are clipped to [1e-6, 1-1e-6].
Dates are UTC midnight cutoffs, never end-of-day. Signals are retrospective;
contemporaneous API availability and predictive value are unverified. The pilot
is provisional (37 assigned wallets), covers June 2026 only, and is not used by
scenario analysis or volatility forecasts. A later request may return a stale,
explicitly dated signal; it is not a live estimate.
