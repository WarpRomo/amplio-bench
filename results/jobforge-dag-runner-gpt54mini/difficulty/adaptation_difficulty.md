# Adaptation difficulty

Structural change, released-panel difficulty, and target-agent performance are reported as separate axes.

## Difficulty calibration

| R | Change | Churn | Panel case | Case β | Case diff pct | Perfect pass | Perfect diff pct | Target case | Reg | Rec |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | extension | 100.0% | 81.4% | -0.55 | 24.4% | 53.8% | 9.0% | 6.7% | — | — |
| 2 | extension | 24.4% | 83.5% | -0.64 | 17.8% | 69.2% | 4.2% | 11.8% | 1 | 2 |
| 3 | extension | 5.9% | 78.8% | -0.45 | 27.5% | 53.8% | 7.5% | 9.4% | 3 | 2 |
| 4 | extension+correction | 3.1% | 77.2% | -0.39 | 31.5% | 46.2% | 13.2% | 22.6% | 1 | 5 |
| 5 | extension | 3.1% | 84.1% | -0.67 | 16.5% | 53.8% | 7.5% | 15.6% | 5 | 3 |
| 6 | extension | 15.6% | 81.5% | -0.56 | 23.6% | 69.2% | 4.2% | 7.4% | 3 | 0 |
| 7 | extension | 18.5% | 81.8% | -0.57 | 22.2% | 61.5% | 6.2% | 9.1% | 0 | 1 |
| 8 | extension+conflict | 42.1% | 78.5% | -0.44 | 28.0% | 61.5% | 6.2% | 18.4% | 1 | 4 |
| 9 | extension | 10.5% | 82.4% | -0.59 | 20.9% | 61.5% | 6.2% | 14.7% | 3 | 2 |

Case β is an equal-weight fractional 1PL calibration over each released model's case-completion ratio. Higher β / percentile means harder for the released sequential panel.

Perfect-round difficulty uses binary reward and is retained as a secondary all-or-nothing view. It can saturate when every model misses at least one case.

Neither panel calibration is an intrinsic isolated-round difficulty estimate.

## Structural descriptors

| R | Instr words | Ref-solution lines | Verifier + | Verifier - | Active cases | +cases | -cases | Active reqs | +reqs | -reqs |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1600 | 9 | 836 | 0 | 45 | 45 | 0 | 24 | 24 | 0 |
| 2 | 975 | 10 | 410 | 690 | 34 | 0 | 11 | 11 | 6 | 19 |
| 3 | 1077 | 10 | 267 | 309 | 32 | 0 | 2 | 14 | 6 | 3 |
| 4 | 586 | 10 | 303 | 369 | 31 | 0 | 1 | 12 | 5 | 7 |
| 5 | 601 | 10 | 419 | 295 | 32 | 1 | 0 | 13 | 8 | 7 |
| 6 | 628 | 10 | 172 | 411 | 27 | 0 | 5 | 8 | 5 | 10 |
| 7 | 479 | 10 | 176 | 166 | 22 | 0 | 5 | 8 | 5 | 5 |
| 8 | 472 | 11 | 361 | 196 | 38 | 16 | 0 | 13 | 9 | 4 |
| 9 | 373 | 10 | 283 | 324 | 34 | 0 | 4 | 11 | 3 | 5 |

## Adaptation heterogeneity (R2+)

- **Case-set churn:** 3.1% to 42.1% (spread 39.0 pp).
- **Perfect-round panel pass:** 46.2% to 69.2% (spread 23.1 pp).
- **Panel case completion:** 77.2% to 84.1% (spread 7.0 pp).
- **Perfect-round difficulty percentile:** 4.2% to 13.2% (spread 9.0 pp).
- **Case-completion difficulty percentile:** 16.5% to 31.5% (spread 15.0 pp).
- **Case-completion β:** -0.67 to -0.39 (span 0.28).
- **Case-calibrated extremes:** easiest R5 (extension), hardest R4 (extension+correction).
- **Highest structural churn:** R8 (extension+conflict), 42.1%.

These are descriptive measures of non-uniformity under the released sequential evaluation. The preferred causal control for history effects is an oracle-prefix isolated-round run with the same target agent.
