# Setup

`amplio-bench` does not store provider or sandbox credentials.

## Python

Python 3.11+ is required.

Create an environment, then install the package:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

The core analysis/audit tooling uses the Python standard library.

Running the EvoCode/Harbor backend additionally requires compatible installations
of Harbor, Daytona, Amplio, and EvoCode. Those are intentionally external
dependencies because benchmark runs should pin their exact upstream revisions.

## Credentials

Export credentials in your shell or source a private file outside the repo:

```bash
export OPENAI_API_KEY='...'
export DAYTONA_API_KEY='...'
```

The repository includes `.env.example` containing variable names only.

Never commit `.env`, API keys, sandbox tokens, private traces, or proprietary task
data. `.gitignore` excludes common credential files and the publish script runs a
secret scan before committing.

## Harbor path

The CLI accepts an explicit Harbor executable through configuration or the
`AMPLIO_BENCH_HARBOR` environment variable. Do not rely on Harbor being globally
installed on `PATH`.

Example:

```bash
export AMPLIO_BENCH_HARBOR=/path/to/venv/bin/harbor
```

## Amplio runtime

The Harbor adapter can use a prebuilt Amplio binary through the environment expected
by the adapter, for example:

```bash
export AMPLIO_HOST_BIN=/path/to/amplio
```

Keep the binary hash and source revision in the run provenance.
