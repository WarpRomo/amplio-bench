# Architecture

`amplio-bench` keeps benchmark workloads, the system under test, and evaluation logic separate.

- **Amplio**: system under test. Pin an upstream revision; do not vendor it here.
- **Workload backend**: supplies evolving tasks and machine-readable verification. EvoCode is the first backend.
- **Runner**: drives task rounds. The EvoCode integration uses Harbor.
- **Adapter**: maps the runner's agent interface onto one persistent Amplio trajectory.
- **This repository**: orchestration, provenance, analysis, validity checks, compact reference results, and future backend integrations.

```text
workload + verifier
       ↓
runner
       ↓
Amplio adapter → persistent Amplio trajectory
       ↓
sandbox/workspace
       ↓
verifier outputs → metrics + audit + provenance
```

## Design rules

1. Preserve upstream verifier semantics.
2. Keep raw task correctness external to Amplio.
3. Keep infrastructure failures distinct from model/agent outcomes.
4. Treat case-level transition metrics as analysis, not replacement benchmark rewards.
5. Make every published result traceable to exact code/task revisions.
6. Avoid backend-specific assumptions in core analysis where possible.
