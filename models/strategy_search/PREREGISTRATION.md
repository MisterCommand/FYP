# Strategy-search preregistration

**HOLDOUT DISCLOSURE: the five historical holdout meetings were used in earlier analyses of wallet-tilt strategies only. Strategies a–f were never evaluated on them, so the holdout is untouched for those strategies. Strategy g is descriptive only and excluded from screening/Holm claims. The placebo is a negative control, not an investable discovery.**

This document and `registration.json` must be committed before calculating any
development or holdout strategy performance. The user authorized reuse of the
previously analyzed meetings with this qualification. No new strategy performance
has been calculated at registration. There will be no strategy additions, parameter
tweaks, alternate horizons or replacement primary metrics after inspecting holdout.

## Split and data availability

The chronological universe is the 14 meetings with a usable original baseline
smart set at t−3. Development is the first nine (64%): **2024-09, 2024-11, 2024-12,
2025-01, 2025-07, 2025-09, 2025-10, 2025-12, 2026-01**. Historical holdout is the
latest five: **2026-03, 2026-04, 2026-06, 2026-07, 2026-09**. No meetings are
reassigned based on returns or entry availability. Earlier retained meetings may
contribute point-in-time wallet skill and SPY scenario history, not development
performance or calibration observations.

Fresh holdout adds **October 28, 2026**, Polymarket event **606422**, markets
**2589810–2589814**. Gamma identifies its October 27–28 FOMC meeting explicitly,
with closed markets and end date October 29. Raw collection uses the existing
external collector, approved `EventLens-research/0.1 (HKUST FYP)` User-Agent,
≤4.77 requests/sec and 429/5xx backoff. Only fully exhausted collection is usable;
failure is reported, never replaced by a different meeting. No performance is
computed during collection. The SPY CSV ends October 7, so **fresh October SPY
results are unavailable**; no synthetic return or unregistered substitute source.
The fresh meeting is additional, never a substitute for one of the five old ones.

## Shared execution, features and costs

- Only **t−3 calendar days, UTC midnight**. All selection/flow trades are strictly
  before cutoff. Baseline smart score/minimum/selection and seeded placebo are
  reused unchanged: prior fully resolved meetings, PnL/notional × n/(n+20), ≥5
  trades, top floor(10%), unavailable below 20 selected wallets. Wallet skill is
  updated online using prior-resolved history, including earlier holdout meetings;
  this is a fixed feature algorithm, not retuning a strategy or calibration fit.
- Signals use `[cutoff−7d, cutoff)` except e's last 24h. No current-market labels
  enter a signal. Zero signal means no position.
- **PM entry:** first actual participant-record trade price **strictly after**
  cutoff for the chosen YES/NO token, before decision-day midnight. Simultaneous
  records tie-break by dedup key. Require both tokens to have eligible entries for
  a market to join the common PM execution sample. Missing entries are reported
  and excluded uniformly, not replaced by pre-cutoff prices. There is no order-book
  evidence: these are hypothetical fills with corrected timing, not executable
  liquidity claims. Pay an additional **$0.02 per share**; if price + cost ≥1,
  abstain. Hold to binary settlement, net ROI = settlement/(price+.02) − 1.
- Each PM market gets one equal-dollar sleeve. Flat sleeves return zero. Compute
  per-meeting mean ROI across eligible sleeves, then mean equally across meetings.
  This avoids treating markets or participant records as independent observations.
  Also report executed sleeve count and missing-entry counts. No capital reuse or
  Kelly sizing. YES/NO direction is a directional bet, not reconstructed inventory.
- For c/d use the last YES-token trade **strictly before** cutoff and cutoff−7d
  as point-in-time trade-implied probability proxies, consistently for old and fresh
  PM markets. Missing snapshots cause abstention, not fabricated momentum. These
  can be stale and are not the EventLens daily probability observations used in f/g.
- **SPY entry:** first recorded NYSE 16:00 New York close **strictly after**
  cutoff; exit first trading-day close strictly after the decision date. No
  pre-cutoff close marking. Charge **10 bp per side × exposure** for both strategy
  and constant-exposure benchmark (20 bp roundtrip at 100%). Cash earns zero.
  Primary observations are non-overlapping meeting windows, not annualized returns.

## Fixed full strategy list (no parameter search)

`registration.json` is the machine-readable authority. There is no development
hyperparameter grid. Only the specified calibration coefficients are fitted.

| ID | Definition | Primary metric (higher is better) |
|---|---|---|
| a_smart_pm | Buy YES if original smart 7d flow >0, NO if <0 | Mean after-cost PM ROI |
| b_contrarian_pm | Buy opposite sign of original all-wallet flow; all-wallet is not verified retail | Mean after-cost PM ROI |
| c_momentum_pm | Buy YES if 7d trade-implied probability change >0, NO if <0 | Mean after-cost PM ROI |
| d_calibration_pm | Prior-only Platt map q=logistic(a+b·logit(p)); buy favorite YES when p≥.5 and q>p, fade longshot with NO when p≤.1 and q<p; otherwise flat | Mean after-cost PM ROI |
| e_late_whale_pm | Sign of net signed YES notional / gross from ≥$1,000 participant trades in last 24h; buy favored token | Mean after-cost PM ROI |
| f_uncertainty_spy | Weight .5 if normalized outcome entropy≥.5 OR fraction of markets with opposing smart/all signs≥.5, else 1; compare with constant 1 | Sharpe(strategy net) − Sharpe(constant net) |
| g_wallet_control | Original offset-logit smart adjustment and historical scenario mixtures, corrected entry, mean-variance γ=10 weights vs same-rule market weights | Mean net excess return; DESCRIPTIVE ONLY |
| h_placebo_pm | Buy token favored by original fixed-seed size-matched placebo flow | Mean after-cost PM ROI; NEGATIVE CONTROL |

Platt fit uses binary outcome rows, summed logistic loss and L2=1 centered at
(a,b)=(0,1); ≥3 prior development meetings, otherwise identity and d abstains.
Development fitting is walk-forward, excluding unresolved meetings and current/
future cutoffs. Holdout uses **one frozen final development-only** Platt fit.
g reuses λ=1 offset logistic fitting (pooled original three horizons, ≥3 prior
usable development meetings), frozen final development-only β on holdout. Its
scenario moments follow the existing prior-observable same-horizon fallback,
but historical windows also use corrected entry. f/g normalize original EventLens
outcome probabilities. Fixed constants are not tuned on holdout.

Secondary SPY metrics: mean net return, excess mean, sample volatility, realized
second moment and window Sharpe. Sharpe is mean/sample std, zero if std=0. For f,
report volatility and Sharpe against constant exposure; merely cutting volatility
does not count as an edge. For h, additionally run **100 seeded within-meeting
smart-signal permutations on development only**, reporting the fraction with
p<.10. These are not candidate strategies and cannot be advanced or selected.

## Screening, tests and pass rule

- For PM and g, one-sided **exact meeting-level sign-flip permutation** of the
  paired meeting returns against zero. Enumerate all 2^n sign patterns; p is the
  fraction of null mean statistics ≥ observed, including identity. For f, enumerate
  paired swaps of strategy/benchmark net returns within each meeting and use the
  Sharpe difference statistic. No asymptotic trade-level p-values. Null assumptions
  are sign symmetry/exchangeability and independent meetings; skewed ROI and tiny
  n can violate them and inference remains fragile.
- Advance only a–f/h with **positive dev primary metric AND one-sided dev p<.10**.
  g is always reported on holdout descriptively, never advanced or counted in Holm.
  h, if advanced, **is** counted in Holm but cannot establish a smart-wallet edge.
- Evaluate advanced strategies on the combined historical + eligible fresh
  holdout **once**, without refitting calibration. One Holm family across all
  advanced a–f/h, including unavailable evaluations as p=1. Use step-down adjusted
  one-sided p-values. Pass requires positive same-sign primary metric, **Holm
  p<.05**, and positive mean net return after the stated costs. No strategy means
  no discovery. Unavailable/not-advanced cells remain blank, not backfilled.
- Report fresh October alone descriptively for advanced PM strategies. Call a
  statistical holdout pass **“exploratory, not independently confirmed”** unless
  the same strategy also has positive after-cost mean ROI on that fresh meeting.
  A fresh-positive pass is “fresh-corroborated exploratory”; one fresh meeting is
  still not independent statistical confirmation. f has no fresh SPY validation.
- A holdout lock file is created exclusively **before** holdout data evaluation;
  re-entry is refused, even after failure. It records preregistration hash,
  development artifact/code hashes and advanced IDs. Reject strategies not listed
  in the committed registration, changed parameters or development gates. Report
  any implementation correction after locking; never silently rerun.

## Limitations fixed in advance

Only nine development and five historical holdout meetings; six PM holdout meetings
if fresh collection/execution succeeds. Holm with so few clusters has very coarse
attainable p-values. API three-year retention clips old history; later skill scores
inherit missing early trades. Maker/taker participant records are not independent
fills or people, and historical normalization/deduplication is imperfect. Costs
cannot recreate spread, market depth, gas or impact. Markets overlap within an
event and positions are correlated. Prior wallet-tilt analysis, one fresh meeting,
stale probability proxies and descriptive controls prevent broad confirmatory claims.
