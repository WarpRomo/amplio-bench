from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import audit_run, write_audit
from .case_metrics import analyze_run, write_analysis
from .failure_analysis import analyze_failures, write_failure_analysis
from .agent_metrics import analyze_agent_events, write_agent_metrics
from .difficulty import adaptation_difficulty, write_difficulty
from .diagnostics import diagnose_run, write_diagnostics
from .provenance import build_manifest, write_manifest
from .runner import run_evocode
from .secrets import scan_tree


def repoarg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("NAME=PATH required")
    name, path = value.split("=", 1)
    return name, Path(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amplio-bench",
        description="Long-horizon benchmarking and analysis for Amplio.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    command = sub.add_parser("analyze-evocode")
    command.add_argument("--run-dir", type=Path, required=True)
    command.add_argument("--out-dir", type=Path, required=True)

    command = sub.add_parser("audit-run")
    command.add_argument("--run-dir", type=Path, required=True)
    command.add_argument("--expected-rounds", type=int)
    command.add_argument("--harbor-root", type=Path)
    command.add_argument("--out", type=Path, required=True)

    command = sub.add_parser("manifest")
    command.add_argument("--task-dir", type=Path, required=True)
    command.add_argument("--adapter", type=Path, required=True)
    command.add_argument("--repo", action="append", default=[], type=repoarg)
    command.add_argument("--out", type=Path, required=True)

    command = sub.add_parser("secret-scan")
    command.add_argument("path", type=Path)

    command = sub.add_parser("run-evocode")
    command.add_argument("--config", type=Path, required=True)
    command.add_argument("--task", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--model", required=True)
    command.add_argument("--dry-run", action="store_true")

    command = sub.add_parser(
        "diagnose-run",
        help="Join verifier failure modes with Amplio harness telemetry.",
    )
    command.add_argument("--run-dir", type=Path, required=True)
    command.add_argument("--panel-json", type=Path)
    command.add_argument("--out-dir", type=Path, required=True)

    command = sub.add_parser(
        "analyze-failures",
        help="Decompose verifier failures and compare them with a released panel.",
    )
    command.add_argument("--run-dir", type=Path, required=True)
    command.add_argument("--panel-json", type=Path)
    command.add_argument("--out-dir", type=Path, required=True)

    command = sub.add_parser(
        "analyze-agent-events",
        help="Analyze deduplicated Amplio event/subagent telemetry.",
    )
    command.add_argument("--run-dir", type=Path, required=True)
    command.add_argument("--out-dir", type=Path, required=True)

    command = sub.add_parser(
        "analyze-difficulty",
        help="Characterize structural and released-panel difficulty by adaptation.",
    )
    command.add_argument("--task-dir", type=Path, required=True)
    command.add_argument("--run-dir", type=Path)
    command.add_argument("--panel-json", type=Path)
    command.add_argument("--panel-dir", type=Path)
    command.add_argument("--out-dir", type=Path, required=True)

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.cmd == "analyze-evocode":
        result = analyze_run(args.run_dir)
        write_analysis(result, args.out_dir)
        print(json.dumps(result, indent=2))
        return

    if args.cmd == "audit-run":
        result = audit_run(args.run_dir, args.expected_rounds, args.harbor_root)
        write_audit(result, args.out)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["validation_status"] == "PASS" else 1)

    if args.cmd == "manifest":
        result = build_manifest(args.task_dir, args.adapter, dict(args.repo))
        write_manifest(result, args.out)
        print(json.dumps(result, indent=2))
        return

    if args.cmd == "secret-scan":
        hits = scan_tree(args.path)
        print("SECRET_SCAN=PASS" if not hits else json.dumps(hits, indent=2))
        raise SystemExit(0 if not hits else 1)

    if args.cmd == "run-evocode":
        raise SystemExit(
            run_evocode(
                args.config,
                args.task,
                args.out,
                args.model,
                args.dry_run,
            )
        )

    if args.cmd == "diagnose-run":
        result = diagnose_run(args.run_dir, args.panel_json)
        write_diagnostics(result, args.out_dir)
        print(json.dumps({
            "run_dir": result["run_dir"],
            "resolved_briefings": result["resolved_briefings"],
            "rounds": result["rounds"],
        }, indent=2))
        return

    if args.cmd == "analyze-failures":
        result = analyze_failures(args.run_dir, args.panel_json)
        write_failure_analysis(result, args.out_dir)
        print(json.dumps(result, indent=2))
        return

    if args.cmd == "analyze-agent-events":
        result = analyze_agent_events(args.run_dir)
        write_agent_metrics(result, args.out_dir)
        print(json.dumps(result, indent=2))
        return

    if args.cmd == "analyze-difficulty":
        result = adaptation_difficulty(
            args.task_dir,
            args.run_dir,
            args.panel_json,
            args.panel_dir,
        )
        write_difficulty(result, args.out_dir)
        print(json.dumps(result, indent=2))
        return

    raise AssertionError(f"unhandled command: {args.cmd}")


if __name__ == "__main__":
    main()
