# Methodology

A run is one persistent Amplio trajectory over an evolving task. A round may extend, correct, or conflict with earlier requirements; the trajectory and workspace persist unless a backend explicitly defines otherwise.

For EvoCode, Harbor owns the environment and official verifier. The adapter starts one Amplio run for round 1 and sends later instructions into the same run/session. The verifier runs after each agent phase.

Report raw, interpretable outputs: cumulative pass count/rate, new-case success, regressions, recoveries, per-requirement results, binary benchmark reward, runtime validity, and exact provenance.

A later round may be intrinsically harder than an earlier round, so declining new-case success is an observation rather than proof of a causal horizon effect.
