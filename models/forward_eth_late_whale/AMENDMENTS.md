# Pre-scoring implementation amendments

Original freeze remains **9b37511a6b9446c6ba8cae7a1ec06e76710429b8**, Unix
**1795613062** (2026-11-25T13:24:22Z). The original preregistration is retained
unchanged. These authorized correctness fixes were made **before any real
post-freeze data was scored**. Only synthetic fixtures are used for validation;
no real scorer/collector invocation or post-freeze market fetch accompanies
these amendments. The original initial run enrolled zero dates.

**N remains 762**, pending a separately authorized final sample-size decision.
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

The dedicated operational worktree is intentionally not changed or executed
while the final N is pending. This amendment changes code, not the study clock.

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
The scorer hash is unchanged from amendment 1. Original freeze, N=762 and all
non-code protocol parameters and historical hashes remain unchanged.
