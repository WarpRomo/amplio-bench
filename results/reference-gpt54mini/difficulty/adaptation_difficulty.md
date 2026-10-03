# Adaptation difficulty

Structural change, released-panel difficulty, and target-agent performance are reported as separate axes.

## Difficulty calibration

| R | Change | Churn | Panel case | Case β | Case diff pct | Perfect pass | Perfect diff pct | Target case | Reg | Rec |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | extension | 100.0% | 51.7% | +0.51 | 80.4% | 23.1% | 24.7% | 29.6% | — | — |
| 2 | correction | 23.8% | 64.0% | +0.09 | 60.1% | 7.7% | 63.7% | 35.8% | 4 | 0 |
| 3 | correction | 10.1% | 69.6% | -0.10 | 47.8% | 0.0% | 89.2% | 31.0% | 4 | 0 |
| 4 | correction+extension | 17.6% | 70.4% | -0.13 | 46.0% | 0.0% | 89.2% | 28.9% | 1 | 2 |
| 5 | correction+extension | 12.4% | 73.6% | -0.25 | 43.0% | 0.0% | 89.2% | 25.8% | 0 | 0 |
| 6 | extension | 7.2% | 74.5% | -0.28 | 41.6% | 0.0% | 89.2% | 25.5% | 1 | 1 |
| 7 | correction+extension | 6.3% | 71.3% | -0.16 | 45.6% | 0.0% | 89.2% | 23.9% | 2 | 1 |
| 8 | conflict | 3.6% | 69.6% | -0.10 | 48.2% | 0.0% | 89.2% | 23.0% | 0 | 0 |

Case β is an equal-weight fractional 1PL calibration over each released model's case-completion ratio. Higher β / percentile means harder for the released sequential panel.

Perfect-round difficulty uses binary reward and is retained as a secondary all-or-nothing view. It can saturate when every model misses at least one case.

Neither panel calibration is an intrinsic isolated-round difficulty estimate.

## Structural descriptors

| R | Instr words | Ref-solution lines | Verifier + | Verifier - | Active cases | +cases | -cases | Active reqs | +reqs | -reqs |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1442 | 1427 | 845 | 0 | 115 | 115 | 0 | 20 | 20 | 0 |
| 2 | 124 | 5 | 379 | 130 | 151 | 36 | 0 | 24 | 5 | 1 |
| 3 | 187 | 5 | 157 | 40 | 168 | 17 | 0 | 27 | 3 | 0 |
| 4 | 141 | 6 | 387 | 17 | 204 | 36 | 0 | 29 | 2 | 0 |
| 5 | 215 | 6 | 185 | 8 | 233 | 29 | 0 | 32 | 3 | 0 |
| 6 | 103 | 6 | 98 | 28 | 251 | 18 | 0 | 33 | 1 | 0 |
| 7 | 117 | 6 | 112 | 15 | 268 | 17 | 0 | 35 | 2 | 0 |
| 8 | 115 | 6 | 142 | 12 | 278 | 10 | 0 | 37 | 2 | 0 |

## Adaptation heterogeneity (R2+)

- **Case-set churn:** 3.6% to 23.8% (spread 20.2 pp).
- **Perfect-round panel pass:** 0.0% to 7.7% (spread 7.7 pp).
- **Panel case completion:** 64.0% to 74.5% (spread 10.4 pp).
- **Perfect-round difficulty percentile:** 63.7% to 89.2% (spread 25.6 pp).
- **Case-completion difficulty percentile:** 41.6% to 60.1% (spread 18.5 pp).
- **Case-completion β:** -0.28 to +0.09 (span 0.38).
- **Case-calibrated extremes:** easiest R6 (extension), hardest R2 (correction).
- **Highest structural churn:** R2 (correction), 23.8%.

These are descriptive measures of non-uniformity under the released sequential evaluation. The preferred causal control for history effects is an oracle-prefix isolated-round run with the same target agent.
