# Methodology

A benchmark run is one persistent Amplio trajectory over an evolving task. Each round may extend, correct, or conflict with earlier requirements; the trajectory and workspace persist unless a backend explicitly defines otherwise.

For EvoCode, Harbor owns the execution environment and official verifier. The adapter starts one Amplio run for round 1 and sends later instructions into the same persistent session. The official verifier runs after every agent phase.

## Reporting principles

1. Preserve the benchmark's native verifier and binary reward.
2. Report case-level partial progress rather than treating binary reward as sufficient.
3. Distinguish infrastructure/runtime failure from agent failure.
4. Track regressions, recoveries, introduced cases, retired cases, and case-set churn.
5. Record exact task/adapter/upstream provenance for publishable runs.
6. Keep structural adaptation load, panel difficulty, and target-agent outcome separate.
7. Do not infer a causal horizon effect from later-round degradation alone.

A later round can differ in intrinsic content, verifier churn, or change type. Declining sequential performance is therefore an observation, not proof that trajectory length itself caused the decline.

## Difficulty controls

Released cross-model results provide a useful **descriptive sequential difficulty** baseline. `analyze-difficulty` calibrates each adaptation against that panel while preserving reach and case-level performance.

The stronger causal control is an **oracle-prefix isolated-round evaluation**: start the same target agent from a correct/reference workspace through round `r-1`, solve only round `r`, and compare with its sequential result.

That comparison is the preferred way to estimate a history penalty separately from adaptation difficulty.

See [`ADAPTATION_DIFFICULTY.md`](ADAPTATION_DIFFICULTY.md).
