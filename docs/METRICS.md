# Metrics

`amplio-bench` reports raw, interpretable trajectory metrics. Benchmark-native binary reward is retained, but case-level analysis is used to expose partial progress and state changes that binary reward can hide.

## Per-round trajectory metrics

- **Case completion:** active verifier cases passing after the round.
- **Introduced cases:** case IDs present in round `r` but absent in `r-1`.
- **Retired cases:** case IDs present in `r-1` but absent in round `r`.
- **Retained cases:** case IDs present in both rounds.
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
