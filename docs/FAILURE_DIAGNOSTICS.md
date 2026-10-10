# Failure diagnostics

Long-horizon benchmark scores are useful for comparison, but they do not by themselves explain what should change in an agent harness. `amplio-bench` therefore keeps two diagnostic layers separate:

1. **Outcome symptoms** from the external verifier.
2. **Harness behavior** from Amplio's own event/session stream.

The goal is attribution-oriented evidence, not a new opaque score.


## One-command run diagnosis

Use the joined report when both verifier logs and Amplio raw snapshots are
available:

```bash
amplio-bench diagnose-run \
  --run-dir /path/to/run \
  --panel-json /path/to/released-task-result.json \
  --out-dir /path/to/diagnostics
```

`summary.md` and `round_diagnostics.csv` align failure-source counts with the
harness signals from the same benchmark round. The component reports remain
under `failures/` and `agent-events/` for case/session-level inspection.

## Verifier failure decomposition

For an active case in round `r > 1`, a failure is exactly one of:

- **Inherited unresolved failure:** failed in both `r-1` and `r`.
- **Regression:** passed in `r-1`, fails in `r`.
- **Adaptation miss:** the case is introduced in `r` and fails.

Recoveries are tracked separately when a retained case changes from fail to pass.
The three failure categories exactly partition active failures, so there are no weights or hand-chosen thresholds.

Run:

```bash
amplio-bench analyze-failures \
  --run-dir /path/to/run \
  --panel-json /path/to/released-task-result.json \
  --out-dir /path/to/failure-analysis
```

Outputs include:

- `round_failure_signals.csv`
- `case_lifecycles.csv`
- `target_panel_cases.csv` when a panel is supplied
- `failure_signals.json`
- `summary.md`

### Released-panel comparison

EvoCode's released task-result JSON includes exact failed verifier cases for each model/round. For every target case, the analyzer reports the fraction of reached panel models that failed the same case.

This supports a useful triage distinction:

- a target failure that almost every released model also exhibits is plausibly a broadly difficult benchmark behavior;
- a target failure that the released panel usually passes is a stronger candidate for trajectory, scaffold, tool-use, or harness investigation.

That distinction is diagnostic only. The released models use a different scaffold/model setup from the target Amplio run, so the comparison must not be presented as causal.

## Amplio event and multi-agent telemetry

The Harbor adapter saves a cumulative snapshot of the full Amplio run topology and each session's event stream after every benchmark round. Raw snapshots are cumulative, so summing each snapshot independently would overcount tool calls and token usage.

`analyze-agent-events` constructs a stable identity from session ID, event step/generation, timestamp, and typed event payload, then counts each event only on the first benchmark-round snapshot where it appears.

```bash
amplio-bench analyze-agent-events \
  --run-dir /path/to/run \
  --out-dir /path/to/agent-analysis
```

It reports per round and per session:

- prompt/completion/total token usage and cache token counts
- tool calls and tool-result errors
- context compactions
- subagent sessions and parent/child depth
- `spawn_agent`, `send_message`, `await_event`, and `session_peek` activity
- inter-agent and environment messages
- child completion/crash/cancellation results
- abnormal/truncated assistant turns and recovery events

These are descriptive system signals. They become useful for causal harness experiments only when one harness factor is changed while model, task, verifier, and budget are controlled.

## Multi-agent direction

A multi-agent evaluation should not merely compare final task success with and without more agents. Before adding a new collaboration score, retain the primitive signals required to answer:

- Did the root actually delegate work?
- How many child sessions were created, and at what depth?
- Did children complete or crash?
- Was information exchanged between sessions?
- How much compute/token budget moved to children?
- Did coordination activity occur before verifier progress, regressions, or recovery?

For benchmarks with explicit cross-agent dependency graphs, dependency-resolution metrics can be added as a benchmark-specific layer. EvoCode does not currently define those dependencies, so `amplio-bench` should not infer them from task text and present them as ground truth.

## Controlled briefing experiments

`amplio-bench` can select Amplio's native per-run briefings without changing the
benchmark task text. Configure them under `[run]`:

```toml
briefings = ["second-opinion"]
```

The default remains `briefings = []`. Selected names are recorded in
`run_command.json`, and `analyze-agent-events` reports the briefings that Amplio
actually resolved in its run detail. This matters for multi-agent experiments:
a configured organization is not evidence that the root actually delegated, so
also inspect `spawn_agent`, child-session, message, and child-result telemetry.

A useful first A/B, after diagnosing the existing runs, is baseline versus
Amplio's built-in `second-opinion` briefing. It asks for an independent review
subagent around decisions that are expensive to reverse. Keep the Amplio binary,
model, task, verifier, and budget fixed between arms. Treat an initial pair as a
signal-finding pilot rather than an aggregate reliability estimate.

## Harness failure signals

A benchmark failure and a harness failure are not the same thing. The joined
report therefore preserves several raw execution signals that can point to
fixable infrastructure or orchestration problems without assigning causal
weights:

- **Tool-payload truncation:** an assistant turn stops at the model output limit
  while emitting tool calls. This can leave a serialized tool argument
  incomplete even when the underlying task is solvable.
- **Invalid tool arguments:** a tool rejects the generated argument payload, for
  example because a truncated JSON object cannot be parsed.
- **Root vs child tool activity:** separates work done by the main trajectory
  from activity added by delegated sessions.
- **Parent-conclusion cancellation:** a child is cancelled specifically because
  its autonomous parent concluded while the child was still live.
- **Subagent completion:** distinguishes a child that was merely spawned from a
  child that actually reached `concluded`.
- **Post-result root follow-up:** records whether a concluded child result was
  followed by another root assistant turn. This is an opportunity-to-use signal,
  not proof that the root incorporated the child's advice.

These distinctions matter for controlled multi-agent experiments. "A child was
spawned" is not sufficient evidence that a review or delegated task was
completed and consumed.

## Failure debt and adaptation capture

The verifier layer also exposes two complementary long-horizon views:

- **Never-solved final debt:** final active failures that never passed in any
  earlier round.
- **Lost-after-pass final debt:** final active failures that passed previously
  and were later lost.
- **New-case capture:** the fraction of cases introduced by the current
  adaptation that pass immediately after that round.

Together with inherited failures, regressions, and recoveries, these quantities
separate failure to acquire new behavior from failure to retain old behavior.
They should remain separate rather than being combined into a weighted
"stability/plasticity" score.


## Cross-round case identity

Cross-round case identity uses EvoCode's canonical `scenario` field, not the per-round ordinal `case_id` (`c001`, `c002`, ...). Ordinal IDs are regenerated by each verifier round and can shift when cases are inserted, retired, or reordered. They remain valid for same-round released-panel joins only.
