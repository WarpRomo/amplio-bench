# amplio-bench

A reproducible harness for benchmarking **Amplio on long-horizon, evolving tasks**.

The core repo is intentionally benchmark-agnostic. **EvoCode is the first supported workload**, not the definition of the project. It is useful because it provides persistent multi-round tasks with cumulative executable verification.

## What it measures

- cumulative externally verified progress
- success on newly introduced requirements
- regressions of previously passing behavior
- recoveries of previously failing behavior
- final per-requirement performance
- task / adapter / dependency provenance
- runtime validity and sandbox cleanup
- verifier isolation for multi-step Harbor runs

The repo intentionally avoids inventing one opaque "Amplio score".

## Setup and credentials

See [`docs/setup.md`](docs/setup.md).

Credentials are supplied only through environment variables/private files and are
never written into repository configuration or result manifests.

## Architecture

```text
Evolving benchmark task
        ↓
Benchmark runner + official verifier
        ↓
Thin Amplio adapter
        ↓
One persistent Amplio trajectory + workspace
        ↓
Sandbox / execution environment
```

For EvoCode, Harbor drives the rounds and official verifier. Round 1 starts one Amplio trajectory; later corrections/extensions are sent into the same session and workspace. The official cumulative verifier runs after each agent phase.

## Reference trajectory

The first checked-in reference is one validated 8-round EvoCode run with Amplio + GPT-5.4 Mini.

| Round | Passing cases | Rate | New solved | Regressions | Recoveries |
|---:|---:|---:|---:|---:|---:|
| 1 | 34 / 115 | 29.6% | — | — | — |
| 2 | 54 / 151 | 35.8% | 24 / 36 | 4 | 0 |
| 3 | 52 / 168 | 31.0% | 2 / 17 | 4 | 0 |
| 4 | 59 / 204 | 28.9% | 6 / 36 | 1 | 2 |
| 5 | 60 / 233 | 25.8% | 1 / 29 | 0 | 0 |
| 6 | 64 / 251 | 25.5% | 4 / 18 | 1 | 1 |
| 7 | 64 / 268 | 23.9% | 1 / 17 | 2 | 1 |
| 8 | 64 / 278 | 23.0% | 0 / 10 | 0 | 0 |

This is a **single reference trajectory**, not an aggregate reliability estimate or model ranking.

## Bootstrap the exact validated reference experiment

```bash
unzip amplio-bench.zip
cd amplio-bench
```

This makes **zero model/API calls**. It copies the exact validated adapter and compact result artifacts already in the reference environment, then independently re-runs this repo's tests, case analysis, run audit, provenance generation, and secret scan against the original trajectory.

## Analyze a run

```bash
PYTHONPATH=src python3 -m amplio_bench.cli analyze-evocode   --run-dir /path/to/run --out-dir /path/to/analysis
```

Outputs `metrics.json`, `round_metrics.csv`, `final_requirements.csv`, and `summary.md`.

## Audit a run

```bash
PYTHONPATH=src python3 -m amplio_bench.cli audit-run   --run-dir /path/to/run --expected-rounds 8   --harbor-root /path/to/harbor --out validation.json
```

## Provenance manifest

```bash
PYTHONPATH=src python3 -m amplio_bench.cli manifest   --task-dir /path/to/task   --adapter adapters/harbor/amplio_agent.py   --repo amplio=/path/to/amplio   --repo harbor=/path/to/harbor   --repo evocode=/path/to/EvoCodeBench   --out manifest.json
```

## Run EvoCode through Amplio

After bootstrapping the validated adapter:

```bash
PYTHONPATH=src python3 -m amplio_bench.cli run-evocode   --config configs/evocode.example.toml   --task /path/to/task --out runs/example   --model 'openai{max_tokens=2048}:gpt-5.4-mini-2026-03-17'
```

Provider credentials stay in environment variables and are never written into the run manifest.

## Validity

A result is not considered valid merely because a command exits. The audit checks, where applicable:

1. expected verifier rounds exist exactly once;
2. Harbor exits successfully;
3. known runtime/provider failures are absent;
4. sandbox cleanup completes;
5. task/code provenance is recorded;
6. Harbor clears prior verifier artifacts before the next agent phase;
7. publishable files contain no provider credentials.

See `docs/VALIDITY.md`.

## Layout

```text
adapters/harbor/        Amplio ↔ Harbor integration
configs/                reusable run configs
docs/                   methodology / metrics / validity / backends
results/                compact reference results
scripts/                bootstrap, verification, GitHub publication helpers
src/amplio_bench/       runner, analysis, audit, provenance
tests/                   unit tests
```

## License

Apache-2.0.


## Development

Run the zero-cost local checks with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m compileall -q src tests
```

A separate live integration smoke should be run before releases to exercise the
full runner → Harbor → Amplio → sandbox → verifier path.

The core package is environment-agnostic. Provider credentials, sandbox
credentials, benchmark checkouts, and runtime binaries are supplied externally
through environment variables or command-line paths.
