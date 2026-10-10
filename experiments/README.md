# Experiments

Keep large/raw run artifacts outside git. Commit compact auditable summaries under
`results/`, with enough hashes/manifests to link them back to retained raw evidence.

## Failure-driven harness experiments

Do not add a harness feature merely because it is available. Start from the
failure and agent-event diagnostics, state one mechanism that could explain the
observed weakness, then change one harness factor while keeping the task, model,
verifier, runtime, and practical budget controls fixed.

### Candidate pilot: independent verification subagent

Amplio currently exposes an opt-in `second-opinion` briefing. This is a useful
small multi-agent specialization control because it asks for independent review
without turning the coding task into a large agent team.

A first signal-finding comparison is:

```text
baseline:       briefings = []
treatment:      briefings = ["second-opinion"]
```

Before spending on the treatment, verify that the selected Amplio binary lists
the briefing. The adapter now fails fast when a configured briefing is missing.
After each run, verify realized behavior with `analyze-agent-events`; a configured
briefing is not evidence that a subagent was actually used.

Compare at least:

- per-round verifier case completion
- adaptation misses, inherited unresolved failures, regressions, and recoveries
- target failures that the released panel usually passes
- subagent spawns/results/messages and child token share
- tool errors, abnormal stops, compactions, and deduplicated token usage

Do not claim a general multi-agent improvement from a single trajectory. If the
pilot shows an informative mechanism-level signal, repeat enough runs to estimate
variance/reliability before broadening the benchmark.
