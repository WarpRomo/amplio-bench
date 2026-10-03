# Contributing

Keep changes small, reproducible, and benchmark-focused.

- preserve upstream verifier semantics
- distinguish infrastructure failure from agent failure
- keep benchmark-native metrics separate from proposed diagnostics
- retain provenance for publishable results
- never commit credentials, private traces, raw sandbox artifacts, or machine-specific paths
- add tests for changes to metrics, audits, parsing, or calibration

Run the local checks before opening a change:

```bash
make check
```

When result artifacts change, also rerun the relevant analysis and validate the generated JSON/CSV/Markdown outputs.
