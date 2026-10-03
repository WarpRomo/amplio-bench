# Setup

`amplio-bench` keeps credentials and large runtime artifacts outside the repository.

## Python

Python 3.11+ is required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

The core analysis/audit package uses only the Python standard library.

Running the EvoCode/Harbor backend additionally requires compatible installations of Amplio, Harbor, the sandbox backend, and EvoCode. Those are intentionally external so benchmark runs can pin exact upstream revisions.

## Credentials

Export provider/sandbox credentials in your shell or source a private file outside the repo.

```bash
export OPENAI_API_KEY='...'
export DAYTONA_API_KEY='...'
```

`.env.example` contains variable names only. Do not commit `.env`, API keys, sandbox tokens, private traces, or proprietary task data.

Before publishing artifacts, run the secret scanner with the relevant credential environment loaded:

```bash
amplio-bench secret-scan .
```

## Harbor executable

Set the Harbor executable explicitly:

```bash
export AMPLIO_BENCH_HARBOR=/path/to/venv/bin/harbor
```

The CLI also accepts the configured command in `configs/evocode.example.toml`, but explicit executable paths are preferred for reproducible runs.

## Amplio runtime

The Harbor adapter uses the Amplio runtime supplied by the surrounding environment. Keep the runtime binary hash and source revision in provenance for benchmark results.

## Raw runs

Keep raw trajectories, sandbox artifacts, and large logs outside Git. Commit only compact, sanitized summaries under `results/`.
