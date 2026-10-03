# Reference trajectory: GPT-5.4 Mini × EvoCode

This directory contains the compact public result from one validated 8-round,
persistent Amplio trajectory on an evolving EvoCode task.

The result is included as a reference for the benchmark format, not as a model
leaderboard claim.

Included artifacts:

- `reference_summary.csv` — concise round-by-round result
- `official_case_metrics.{csv,json}` — case-level trajectory metrics
- `generated/` — analysis regenerated from the retained run
- `provenance.json` — path-free task/model/upstream provenance
- `validation.json` — compact run-validity record
- `audit/` — non-secret hashes and the transport-only retry patch

No machine hostname, user home, credentials, or absolute execution paths are
included in the public result.
