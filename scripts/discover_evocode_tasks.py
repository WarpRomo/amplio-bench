#!/usr/bin/env python3
"""Discover EvoCode tasks without reading solutions or verifier source."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re
import sys
import tomllib

ML_MARKERS = ("ml", "ai", "model", "checkpoint", "inference", "pipeline")


def load_task(path: Path) -> dict:
    with (path / "task.toml").open("rb") as f:
        cfg = tomllib.load(f)
    md = cfg.get("metadata", {})
    rc = md.get("requirement_chain", {})
    chain_steps = rc.get("steps", [])
    declared = cfg.get("steps", [])
    changes = []
    for x in chain_steps:
        changes.extend(x.get("change_types", []))
    num_steps = rc.get("num_steps") or len(declared)
    name = str(md.get("name", path.name))
    category = str(md.get("category", ""))
    hay = " ".join((path.name, name, category)).lower()
    is_ml = any(re.search(rf"(^|[^a-z]){re.escape(m)}([^a-z]|$)", hay) for m in ML_MARKERS)
    # EvoCode names use mlops, so catch this explicitly.
    is_ml = is_ml or "mlops" in hay or "ml-" in hay or "_ml_" in hay
    first_instruction = ""
    if declared:
        step_name = declared[0].get("name")
        if step_name:
            p = path / "steps" / step_name / "instruction.md"
            if p.exists():
                first_instruction = " ".join(p.read_text(errors="replace").split())[:220]
    return {
        "task_dir": path.name,
        "name": name,
        "category": category,
        "difficulty": md.get("difficulty", ""),
        "rounds": int(num_steps),
        "extensions": changes.count("extension"),
        "corrections": changes.count("correction"),
        "conflicts": changes.count("conflict"),
        "is_ml": is_ml,
        "first_instruction": first_instruction,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks_dir", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    rows = []
    for toml in sorted(args.tasks_dir.rglob("task.toml")):
        # Require official task shape; skip nested/non-task config files.
        if not (toml.parent / "steps").is_dir():
            continue
        rows.append(load_task(toml.parent))

    if not rows:
        print(f"No EvoCode tasks found beneath {args.tasks_dir}", file=sys.stderr)
        return 2

    ml = [r for r in rows if r["is_ml"]]
    # Prefer manageable tasks that still contain corrections/conflicts.
    ml.sort(key=lambda r: (-(r["corrections"] + r["conflicts"]), abs(r["rounds"] - 8), r["task_dir"]))

    fields = [
        "task_dir", "name", "category", "difficulty", "rounds",
        "extensions", "corrections", "conflicts", "first_instruction",
    ]
    out = args.output.open("w", newline="") if args.output else sys.stdout
    try:
        w = csv.DictWriter(out, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(ml)
    finally:
        if args.output:
            out.close()

    print(f"tasks_total={len(rows)} ml_candidates={len(ml)}", file=sys.stderr)
    if ml:
        print(f"recommended_pilot={ml[0]['task_dir']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
