# Metrics

`amplio-bench` reports raw, interpretable trajectory metrics. Benchmark-native binary reward is retained, but case-level analysis is used to expose partial progress and state changes that binary reward can hide.

## Per-round trajectory metrics

- **Case completion:** active verifier cases passing after the round.
- **Introduced cases:** semantic verifier cases present in round `r` but absent in `r-1`.
- **Retired cases:** semantic verifier cases present in `r-1` but absent in round `r`.
- **Retained cases:** semantic verifier cases present in both rounds.

For EvoCode, cross-round identity is derived from the canonical `scenario` field. The emitted `case_id` (`c001`, `c002`, ...) is only an ordinal within one verifier round and can be renumbered after insertions/removals; it is therefore used only for same-round joins such as released-panel failure comparison.
- **New-case success:** introduced cases passing after the adaptation.
- **Regression:** retained case passed in `r-1` and fails in `r`.
- **Recovery:** retained case failed in `r-1` and passes in `r`.
- **Stable success/failure:** retained case keeps the same status.
- **Case-set churn:** `(introduced + retired) / union(previous_cases, current_cases)`.
- **Binary reward:** benchmark-native round reward when available.

Case-set churn matters because an evolving benchmark may revise or retire requirements rather than monotonically adding tests.

## Requirement metrics

The final round is grouped by `requirement_ref` when the verifier emits it. The result records passing/failing cases and success rate for each active requirement.

## Adaptation difficulty

`analyze-difficulty` keeps three concepts separate:

1. structural adaptation load
2. released-panel sequential difficulty
3. target-agent sequential outcome

The released-panel layer reports case-completion statistics, perfect-round success, uncertainty for binary pass rate, and regularized 1PL difficulty calibrations across the supplied panel.

The case-completion 1PL is the primary fine-grained calibration because perfect-round reward can saturate on difficult tasks. It is a descriptive fractional-response model, not an official benchmark score or an intrinsic isolated-round difficulty estimate.

See [`ADAPTATION_DIFFICULTY.md`](ADAPTATION_DIFFICULTY.md).

## Token diagnostics

`metrics.py` contains token-AUC and recovery-token helpers for future use. They should only be reported when token events have a trustworthy, deduplicated identity. Cumulative snapshots must not be summed as independent token usage.


## Failure-source diagnostics

`analyze-failures` partitions active failures after the initial round into
unresolved inherited failures, regressions, and misses on newly introduced
cases. These categories are mutually exclusive and exhaustive for the current
active verifier set. The analyzer also records case lifecycles and, when given a
released EvoCode result JSON, the released-panel failure rate for the exact same
case.

## Agent and multi-agent telemetry

`analyze-agent-events` reads the cumulative Amplio event snapshots retained by
the Harbor adapter. Events are deduplicated by stable identity before counting,
so token/tool totals are not multiplied by the number of benchmark snapshots.
It reports token/cache usage, tool calls/errors, compactions, session topology,
subagent spawns, messaging/waiting activity, child outcomes, and abnormal model
stops per benchmark round and per session.

These metrics describe harness behavior. They should be used to formulate and
test interventions, not collapsed into an arbitrary overall agent-quality score.

## Harness failure-mode telemetry

The agent-event layer additionally reports raw signals useful for diagnosing
harness behavior:

- root and child tool calls separately;
- assistant turns that hit the output limit while emitting tool calls;
- invalid tool-argument errors;
- subagent terminal status and completion rate;
- children cancelled because their parent concluded;
- concluded child results followed by a later root turn.

For required-delegation experiments, `diagnose-run` reports three separate
lifecycle rates: **spawn adherence**, **completion adherence**, and **post-result
follow-up adherence**. This avoids treating a spawned-but-cancelled reviewer as a
successful intervention.

The verifier report also records **new-case capture**, **never-solved final
failure debt**, **lost-after-pass final failure debt**, and **panel-zero target
failures**. These are reported as separate interpretable axes rather than an
opaque composite score.
