# Backends

## EvoCode

First supported workload. It supplies evolving multi-round coding requirements, persistent workspace semantics, cumulative executable verification, and stable case-level outcomes.

## Adding another backend

A backend should expose ordered rounds/interventions, persistent trajectory semantics, machine-readable verification, task/verifier provenance, and stable semantic case identity (either a stable ID or enough metadata to derive one). Once case states exist, transition metrics are backend-agnostic.
