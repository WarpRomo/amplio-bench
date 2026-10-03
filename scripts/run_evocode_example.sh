#!/usr/bin/env bash
set -euo pipefail

: "${TASK:?Set TASK to an EvoCode task directory}"
: "${OUT:?Set OUT to an output directory}"
: "${MODEL:?Set MODEL to a provider/model specification}"
: "${AMPLIO_BENCH_HARBOR:?Set AMPLIO_BENCH_HARBOR to the Harbor executable}"

PYTHON=${PYTHON:-python3}

PYTHONPATH="${PYTHONPATH:-}:src" "$PYTHON" -m amplio_bench.cli run-evocode   --config configs/evocode.example.toml   --task "$TASK"   --out "$OUT"   --model "$MODEL"
