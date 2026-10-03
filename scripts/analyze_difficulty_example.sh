#!/usr/bin/env bash
set -euo pipefail

: "${TASK_DIR:?Set TASK_DIR to the benchmark task directory}"
: "${RUN_DIR:?Set RUN_DIR to the completed target-agent run}"
: "${PANEL_DIR:?Set PANEL_DIR to the released per-task panel JSON directory}"
: "${OUT_DIR:?Set OUT_DIR to the output directory}"

PYTHON=${PYTHON:-python3}

PYTHONPATH="${PYTHONPATH:-}:src" \
"$PYTHON" -m amplio_bench.cli analyze-difficulty \
  --task-dir "$TASK_DIR" \
  --run-dir "$RUN_DIR" \
  --panel-dir "$PANEL_DIR" \
  --out-dir "$OUT_DIR"
