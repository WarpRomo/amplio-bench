# Contributing

Keep changes small, reproducible, and benchmark-focused. Preserve benchmark/verifier semantics, distinguish infrastructure failure from agent failure, retain provenance, never commit credentials/private traces, and add tests for metric/audit changes.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
