# Reference trajectory: GPT-5.4 Mini × EvoCode

Compact public artifacts from one validated 8-round persistent Amplio trajectory on the `ml-checkpoint-reproducibility-engine` EvoCode workload.

- Rounds: 8
- Final verifier cases: 64 / 278
- Final binary reward: 0.0
- Validation: PASS
- Scope: single trajectory, not an aggregate model ranking

Key artifacts:

- `reference_summary.csv` — concise round-by-round baseline
- `official_case_metrics.{csv,json}` — retained case-level trajectory metrics
- `generated/` — analysis regenerated from the retained run
- `difficulty/` — structural and released-panel adaptation-difficulty analysis
- `provenance.json` — path-free task/model/upstream provenance
- `validation.json` — compact validity record
- `audit/` — non-secret hashes and retained retry patch

See [`difficulty/adaptation_difficulty.md`](difficulty/adaptation_difficulty.md) for the per-round difficulty decomposition.
