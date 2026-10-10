# amplio-bench

A reproducible benchmark harness for evaluating **Amplio on long-horizon, evolving tasks**.

`amplio-bench` keeps the workload, runner, system under test, and analysis layers separate. EvoCode is the first supported workload; the core analysis is designed around ordered interventions, persistent agent state, and machine-readable verification rather than any one benchmark.

## What it measures

The harness reports interpretable trajectory-level signals instead of collapsing behavior into one opaque score:

- cumulative verifier case completion
- success on newly introduced cases
- retired and retained cases
- regressions and recoveries
- case-set churn across adaptations
- final per-requirement performance
- structural adaptation descriptors
- released-panel adaptation difficulty
- exact failure-source decomposition and released-panel case comparison
- deduplicated token/tool/compaction telemetry and subagent coordination signals
- run validity, provenance, and secret hygiene

For difficulty analysis, structural change, released-panel difficulty, and the target agent's observed sequential outcome are intentionally kept as separate axes.

## Architecture

```text
evolving task + verifier
        ↓
benchmark runner
        ↓
Amplio adapter
        ↓
persistent Amplio trajectory + workspace
        ↓
verifier outputs
        ↓
metrics + difficulty analysis + audit + provenance
```

For the EvoCode backend, Harbor owns round execution and the official verifier. Round 1 starts one Amplio trajectory; later extensions, corrections, and conflicts are sent into the same persistent session/workspace.

## Install

Python 3.11+ is required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
amplio-bench --help
```

The analysis and audit package uses only the Python standard library. Running EvoCode additionally requires compatible external installations of Amplio, Harbor, the sandbox backend, and EvoCode.

See [`docs/setup.md`](docs/setup.md).

## Run an EvoCode task

Set the Harbor executable explicitly:

```bash
export AMPLIO_BENCH_HARBOR=/path/to/harbor
```

Then run a persistent trajectory:

```bash
amplio-bench run-evocode \
  --config configs/evocode.example.toml \
  --task /path/to/evocode-task \
  --out runs/example \
  --model 'provider:model'
```

`scripts/run_evocode_example.sh` provides the same flow as a small portable shell wrapper.

## Analyze a trajectory

```bash
amplio-bench analyze-evocode \
  --run-dir /path/to/run \
  --out-dir /path/to/analysis
```

Outputs:

- `metrics.json`
- `round_metrics.csv`
- `final_requirements.csv`
- `summary.md`

Transition metrics use stable semantic verifier-case identity to distinguish newly introduced cases, retired cases, regressions, recoveries, and retained behavior. EvoCode's per-round ordinal `case_id` values are not treated as cross-round identities; the analyzer uses the canonical `scenario` field for trajectory matching.

## Analyze adaptation difficulty

```bash
amplio-bench analyze-difficulty \
  --task-dir /path/to/task \
  --run-dir /path/to/run \
  --panel-dir /path/to/released/task-json \
  --out-dir /path/to/difficulty
```

The analyzer reports:

- structural change: instruction/reference/verifier footprint and case/requirement churn
- released-panel case completion and perfect-round success
- benchmark-wide regularized 1PL difficulty calibration
- target trajectory case completion, regressions, and recoveries

The primary fine-grained panel calibration uses each model-round's case-completion ratio. Binary perfect-round difficulty is retained as a secondary view because it can saturate when all models miss at least one case.

These are **descriptive sequential-panel difficulty measures**, not intrinsic isolated-round difficulty. The recommended causal control is an oracle-prefix isolated-round evaluation with the same target agent.

See [`docs/ADAPTATION_DIFFICULTY.md`](docs/ADAPTATION_DIFFICULTY.md).

Optional Amplio-native per-run briefings can also be selected in the run config for controlled harness experiments; the baseline uses none.

## Diagnose failure modes and harness behavior

A completed run can be analyzed without another model call:

```bash
amplio-bench diagnose-run \
  --run-dir /path/to/run \
  --panel-json /path/to/evocode-task-result.json \
  --out-dir /path/to/diagnostics
```

The report aligns exact verifier failure sources (unresolved inherited failures,
regressions, and misses on newly introduced cases) with deduplicated Amplio
harness telemetry such as tokens, tool errors, compactions, subagent activity,
and inter-agent messages. It also compares target case failures with the released
EvoCode panel to distinguish benchmark-common weaknesses from stronger
target/scaffold/trajectory-specific candidates. These remain separate observable
axes rather than a weighted failure score.

The runner also supports optional Amplio-native per-run briefings for controlled
harness A/B experiments. The baseline uses none; configured briefing names are
validated against the selected Amplio binary before execution and recorded in
run provenance.

See [`docs/FAILURE_DIAGNOSTICS.md`](docs/FAILURE_DIAGNOSTICS.md).

## Reference results

Two validated single trajectories are checked in as compact examples of the result format:

| Workload | Rounds | Final cases | Final binary reward |
|---|---:|---:|---:|
| ML checkpoint reproducibility | 8 | 64 / 278 | 0.0 |
| Jobforge DAG runner | 9 | 5 / 34 | 0.0 |

These are **reference trajectories**, not aggregate reliability estimates or model rankings.

- [`results/reference-gpt54mini/`](results/reference-gpt54mini/)
- [`results/jobforge-dag-runner-gpt54mini/`](results/jobforge-dag-runner-gpt54mini/)

## Validity and provenance

A benchmark result is not considered valid merely because the process exits. The audit layer checks, where applicable:

1. expected verifier rounds exist exactly once
2. the runner exits successfully
3. known runtime/provider failures are absent
4. sandbox cleanup completes
5. verifier isolation is preserved across rounds
6. task, adapter, and dependency provenance are recorded
7. publishable artifacts contain no known credentials

See [`docs/VALIDITY.md`](docs/VALIDITY.md) and [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Project layout

```text
adapters/harbor/        Harbor ↔ Amplio integration
configs/                reusable run configuration
docs/                   methodology, metrics, validity, difficulty, roadmap
experiments/            guidance for retaining raw experiment evidence
results/                compact validated reference results
scripts/                portable helper scripts
src/amplio_bench/       runner, analysis, difficulty, audit, provenance
tests/                   unit and repository-hygiene tests
```

Large raw trajectories and credentials stay outside Git.

## Development

Run the zero-cost checks with:

```bash
make check
```

or directly:

```bash
PYTHONPATH=src python3 -W error -m unittest discover -s tests -v
PYTHONPATH=src python3 -W error -m compileall -q src tests
for f in scripts/*.sh; do bash -n "$f"; done
```

A live end-to-end smoke should be run before major releases when runner/adapter behavior changes.

## Scope

The current repository establishes the harness and analysis layer. The main research control not yet implemented is **oracle-prefix isolation**, which is needed to separate adaptation difficulty from the penalty of carrying an imperfect long-running history.

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## License

Apache-2.0.
