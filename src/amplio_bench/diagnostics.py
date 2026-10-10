from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import json

from .agent_metrics import analyze_agent_events, write_agent_metrics
from .failure_analysis import analyze_failures, write_failure_analysis


def diagnose_run(
    run_dir: Path,
    panel_json: Path | None = None,
) -> dict[str, Any]:
    """Join verifier failure symptoms with Amplio harness telemetry by round."""

    failures = analyze_failures(run_dir, panel_json)
    agent = analyze_agent_events(run_dir)

    agent_by_round = {row["round"]: row for row in agent["rounds"]}
    joined: list[dict[str, Any]] = []
    for failure in failures["rounds"]:
        round_number = failure["round"]
        telemetry = agent_by_round.get(round_number, {})
        joined.append(
            {
                "round": round_number,
                "cases_success": failure["cases_success"],
                "cases_fail": failure["cases_fail"],
                "inherited_failures": failure["inherited_failures"],
                "regressions": failure["regressions"],
                "adaptation_misses": failure["adaptation_misses"],
                "recoveries": failure["recoveries"],
                "introduced_cases": failure.get("introduced_cases"),
                "introduced_successes": failure.get("introduced_successes"),
                "new_case_capture_rate": failure.get("new_case_capture_rate"),
                "panel_zero_target_failures": failure.get(
                    "panel_zero_target_failures"
                ),
                "case_churn_rate": failure["case_churn_rate"],
                "tokens": telemetry.get("total_tokens"),
                "prompt_tokens": telemetry.get("prompt_tokens"),
                "assistant_turns": telemetry.get("assistant_turns"),
                "tool_calls": telemetry.get("tool_calls"),
                "root_tool_calls": telemetry.get("root_tool_calls"),
                "child_tool_calls": telemetry.get("child_tool_calls"),
                "tool_errors": telemetry.get("tool_errors"),
                "invalid_tool_argument_errors": telemetry.get("invalid_tool_argument_errors"),
                "tool_payload_truncation_turns": telemetry.get("tool_payload_truncation_turns"),
                "compactions": telemetry.get("compactions"),
                "new_subagent_sessions": telemetry.get("new_subagent_sessions"),
                "new_subagent_concluded": telemetry.get("new_subagent_concluded"),
                "new_subagent_cancelled": telemetry.get("new_subagent_cancelled"),
                "new_subagent_crashed": telemetry.get("new_subagent_crashed"),
                "parent_conclusion_cancellations": telemetry.get(
                    "parent_conclusion_cancellations"
                ),
                "concluded_child_results_with_root_followup": telemetry.get(
                    "concluded_child_results_with_root_followup"
                ),
                "spawn_agent_calls": telemetry.get("spawn_agent_calls"),
                "agent_messages": telemetry.get("agent_messages"),
                "child_results": telemetry.get("child_results"),
                "abnormal_stop_turns": telemetry.get("abnormal_stop_turns"),
                "truncated_turns": telemetry.get("truncated_turns"),
            }
        )

    manifest_path = Path(run_dir) / "run_command.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text())
            if isinstance(loaded, dict):
                manifest = loaded
        except json.JSONDecodeError:
            manifest = {}

    require_from = manifest.get("require_subagent_from_round")
    delegation: dict[str, Any] | None = None
    if isinstance(require_from, int) and require_from >= 1:
        required = [row for row in joined if row["round"] >= require_from]
        spawned = sum((row.get("new_subagent_sessions") or 0) > 0 for row in required)
        completed = sum((row.get("new_subagent_concluded") or 0) > 0 for row in required)
        followed_up = sum(
            (row.get("concluded_child_results_with_root_followup") or 0) > 0
            for row in required
        )
        delegation = {
            "required_from_round": require_from,
            "required_rounds": len(required),
            "rounds_with_new_subagent": spawned,
            "rounds_with_concluded_subagent": completed,
            "rounds_with_concluded_result_and_root_followup": followed_up,
            # Backward-compatible alias: historically `adherence` meant only spawn.
            "adherence": spawned / len(required) if required else None,
            "spawn_adherence": spawned / len(required) if required else None,
            "completion_adherence": completed / len(required) if required else None,
            "followup_adherence": followed_up / len(required) if required else None,
        }

    return {
        "run_dir": str(Path(run_dir)),
        "panel_json": str(panel_json) if panel_json is not None else None,
        "resolved_briefings": agent.get("resolved_briefings") or [],
        "delegation": delegation,
        "failures": failures,
        "agent_events": agent,
        "rounds": joined,
    }


def _fmt(value: Any) -> str:
    return "-" if value is None else str(value)


def _rate(value: Any) -> str:
    return "-" if value is None else f"{100 * float(value):.1f}%"


def write_diagnostics(result: dict[str, Any], out_dir: Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    write_failure_analysis(result["failures"], out / "failures")
    write_agent_metrics(result["agent_events"], out / "agent-events")

    compact = {
        "run_dir": result["run_dir"],
        "panel_json": result["panel_json"],
        "resolved_briefings": result["resolved_briefings"],
        "delegation": result.get("delegation"),
        "failure_summary": result["failures"].get("summary", {}),
        "harness_summary": {
            key: result["agent_events"].get("summary", {}).get(key)
            for key in (
                "root_tool_calls",
                "child_tool_calls",
                "tool_errors",
                "invalid_tool_argument_errors",
                "tool_payload_truncation_turns",
                "parent_conclusion_cancellations",
                "subagent_sessions",
                "subagent_completion_rate",
                "concluded_child_results_with_root_followup",
                "compactions",
            )
        },
        "rounds": result["rounds"],
    }
    (out / "diagnostics.json").write_text(json.dumps(compact, indent=2) + "\n")

    fields = [
        "round",
        "cases_success",
        "cases_fail",
        "inherited_failures",
        "regressions",
        "adaptation_misses",
        "recoveries",
        "introduced_cases",
        "introduced_successes",
        "new_case_capture_rate",
        "panel_zero_target_failures",
        "case_churn_rate",
        "tokens",
        "prompt_tokens",
        "assistant_turns",
        "tool_calls",
        "root_tool_calls",
        "child_tool_calls",
        "tool_errors",
        "invalid_tool_argument_errors",
        "tool_payload_truncation_turns",
        "compactions",
        "new_subagent_sessions",
        "new_subagent_concluded",
        "new_subagent_cancelled",
        "new_subagent_crashed",
        "parent_conclusion_cancellations",
        "concluded_child_results_with_root_followup",
        "spawn_agent_calls",
        "agent_messages",
        "child_results",
        "abnormal_stop_turns",
        "truncated_turns",
    ]
    with (out / "round_diagnostics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in result["rounds"]:
            writer.writerow({field: row.get(field) for field in fields})

    briefings = result.get("resolved_briefings") or []
    briefing_text = ", ".join(str(x) for x in briefings) if briefings else "none"
    lines = [
        "# Run diagnostics",
        "",
        f"Resolved run briefings: **{briefing_text}**",
    ]
    delegation = result.get("delegation")
    if delegation is not None:
        spawn_text = _rate(delegation.get("spawn_adherence"))
        completion_text = _rate(delegation.get("completion_adherence"))
        followup_text = _rate(delegation.get("followup_adherence"))
        lines.append(
            "Delegation lifecycle from "
            f"R{delegation['required_from_round']}: spawned "
            f"**{delegation['rounds_with_new_subagent']}/"
            f"{delegation['required_rounds']} ({spawn_text})**, child concluded "
            f"**{delegation['rounds_with_concluded_subagent']}/"
            f"{delegation['required_rounds']} ({completion_text})**, concluded result "
            f"followed by another root turn **"
            f"{delegation['rounds_with_concluded_result_and_root_followup']}/"
            f"{delegation['required_rounds']} ({followup_text})**."
        )
    failure_summary = result["failures"].get("summary", {})
    agent_summary = result.get("agent_events", {}).get("summary", {})
    lines.extend([
        "",
        "Final failure debt: "
        f"**{failure_summary.get('final_never_solved_failures', '-')} never solved**, "
        f"**{failure_summary.get('final_lost_after_pass_failures', '-')} lost after pass**; "
        f"panel-zero target failures: "
        f"**{failure_summary.get('final_panel_zero_target_failures', '-')}**.",
        "",
        "Harness failure signals: "
        f"**{agent_summary.get('tool_payload_truncation_turns', 0)}** "
        "tool-call turns hit the output limit, "
        f"**{agent_summary.get('invalid_tool_argument_errors', 0)}** "
        "invalid tool-argument errors, and "
        f"**{agent_summary.get('parent_conclusion_cancellations', 0)}** "
        "child sessions were cancelled because a parent concluded. "
        f"Compactions: **{agent_summary.get('compactions', 0)}**.",
        "",
        "This table aligns exact external-verifier failure sources with "
        "deduplicated Amplio harness telemetry. It is diagnostic evidence, "
        "not a causal or weighted failure score.",
        "",
        "| R | Fail | Inherited | Reg | New miss | Rec | Churn | Tokens | "
        "Root tools | Tool err | Trunc | New child | Child done | Child cancel |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in result["rounds"]:
        lines.append(
            f"| {row['round']} | {row['cases_fail']} | "
            f"{_fmt(row['inherited_failures'])} | {_fmt(row['regressions'])} | "
            f"{_fmt(row['adaptation_misses'])} | {_fmt(row['recoveries'])} | "
            f"{_rate(row['case_churn_rate'])} | {_fmt(row['tokens'])} | "
            f"{_fmt(row['root_tool_calls'])} | {_fmt(row['tool_errors'])} | "
            f"{_fmt(row['tool_payload_truncation_turns'])} | "
            f"{_fmt(row['new_subagent_sessions'])} | {_fmt(row['new_subagent_concluded'])} | "
            f"{_fmt(row['new_subagent_cancelled'])} |"
        )

    lines.extend(
        [
            "",
            "Use the nested `failures/` report for case lifecycles and released-panel "
            "comparison, and `agent-events/` for per-session/tool/subagent detail.",
        ]
    )
    (out / "summary.md").write_text("\n".join(lines) + "\n")
