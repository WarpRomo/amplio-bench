# Roadmap

## Implemented

- persistent multi-round Amplio trajectories
- EvoCode/Harbor backend integration
- case-level progress, regressions, and recoveries
- introduced / retired / retained case tracking
- case-set and requirement churn
- structural adaptation descriptors
- released-panel case-completion and perfect-round difficulty calibration
- benchmark-wide difficulty percentiles
- run audit, verifier-isolation checks, provenance, and secret scanning
- compact validated reference-result bundles
- failure-source decomposition and released-panel case comparison
- deduplicated token/cache/tool/compaction/subagent telemetry
- opt-in Amplio-native briefing controls for harness A/B experiments

## Next research controls

- oracle-prefix isolated-round evaluation to estimate history penalty
- repeated trajectories for variance and reliability
- matched model/scaffold comparisons against released panels
- additional evolving-task backends

## Deliberately deferred

- an opaque single benchmark score
- a dashboard before the metrics and controls stabilize


## Failure-mode and coordination diagnostics

The next evaluation layer should connect external verifier symptoms to
harness-observable behavior. The repository now supports zero-cost analysis of
existing runs through failure-source decomposition, released-panel case
comparison, and deduplicated Amplio event/subagent telemetry.

Recommended sequence before paying for broader multi-agent sweeps:

1. Run the new analyzers on the existing validated reference trajectories.
2. Determine whether subagents were used naturally and whether failures align
   with tool errors, compaction, abnormal stops, or unresolved failure backlog.
3. Select one falsifiable harness intervention based on that evidence.
4. Test it on a small contrasting subset of rounds/tasks with the same model and
   verifier before broadening the suite.

A future multi-agent benchmark layer should use explicit task dependencies when
the workload provides them. Do not fabricate dependency graphs from prose only
to produce a collaboration metric.

## Native briefing A/B controls

The runner can now select Amplio-native per-run briefings while preserving the
benchmark task text. After failure/event diagnostics identify a plausible
harness-sensitive failure mode, use a small controlled A/B before broad sweeps.
A natural first multi-agent specialization control is Amplio's built-in
`second-opinion` briefing, with resolved briefing names and realized child-agent
activity checked from the event telemetry rather than assumed from config.
