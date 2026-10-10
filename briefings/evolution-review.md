---
name: evolution-review
description: Require one fresh-context review of each evolved requirement before concluding the round.
scope: root
---

## Evolution review protocol

For every new benchmark instruction after the initial build, treat the change as
an adaptation that can invalidate assumptions made earlier in the trajectory.
Before concluding that round:

1. Implement the new requirement in the shared workspace first.
2. Spawn exactly one fresh sub-agent with `spawn_agent` to independently review
   the current workspace against the latest instruction and the accumulated
   contract. Give the reviewer the evidence and requirements, not your own
   conclusion.
3. Ask the reviewer specifically to look for: missed new requirements, stale
   assumptions from earlier rounds, regressions of previously working behavior,
   insufficient validation, and places where the implementation appears to have
   stopped adapting to the new steering.
4. Wait for the reviewer result. Address concrete findings in the workspace and
   rerun the relevant checks before concluding.

Keep implementation ownership with the root agent. The reviewer is a fresh-context
critic, not a replacement implementer. Do not recursively create reviewers from
inside a reviewer sub-agent.
