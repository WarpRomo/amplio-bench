# Harbor adapter

`amplio_agent.py` implements the thin Harbor-facing adapter used by `amplio-bench`.

The adapter's responsibility is intentionally narrow:

- start one Amplio trajectory for the first round
- reuse the same trajectory for later rounds
- preserve the benchmark-controlled workspace
- keep provider credentials in the host environment rather than repository files

Benchmark semantics, sandbox lifecycle, and verification remain owned by Harbor/EvoCode.
