# Metrics

- **Cumulative success:** cumulative verifier cases passing after a round.
- **New-case success:** newly introduced cases that pass after the new steering.
- **Regression:** a case that passed in `r-1` and fails in `r`.
- **Recovery:** a case that failed in `r-1` and passes in `r`.
- **Stable success/failure:** unchanged behavior across consecutive rounds.
- **Binary reward:** retained exactly when the benchmark exposes it; it does not replace case-level partial progress.

The original project's task-level token-AUC helpers remain in `metrics.py` for compatibility, but are diagnostics rather than official EvoCode metrics.
