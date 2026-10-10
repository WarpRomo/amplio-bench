#!/usr/bin/env bash
set -euo pipefail

: "${RUN_DIR:?Set RUN_DIR to the completed Amplio benchmark run}"
: "${PANEL_JSON:?Set PANEL_JSON to the released EvoCode task-result JSON}"
: "${OUT_DIR:?Set OUT_DIR to the diagnostics output directory}"

PYTHON=${PYTHON:-python3}

PYTHONPATH="${PYTHONPATH:-}:src" \
"$PYTHON" -m amplio_bench.cli diagnose-run \
  --run-dir "$RUN_DIR" \
  --panel-json "$PANEL_JSON" \
  --out-dir "$OUT_DIR"

echo "SUMMARY=$OUT_DIR/summary.md"
