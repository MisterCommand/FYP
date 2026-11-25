# Crypto event search preregistration — round 4

**No strategy performance has been computed before this registration. The latest
one-third of each included family's usable events is an untouched crypto holdout.
This is search round 4: holdout alpha is 0.01, deliberately stricter than the
earlier 0.05 rule. “None found” is acceptable. No tuning after holdout.**

## Locked population and split

The included production families are BTC and ETH daily above-price ladders,
daily up/down, and hourly up/down. Each passed the committed feasibility screen
of at least 60 usable events. Weekly families do not meet the threshold. The exact
included families, every development/holdout event ID, observation timestamp,
cutoff, eligible-contract count and UTC resolution-date cluster are enumerated
in `registration.json`; its feasibility-table hashes lock the screen.

Within each family sort by the rule-derived observation timestamp, then numeric
event ID. Holdout is the latest ceil(N/3); development is the earlier remainder.
The deterministic sample was selected from Gamma metadata, not returns. No
replacement or resampling follows outcomes. Binance-compatible source rules are
required. Chainlink TWAP contracts and a misassigned hourly/weekly object remain
documented exclusions, not substituted with a different oracle. Existing FOMC
and macro results were analyzed previously; these crypto strategy outcomes were
not. Discovery/feasibility used terminal labels only for mapping and eligibility,
never strategy PnL or selection by performance.

| Family | Development events | Latest holdout events |
|---|---:|---:|
| BTC above-date | 80 | 40 |
| ETH above-date | 80 | 40 |
| BTC daily up/down | 79 | 40 |
| ETH daily up/down | 79 | 40 |
| BTC hourly up/down | 78 | 39 |
| ETH hourly up/down | 78 | 40 |

## Point-in-time information and execution

- Daily cutoff: 12 hours before the resolution-rule observation; hourly: 30
  minutes before its one-hour candle ends. Weekly would use half the stated
  observation interval, but no weekly family qualifies. These are not Gamma's
  sometimes incorrect endDate times. Noon-start 1m candles end one minute later;
  a candle explicitly closing at noon ends at noon. ET conversions observe DST.
- The last YES/Up participant price strictly before cutoff is the market
  probability. Entry is the first participant trade **strictly after** cutoff
  and strictly before the underlying observation, separately for each outcome;
  ties use the existing deterministic trade fingerprint. Both entry sides are
  required for common contract eligibility. No interpolation or stale pre-cutoff
  execution is permitted.
- Buy one outcome and hold to terminal binary settlement. Cost is the same
  **$0.02 per share** proxy as the macro search, added to entry price. Entry plus
  cost >=1 means cash. No-signal/missing-lookback means cash, not a fabricated
  trade. Return per dollar is payout/(price+cost)-1; cash is zero. The flat proxy
  is not a reconstruction of historical fee schedules, bid/ask, slippage or
  fill capacity, including markets whose Gamma fee flag is enabled.
- Flows use at most seven days strictly before cutoff. Skill uses only trades
  and conservative oracle settlement proxies strictly before cutoff: existing
  FOMC (including the previously collected fresh meeting), all macro families,
  plus the same crypto family. Never other crypto families. Earlier resolved
  holdout events may update subsequent wallet skill mechanically, as they would
  in live use; hyperparameters do not update. All collected same-family markets
  can supply historical skill even if an event fails entry/spot eligibility.
- Wallet score is prior settlement PnL/gross notional times n/(n+20), minimum
  five participant records. Select the top floor(10%), minimum 20 wallets, ties
  lexicographic. The placebo is a deterministic size-matched draw from the same
  qualified universe, seeded by 42, event ID and cutoff. Participant records are
  not unique fills or independent wallet actions.

## Seven fixed strategies (no tuning)

| ID | Rule |
|---|---|
| a_smart_pm | Buy YES/Up for positive selected-wallet signed flow; NO/Down for negative flow. |
| b_contrarian_pm | Buy opposite the sign of all-wallet flow. |
| c_momentum_pm | Buy the sign of probability change from cutoff minus the cutoff-to-observation horizon to cutoff (12h daily, 30m hourly). Missing earlier price means cash. |
| d_calibration_pm | Fit the existing penalized logistic calibration map on prior-resolved same-family events only; buy favorites p>=0.5 when calibrated q>p, or NO on longshots p<=0.1 when q<p. Minimum 3 prior events, L2=1 toward intercept 0/slope 1. |
| e_late_whale_pm | Sign of flow in trades with at least $1,000 notional, in the last 24h strictly before cutoff. |
| g_spot_pm | Digital/lognormal spot-implied probability; buy YES/Up if model minus market >0.05, NO/Down if <-0.05, otherwise cash. |
| h_placebo_pm | Same flow rule as a, with the seeded size-matched random-wallet cohort. A pass is a negative-control finding, not evidence of skill. |

The calibration feature map uses only historical cutoff probabilities with labels
available strictly before the current cutoff. It does not use numeric Gamma IDs
as chronological ordering. Development fitting walks forward; the holdout map is
frozen using development observations available before the earliest holdout
cutoff in that family. No holdout labels fit calibration.

### Registered spot model

The spot quote is the latest **completed** Binance 1m close strictly before
cutoff, at most 61 seconds old. Volatility is sample standard deviation (ddof=1)
of the 719 log returns from 720 contiguous completed hourly closes in the trailing
30-day window, multiplied by sqrt(24*365). Every included hourly close timestamp
is >=cutoff-30d and <cutoff; unfinished/future candles are excluded.

Let S be cutoff spot, K the contract's dollar threshold, sigma annualized realized
volatility, T actual seconds until observation divided by 365*86400. With zero
drift/rates, p=Phi((ln(S/K)-sigma^2*T/2)/(sigma*sqrt(T))). At zero volatility use
the deterministic S>K outcome, with 0.5 at exact equality. Daily up/down K is the
prior-day rule candle close; hourly up/down K is the rule candle's open, known
before cutoff. Only that open is used, never its later close. No terminal spot
price enters the model. Binance matches the admitted oracle; Chainlink TWAP is
not modeled by pretending that its barrier is Binance. Missing/nonpositive/
nonfinite prices, gaps or insufficient volatility history fail closed.

## Primary metric and inference

Each eligible binary contract gets an equal dollar/cash allocation within its
event. Average contract returns within event, then events within family/date,
then families within date for the pooled test. The primary metric is the mean
of these **UTC resolution observation-date portfolio ROIs after costs**. This
clusters all co-resolving events/families by date; contracts and hourly events
are not treated as independent observations. It does not remove serial or
cross-date dependence. Report cluster/event/contract/trade counts as well.
Per-family split boundaries can differ: a date in one family's development may
be in another family's holdout. No cross-crypto-family skill or calibration is
shared, but clustering within a phase cannot eliminate cross-phase correlation.

For each strategy×family use a one-sided date-cluster sign-flip test of positive
mean ROI: exact enumeration through 16 dates; otherwise 65,536 seeded draws,
seed 42, with the plus-one correction. Rank development hypotheses by their
primary metric. Advance only positive development means with p<0.10.

**One extra pooled test:** a_smart_pm across all included families, using each
family's registered development/holdout membership and the same hierarchy and
gate. There are no other pooled or alternative-cutoff tests.

Freeze development metrics, ranks, advanced IDs, fitted calibration, code/input
hashes before holdout. Claim an exclusive, retained holdout lock **before reading
holdout features or strategy returns**. Evaluate only the exact registered,
advanced strategy×family/pooled hypotheses once. All advanced hypotheses,
including placebo and the pooled test, enter one Holm family. Pass requires
the same positive sign, positive after-cost mean, and Holm-adjusted one-sided
**p<0.01**. No advancement means no strategy holdout evaluation. Failed/not-advanced
hypotheses are not tuned, replaced or rerun. A significant placebo is reported
as a negative-control warning, not a substantive edge.

## Integrity and limitations registered in advance

Registry/Markdown/coverage hashes normalize CRLF to LF; binary hashes remain byte
exact. Runtime compares registration and feasibility artifacts with this commit.
The source-fingerprinted crypto cache must match raw histories and mappings;
all prior caches are prepared before freeze hashes are taken. Holdout rejects
changed inputs and unknown/unadvanced requests before feature/return reads, and
retains its lock even after a failure. A clean new-data-root run is a separate
research execution, not permission to retry this holdout.

Missing histories, unreliable terminal settlement, insufficient prior wallets,
missing post-cutoff prices and source-incompatible/gapped spot observations were
screened before registration. Missing per-strategy lookbacks imply cash on the
common eligible sample, not favorable sample deletion. There is no SPY strategy
in this crypto round. No optional sensitivity or alternate strategy is added.

Report limitations: this is **round 4 of a search sequence**, so even alpha 0.01
does not eliminate cumulative search risk; sampled recurring series, retention,
survivorship, label-time proxies, overlapping ladders, date-to-date dependence,
one placebo, first participant prints rather than executable order-book quotes,
flat transaction costs/fee variation and a nonstationary zero-drift lognormal
model all limit interpretation. A holdout pass is evidence under this registered
model, not a guarantee of a tradable or persistent edge.
