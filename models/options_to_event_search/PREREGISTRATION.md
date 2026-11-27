# Round 7: option-implied index moves → prediction-market probabilities

**Registered before inspecting any real options-to-event performance.** Availability/feature construction and synthetic tests alone preceded this registration. Freeze this document and `registration.json` in Git and push before running development. No ETH/crypto data, forward test code or operational worktree is used or changed.

## Population and split

FOMC archives from #8/#11 (including complete October 2026) and the #12 headline CPI MoM/YoY, payrolls and unemployment archives only. Reuse archived settlement logic and official release timestamps. CPI MoM/YoY at the same release are one event; every contract remains a binary, including overlapping contracts. No independence or unit-sum assumption across CPI contracts.

Availability is fixed in FEASIBILITY.md, feasibility.csv, asset_coverage.csv and event_split.csv. Exact event lists, all source hashes and executable code hashes are in registration.json. There are **21/22/23/21 usable events**, respectively. The latest `ceil(.30*n)` events per family are holdout: **7 each**, with **14/15/16/14** development events. An event with either a daily, trading or t−1 snapshot is usable; specific hypothesis counts can be smaller. The seven early FOMC events without retained quotes are excluded. No further family selection.

These exact event lists and split must equal round six's committed registration. Feasibility rejects a mismatch rather than selecting a replacement population. The approved 15-minute boundary shift changes some contract/day availability counts but not event membership.

This is a new-strategy historical holdout, **not fresh data independent of earlier studies**. No pooled confirmatory test is registered.

## Two option-implied predictors, daily only

1. **VIX log change:** `log(VIX_d / VIX_previous)`.
2. **Event-volatility term-structure change:** `log(VIX9D_d / VIX_d) - log(VIX9D_previous / VIX_previous)`.

Use official CBOE `https://cdn.cboe.com/api/global/us_indices/daily_prices/{VIX,VIX9D}_History.csv`, intersected with the fixed round-six session calendar: matching **1,255 daily closes, 2021-11-26–2026-11-25**, hence **1,254 change windows**. All retained event dates are covered. No close after 2026-11-25 is used. Yahoo series are retained only as hash-pinned coverage cross-checks, not alternate predictors. Official CBOE data was selected before performance; Yahoo's VIX close differs on one original required date (2026-02-06).

**MOVE is excluded before performance**, not a third predictor: Yahoo `^MOVE` lacks nine round-six calendar dates, including five dates needed by the original feature windows; its close timing is also unclear. Do not fill its gaps, change the population to accommodate it, or add a MOVE hypothesis. This leaves **24**, not 36, confirmatory hypotheses. No hourly analysis is added.

Session dates are identical to round six, using its archived SPY response **only as a calendar**, never a predictor. **Approved timing change:** the daily predictor and PM boundary is **16:15 America/New_York**, or **13:15** on open July 3/December 24 sessions and the Friday after Thanksgiving. CBOE calculates VIX through 15:15 CT, so using its daily close at round six's 16:00 ET decision would look ahead. The user explicitly approved the 15-minute shift before preregistration and any performance. DST is handled with zoneinfo. Closed holidays/weekends have no asset window; d+1 means next exchange session. H2's release-minus-24h cutoff is unchanged and uses only a completed index window.

Use numerical units **1% log change for each predictor**, `x=raw_change/.01`. These are fixed dimensional scalings, not fitted hyperparameters or additional predictors. No clipping, signal threshold, lag search or window search.

## Timing and missing observations

For each event contract, eligible forecast closes d precede its official release. Asset input is `[d−1 session close, d session close]`. H1 PM endpoints are the **last actual normalized-YES trade at or before d close and d+1 close**. Require a fresh trade in each corresponding session interval `(previous close, current close]`; skip/count no-trade gaps rather than carrying stale prices. Deterministic timestamp ties use dedup-key order. PM target observations may extend through release, but no later than archived settlement; never impute a resolved 0/1 target in place of a trade. This makes the last pre-release daily forecast eligible even if next-session probabilities incorporate the release.

H3 uses a **separate, current-close-only eligibility set**: require the fresh baseline by d, but **do not condition entry or inclusion on a future H1 quote**. Include the last close before release. Its selected entry is the first actual trade of the selected YES/NO token **strictly after d close and strictly before official release**, even if the first such side trade is in a later session. No entry at exactly the decision timestamp; none after announcement. Use actual side price, not a complemented other-token entry.

H2 uses **official release minus 24 hours**, as in the prior event protocol. PM baseline is the last trade at or before that cutoff, at most 24h old (strictly newer than cutoff−24h). The predictor is the latest asset window **completed by** that cutoff, never that calendar day's later close. Missing fresh quotes or missing asset windows are skipped/countable, not zero-filled.

## Outcome sign mapping: development only, causal within development

For each family × asset × canonical outcome class, estimate the covariance sign between asset move and next-day Δlogit(p) using **strictly earlier resolved development events only**, with each training target's next close strictly before the current cutoff. Never use the current event, even another contract, and never use any held-out event to learn signs. Require **three distinct prior-resolved development events** in that class. This expanding, past-only rule avoids choosing a sign on the same development returns tested by the gate.

Canonicalization case-folds, removes whitespace/commas, unifies ≥/≤ with >=/<= and bps with bp. Numeric thresholds are retained, not selected by performance. CPI MoM and YoY outcome classes retain their original subtype prefix. No observation-based sign borrowing into an unseen class. Unknown/zero-covariance classes: H1 omitted; H2 stays exactly at market; H3 cash. Zero asset returns with a known class remain valid zero regressors in H1 and cash in H3.

At holdout, recompute the same registered as-of mapping from the frozen development sources alone (some older development settlements may become observable later). Holdout target signs never enter the map. No manual interpretation or sign reversal after development.

## Fixed confirmatory hypotheses: 4 families × 2 assets × 3 = 24

Each is separate; **both assets count toward multiplicity**.

### H1: lead-lag

Fit pooled daily contract rows:

`Δlogit(p_next_close) = outcome_class_fixed_effect + b * signed_scaled_asset_move + error`.

Clip probabilities only for the logit transform, to `[1e-6, 1−1e-6]`. Test **b > 0**, with the sign map defined above. OLS uses all eligible informative rows, outcome fixed effects and event-cluster CR1 standard errors (G/(G−1) × (n−1)/(n−k), k includes fixed effects and slope). One-sided p uses an event-level restricted-null wild-score sign-flip test on `Σ_event x_within*y_within`, after outcome demeaning. At ≤16 events enumerate all signs; otherwise 10,000 seeded draws plus-one. Report coefficient and clustered SE, not a trading ROI for H1. Small-cluster inference is a limitation, not a reason to substitute a more favorable p.

### H2: outcome accuracy

At each event's t−1 cutoff, fit a single family/asset coefficient:

`logit(p_adj) = logit(p_market) + beta * signed_scaled_asset_move`.

L2 is **1.0**, the #8 offset-logistic sum-loss convention, with penalty `beta²/2`. No intercept, tuning, renormalization across binary contracts or extra feature. Require three distinct prior-resolved events with informative signed inputs. Training signals themselves are constructed as of their original cutoffs. Missing training/sign maps give the exact unadjusted market probability, including 0/1 endpoints.

This is an **expanding walk-forward** coefficient: labels from an earlier event, including an earlier held-out event, may enter beta fitting **only after that contract's settlement and strictly before the current cutoff**; signs still use development only. Same-event or future labels are forbidden. This is deterministic online learning fixed before the one terminal holdout evaluation, not a new holdout selection pass.

Compute binary Brier per contract, average within event, then equal-weight events. Primary improvement is `Brier_market − Brier_adjusted` (positive better); also report adjusted-minus-market delta. Paired event bootstrap: 10,000 seeded resamples of complete event pairs; one-sided null p is the plus-one fraction of centered bootstrap means ≥ observed improvement. Report percentile 95% CI. At fewer than five test events use p=1.

### H3: trading

For each current-close opportunity, positive signed move buys YES, negative buys NO, zero/untrained stays cash. Hold to archived binary settlement. Pay **$0.02/share**: per-dollar ROI `realized_side/(entry_side_price+.02)−1`. If cost-inclusive price ≥1 or a selected pre-release entry is absent, stay cash. No position sizing optimization. All contract/day opportunities receive equal weight within event, including cash; primary statistic is mean of event means. One-sided event sign-flip p tests positive after-cost ROI (same exact/seeded algorithm as H1). This is a diagnostic of overlapping entry bets, not compounded portfolio returns.

## Placebo (not a confirmatory hypothesis)

Run the identical sign-learning, H1/H2/H3 fitting/execution and inference pipelines with another date's asset move. Both assets and all contracts at the same family/asset-window end use the same donor date. Donor is **strictly earlier**, selected by `int(SHA256(UTF8("42|"+family+"|"+str(asset_end_epoch))).hexdigest(),16) % current_zero_based_asset_window_index`. Thus the date differs and is already observable; no future donor feature. Seed is **42**. Rerun sign-learning separately for the placebo, not with the real fitted sign.

Report all development placebos, and only matching advanced main pipelines on holdout. Placebo results do **not** advance, alter the advancement set or count in Holm.

## Gate, single look, correction and provenance

- A real hypothesis advances only if its registered metric is positive and **development one-sided p < .10**. Fewer than five informative test events yields p=1. Freeze the full development results, inputs, code pins and exact advancement set in a **committed development.json** before holdout.
- Holdout is evaluated **once**, for advanced real hypotheses and their descriptive controls only. Create an exclusive retained lock **before** any holdout metric/test. Failure leaves the claim in place and blocks retries. Nonadvanced holdout performance remains uncomputed.
- Holm correction runs **across all advanced real family × asset × H hypotheses**, with no family/asset-specific reset and no placebos. A pass requires a positive same-direction metric and **one-sided Holm p < .01**. No alternate p, assets or follow-up confirmatory tests. This is **round 7** of a repeated research sequence; .01 is stricter than .05 but does not erase search history.
- Release-level inference: one pooled CPI event per release, FOMC one meeting, payrolls/unemployment one release each. Co-released families are dependent hypotheses, not extra pooled observations; Holm is valid under dependence given valid marginal p-values. No pooled strategy is added.
- RNG seed **42** throughout. Database hashes stream unchanged; text hashes normalize CRLF→LF. Existing archive DBs, source metadata, raw asset responses, feature panel, feasibility manifest, executable code and dependency code are pinned. Runtime rejects uncommitted/changed preregistration or changed pinned inputs/code. All caches are prepared **before** hashing; no source collection occurs during scoring.
- Report every development result and control, all advanced holdouts, adjusted p-values, missingness and limitations in RESULTS.md/results.csv. Never rewrite this preregistration or alter the cutoff, sign, split or hypothesis list in response to performance.
