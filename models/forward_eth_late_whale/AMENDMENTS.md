# Pre-scoring implementation amendments

Original freeze remains **9b37511a6b9446c6ba8cae7a1ec06e76710429b8**, Unix
**1795613062** (2026-11-25T13:24:22Z). The original preregistration is retained
in that commit; the current document incorporates amendment 3 below.
These authorized amendments were made **before any real
post-freeze data was scored**. Only synthetic fixtures are used for validation;
no real scorer/collector invocation or post-freeze market fetch accompanies
these amendments. The original initial run enrolled zero dates.

**Current N=191**, selected by Anthony in amendment 3 before post-freeze scoring.
Alpha .01, no interim, strategy, whale threshold/window, cutoff, entry, cost,
wallet-skill definition and historical planning inputs are unchanged.

## Amendment 1 — pending settlement metadata

A closed market lacking both `closedTime` and `umaEndDate` is pending/unresolved,
not an exception that aborts the whole batch. It is listed separately in stdout
and persistent progress, is not collected/scored and does not count toward N.
Conservative settlement timestamps not yet available are also pending. A valid
timestamp in either supported field remains sufficient; malformed timestamps
still fail closed rather than being silently hidden.

The loader permits committed, explicitly declared pre-scoring rule/scorer hash
amendments while preserving the original freeze and every protocol parameter.
Registration and this amendment record must match committed bytes; changes to
other pinned dependencies or protocol parameters remain refused.

New normalized SHA-256 values:

- `rule.py`: `be36347bfcbfb2a6e46646c682af5ba816e6b2cd66b04fbfc0eea3cd791f8dfe`
- `score_forward.py`: `9b0140123b78f14438c7fd3493ffe7a32aa7f3824db9ed5dd8a186442e7662f0`

At amendments 1–2 the dedicated operational worktree was intentionally not
changed or executed while final N was pending. They did not change the study clock.

## Amendment 2 — bounded-memory hashing

Hash files in 1 MiB chunks instead of reading complete frozen databases into
memory. Binary bytes are unchanged. For the registered text suffixes, retain
CRLF-to-LF normalization even when the CR/LF pair spans two chunks; preserve a
lone trailing CR. The resulting SHA-256 is identical to the original whole-file
algorithm. Synthetic binary/text fixtures cover multiple bounded reads, empty
files, CRLF boundaries, trailing CR and read-error propagation. No real database
is read to verify this amendment, and no market is fetched or scored.

New normalized `rule.py` SHA-256:
`162ee6abcad4fe8f89f3cb60cf7bece3b320ece727288ef4be3af800251f8e41`.
At amendment 2 the scorer hash was unchanged from amendment 1, N was still 762,
and the original freeze and historical hashes were unchanged. Only the target N
and associated documentation/validation are superseded by amendment 3 below.

## Amendment 3 — Anthony's final N=191, before forward scoring

Anthony selected **N=191 eligible resolved dates** before any real post-freeze
data was scored. The only earlier real run saw **0 eligible markets**. This
choice was made for the FYP timeline: about **June 2027** rather than the
original approximately **January 2029** half-effect-powered design. The nominal
endpoint is June 4, 2027; allowing historical eligibility gives about June 6.
Approximately 146 of the 191 dates are expected to trade; cash dates still count.

**Power caveat:** N=191 gives approximately **80% power only if the full observed
effect is real**, and approximately **23% if it is half**. Normal-approximation
power using the already-registered pooled variance is .80154 and .22977,
respectively. Variance stability and independent dates are assumptions, not
guarantees. This deliberately sacrifices half-effect power for feasibility;
a null result cannot rule out that smaller effect. The historical N=762
half-effect and N=191 full-effect calculations remain in the JSON unchanged.

The original freeze commit and timestamp remain exactly those above. Alpha
remains **0.01, one-sided**, with **no interim look**, exactly one terminal look
and the same rule, cutoff, entry, cost, wallet-skill definition and every other
protocol parameter. No real scorer/collector was run and no post-freeze data
was fetched or read for this amendment. Only synthetic fixtures were tested.

The loader accepts the explicit committed Anthony 762-to-191 declaration, not
arbitrary resizing, and checks the amended preregistration against committed
bytes and its pin. The original freeze is never replaced by the amendment date.
The existing operational worktree is untouched; activate the approved amended
code before scheduling, as described in `SCHEDULING.md`.

Current normalized SHA-256 values:

- `rule.py` (unchanged): `162ee6abcad4fe8f89f3cb60cf7bece3b320ece727288ef4be3af800251f8e41`
- `score_forward.py`: `02f696a68302fc4e563549b16161a03840668d22540f4ab32bce207261e9b5e0`
- `FORWARD_PREREGISTRATION.md`: `384b259d8e357b76891b1ec2ef26c66bdf338b0ff0095bb1b7abcc754186290c`
