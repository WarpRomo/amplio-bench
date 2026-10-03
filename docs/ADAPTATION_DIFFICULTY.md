# Adaptation difficulty

Long-horizon performance at round `r` mixes at least three different effects:

1. **Structural adaptation load** — how much the specification/verifier changed.
2. **Released-panel sequential difficulty** — how difficult that round was across
   the released model panel while each model followed its own persistent trajectory.
3. **History penalty** — additional difficulty caused by inheriting the agent's own
   prior implementation/context instead of a correct prefix.

`amplio-bench` reports these separately. It does not collapse them into a
hand-weighted scalar score.

## Structural adaptation load

The analyzer records:

- change type (`extension`, `correction`, `conflict`),
- instruction size,
- reference-solution footprint,
- verifier lines added/removed,
- active / introduced / retired / retained verifier cases,
- active / introduced / retired requirements.

Case-set churn between consecutive rounds is:

`(|introduced| + |retired|) / |union(previous_cases, current_cases)|`

This captures revisions that replace or retire behavior rather than only adding tests.

## Released-panel difficulty

The current EvoCode result files provide, for each released model and round,
`pass`, `total`, `fail`, and binary `reward`.

Two complementary calibrations are reported.

### Perfect-round difficulty

A regularized 1PL model is fit to binary round rewards. This measures
all-or-nothing round difficulty after accounting for model ability. It is useful,
but it can saturate when every model misses at least one verifier case.

### Case-completion difficulty

A second regularized 1PL calibration uses each model-round's case-completion ratio
(`pass / total`) as a fractional response. Each model-round has equal weight.

This intentionally avoids letting rounds with hundreds of correlated verifier
cases dominate latent model ability merely because they contain more cases. The
result is a fine-grained **case-completion difficulty** that remains informative
when binary perfect-round reward is all zero.

Higher beta means harder for the released panel. The analyzer also reports the
difficulty percentile relative to all task-rounds in the supplied panel directory.

This fractional 1PL is a descriptive calibration, not an official EvoCode metric
and not a claim that verifier cases are independent psychometric items.

## Reach and uncertainty

For transparency the report also includes:

- models reaching the round / total panel models,
- conditional perfect-round pass rate,
- a 95% Wilson interval for binary pass rate,
- mean / median / standard deviation of case completion.

Missing later rounds are therefore visible rather than silently treated as
ordinary failures.

## Target-agent outcome

The target Amplio trajectory's case completion, regressions, and recoveries are
shown alongside the difficulty descriptors but are **not used to estimate
difficulty**.

The repo deliberately does not present a target-minus-panel residual as a
normalized performance score: the target run may use a different model and
scaffold from the released panel, so that comparison is descriptive rather than
causal.

## Causal next step: oracle-prefix history gap

To separate intrinsic adaptation difficulty from accumulated-history effects,
evaluate the same target agent on round `r` after fast-forwarding the workspace
through a correct/reference prefix ending at `r-1`.

For case completion `C`:

`history_gap(r) = C_isolated(r) - C_sequential(r)`

A large positive value means the adaptation is substantially easier from a correct
prefix than after the agent carries its own history.

The current released panel is a sequential full-chain evaluation. Oracle-prefix
isolation should therefore be run and reported as a separate experiment.
