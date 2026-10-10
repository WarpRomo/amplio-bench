from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
import csv
import hashlib
import json
import re


SNAPSHOT_RE = re.compile(r"amplio-round-(\d+)-run\.json$")


def _json(path: Path) -> Any:
    return json.loads(Path(path).read_text())


def _safe_session_id(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", session_id)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_snapshot(paths: list[Path], round_number: int) -> Path:
    if len(paths) == 1:
        return paths[0]

    by_hash: dict[str, list[Path]] = {}
    for path in paths:
        by_hash.setdefault(_file_sha256(path), []).append(path)

    if len(by_hash) != 1:
        details = ", ".join(
            f"{digest[:12]}:{len(group)}"
            for digest, group in sorted(by_hash.items())
        )
        raise ValueError(
            f"conflicting Amplio run snapshots for round {round_number}: {details}"
        )

    # Harbor's durable log download may preserve the same cumulative snapshot in
    # several nested locations across resume rounds. Once byte identity is proven,
    # prefer the shallowest path so adjacent session-event files are resolved from
    # the least-nested canonical copy.
    return min(paths, key=lambda path: (len(path.parts), len(str(path)), str(path)))


def discover_snapshots(run_dir: Path) -> dict[int, Path]:
    found: dict[int, list[Path]] = {}
    for path in Path(run_dir).rglob("amplio-round-*-run.json"):
        match = SNAPSHOT_RE.search(path.name)
        if not match:
            continue
        round_number = int(match.group(1))
        found.setdefault(round_number, []).append(path)

    return {
        round_number: _canonical_snapshot(paths, round_number)
        for round_number, paths in found.items()
    }


def _event_file(run_file: Path, round_number: int, session_id: str) -> Path | None:
    safe = _safe_session_id(session_id)
    expected = run_file.with_name(
        f"amplio-round-{round_number:02d}-session-{safe}-events.json"
    )
    if expected.exists():
        return expected

    # Be tolerant of download_dir implementations that add an extra directory.
    matches = list(
        run_file.parent.rglob(
            f"amplio-round-{round_number:02d}-session-{safe}-events.json"
        )
    )
    if len(matches) == 1:
        return matches[0]
    return None


def _event_signature(session_id: str, record: dict[str, Any]) -> str:
    stable = {
        "session_id": session_id,
        "step": record.get("step"),
        "generation": record.get("generation"),
        "created_at": record.get("created_at"),
        "event": record.get("event"),
    }
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _snapshot(path: Path, round_number: int) -> dict[str, Any]:
    run = _json(path)
    sessions = run.get("sessions") or []
    if not isinstance(sessions, list):
        raise ValueError(f"invalid sessions array in {path}")

    events: list[dict[str, Any]] = []
    missing: list[str] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        session_id = str(session.get("session_id") or "")
        if not session_id:
            continue
        event_path = _event_file(path, round_number, session_id)
        if event_path is None:
            missing.append(session_id)
            continue
        raw = _json(event_path)
        if not isinstance(raw, list):
            raise ValueError(f"invalid event array in {event_path}")
        for record in raw:
            if not isinstance(record, dict):
                continue
            item = dict(record)
            item["_session_id"] = session_id
            item["_signature"] = _event_signature(session_id, record)
            events.append(item)

    return {
        "run": run,
        "sessions": [s for s in sessions if isinstance(s, dict)],
        "events": events,
        "missing_event_sessions": missing,
    }


def _tool_call_map(records: Iterable[dict[str, Any]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for record in records:
        event = record.get("event") or {}
        if not isinstance(event, dict) or event.get("type") != "assistant":
            continue
        session_id = str(record.get("_session_id") or "")
        for call in event.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            call_id = str(call.get("id") or "")
            name = str(call.get("name") or "")
            if call_id:
                out[(session_id, call_id)] = name
    return out


def _new_counter() -> Counter[str]:
    return Counter(
        {
            "events": 0,
            "assistant_turns": 0,
            "root_assistant_turns": 0,
            "child_assistant_turns": 0,
            "tool_calls": 0,
            "root_tool_calls": 0,
            "child_tool_calls": 0,
            "tool_errors": 0,
            "root_tool_errors": 0,
            "child_tool_errors": 0,
            "invalid_tool_argument_errors": 0,
            "length_stop_turns": 0,
            "tool_payload_truncation_turns": 0,
            "parent_conclusion_cancellations": 0,
            "child_results_with_root_followup": 0,
            "concluded_child_results_with_root_followup": 0,
            "spawn_agent_calls": 0,
            "send_message_calls": 0,
            "await_event_calls": 0,
            "session_peek_calls": 0,
            "compactions": 0,
            "agent_messages": 0,
            "environment_messages": 0,
            "child_results": 0,
            "child_results_concluded": 0,
            "child_results_crashed": 0,
            "child_results_cancelled": 0,
            "recover_events": 0,
            "abnormal_stop_turns": 0,
            "truncated_turns": 0,
            "refusals": 0,
            "system_errors": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "root_total_tokens": 0,
            "child_total_tokens": 0,
        }
    )


def _summarize_events(
    records: Iterable[dict[str, Any]],
    parents: dict[str, str],
    call_names: dict[tuple[str, str], str],
) -> tuple[Counter[str], Counter[str], Counter[str]]:
    records = list(records)
    metrics = _new_counter()
    tool_calls: Counter[str] = Counter()
    tool_errors: Counter[str] = Counter()

    for record in records:
        metrics["events"] += 1
        session_id = str(record.get("_session_id") or "")
        is_child = bool(parents.get(session_id))
        event = record.get("event") or {}
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")

        if event_type == "assistant":
            metrics["assistant_turns"] += 1
            metrics["child_assistant_turns" if is_child else "root_assistant_turns"] += 1
            usage = event.get("usage") or {}
            if isinstance(usage, dict):
                for field in (
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "cache_read_tokens",
                    "cache_write_tokens",
                ):
                    value = usage.get(field)
                    if isinstance(value, int):
                        metrics[field] += value
                total = usage.get("total_tokens")
                if isinstance(total, int):
                    metrics["child_total_tokens" if is_child else "root_total_tokens"] += total

            if event.get("refusal"):
                metrics["refusals"] += 1
            if event.get("stop_reason") == "length":
                metrics["length_stop_turns"] += 1
                if event.get("tool_calls"):
                    metrics["tool_payload_truncation_turns"] += 1
            stop_notice = record.get("stop_notice")
            if isinstance(stop_notice, dict):
                metrics["abnormal_stop_turns"] += 1
                if stop_notice.get("truncated"):
                    metrics["truncated_turns"] += 1

            for call in event.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                name = str(call.get("name") or "unknown")
                metrics["tool_calls"] += 1
                metrics["child_tool_calls" if is_child else "root_tool_calls"] += 1
                tool_calls[name] += 1
                if name == "spawn_agent":
                    metrics["spawn_agent_calls"] += 1
                elif name == "send_message":
                    metrics["send_message_calls"] += 1
                elif name == "await_event":
                    metrics["await_event_calls"] += 1
                elif name == "session_peek":
                    metrics["session_peek_calls"] += 1

        elif event_type == "tool_result":
            if event.get("is_error"):
                metrics["tool_errors"] += 1
                metrics["child_tool_errors" if is_child else "root_tool_errors"] += 1
                content = str(event.get("content") or "")
                if "Invalid arguments:" in content:
                    metrics["invalid_tool_argument_errors"] += 1
                call_id = str(event.get("tool_call_id") or "")
                tool_name = call_names.get((session_id, call_id), "unknown")
                tool_errors[tool_name] += 1

        elif event_type == "compaction":
            metrics["compactions"] += 1

        elif event_type == "message":
            sender_type = str(event.get("sender_type") or "agent")
            if sender_type == "environment":
                metrics["environment_messages"] += 1
            else:
                metrics["agent_messages"] += 1

        elif event_type == "child_result":
            metrics["child_results"] += 1
            verdict = str(event.get("verdict") or "")
            key = f"child_results_{verdict}"
            if key in metrics:
                metrics[key] += 1

        elif event_type == "recover":
            metrics["recover_events"] += 1

        elif event_type == "system":
            marker = str(event.get("marker") or "")
            if marker == "error":
                metrics["system_errors"] += 1
            if marker == "cancelled":
                content = str(event.get("content") or "")
                if "parent " in content and " concluded" in content:
                    metrics["parent_conclusion_cancellations"] += 1

    # A child result is only operationally useful if the root gets another model
    # turn after it arrives. This is an opportunity-to-use signal, not proof that
    # the model actually incorporated the review semantically.
    by_session: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        sid = str(record.get("_session_id") or "")
        by_session.setdefault(sid, []).append(record)
    for session_id, session_records in by_session.items():
        if parents.get(session_id):
            continue
        ordered = sorted(
            session_records,
            key=lambda record: (
                str(record.get("created_at") or ""),
                int(record.get("step") or 0),
            ),
        )
        for index, record in enumerate(ordered):
            event = record.get("event") or {}
            if not isinstance(event, dict) or event.get("type") != "child_result":
                continue
            later_root_turn = any(
                isinstance((later.get("event") or {}), dict)
                and (later.get("event") or {}).get("type") == "assistant"
                for later in ordered[index + 1 :]
            )
            if later_root_turn:
                metrics["child_results_with_root_followup"] += 1
                if str(event.get("verdict") or "") == "concluded":
                    metrics["concluded_child_results_with_root_followup"] += 1

    return metrics, tool_calls, tool_errors


def _depths(sessions: list[dict[str, Any]]) -> dict[str, int]:
    parents = {
        str(s.get("session_id") or ""): str(s.get("parent_id") or "")
        for s in sessions
        if s.get("session_id")
    }
    cache: dict[str, int] = {}

    def depth(session_id: str) -> int:
        if session_id in cache:
            return cache[session_id]
        seen: set[str] = set()
        current = session_id
        d = 0
        while parents.get(current):
            if current in seen:
                raise ValueError("cycle in Amplio session parent graph")
            seen.add(current)
            current = parents[current]
            d += 1
        cache[session_id] = d
        return d

    for session_id in parents:
        depth(session_id)
    return cache


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_seconds(records: list[dict[str, Any]]) -> float | None:
    times = [
        parsed
        for parsed in (_parse_time(record.get("created_at")) for record in records)
        if parsed is not None
    ]
    if len(times) < 2:
        return None
    return max(0.0, (max(times) - min(times)).total_seconds())


def analyze_agent_events(run_dir: Path) -> dict[str, Any]:
    """Analyze deduplicated Amplio snapshots captured by the Harbor adapter.

    Each benchmark-round snapshot is cumulative. Events are therefore identified
    by a stable content signature and counted only on the first snapshot where
    they appear. This prevents the token/tool inflation caused by summing the raw
    cumulative snapshots independently.
    """

    snapshot_files = discover_snapshots(Path(run_dir))
    if not snapshot_files:
        raise ValueError("no Amplio raw round snapshots found")

    snapshots = {
        round_number: _snapshot(path, round_number)
        for round_number, path in sorted(snapshot_files.items())
    }

    latest_round = max(snapshots)
    latest = snapshots[latest_round]
    latest_sessions = latest["sessions"]
    latest_parents = {
        str(s.get("session_id") or ""): str(s.get("parent_id") or "")
        for s in latest_sessions
        if s.get("session_id")
    }
    depths = _depths(latest_sessions)

    seen_events: set[str] = set()
    seen_sessions: set[str] = set()
    round_rows: list[dict[str, Any]] = []

    for round_number, snapshot in sorted(snapshots.items()):
        sessions = snapshot["sessions"]
        parents = {
            str(s.get("session_id") or ""): str(s.get("parent_id") or "")
            for s in sessions
            if s.get("session_id")
        }
        records = snapshot["events"]
        call_names = _tool_call_map(records)

        new_records = [
            record
            for record in records
            if record["_signature"] not in seen_events
        ]
        for record in new_records:
            seen_events.add(record["_signature"])

        current_sessions = set(parents)
        new_sessions = current_sessions - seen_sessions
        seen_sessions |= current_sessions
        session_by_id = {
            str(session.get("session_id") or ""): session
            for session in sessions
            if session.get("session_id")
        }
        new_subagent_ids = [sid for sid in new_sessions if parents.get(sid)]
        new_subagent_status_counts = Counter(
            str(session_by_id.get(sid, {}).get("status") or "unknown")
            for sid in new_subagent_ids
        )

        metrics, tool_calls, tool_errors = _summarize_events(
            new_records, parents, call_names
        )
        row: dict[str, Any] = {
            "round": round_number,
            "new_sessions": len(new_sessions),
            "new_subagent_sessions": len(new_subagent_ids),
            "new_subagent_concluded": new_subagent_status_counts.get("concluded", 0),
            "new_subagent_cancelled": new_subagent_status_counts.get("cancelled", 0),
            "new_subagent_crashed": new_subagent_status_counts.get("crashed", 0),
            "new_subagent_status_counts": dict(sorted(new_subagent_status_counts.items())),
            "cumulative_sessions": len(current_sessions),
            "cumulative_subagent_sessions": sum(bool(parent) for parent in parents.values()),
            "duration_seconds": _duration_seconds(new_records),
            "missing_event_sessions": len(snapshot["missing_event_sessions"]),
            **dict(metrics),
            "tool_calls_by_name": dict(sorted(tool_calls.items())),
            "tool_errors_by_name": dict(sorted(tool_errors.items())),
        }
        round_rows.append(row)

    latest_records = latest["events"]
    latest_call_names = _tool_call_map(latest_records)
    total_metrics, tool_calls, tool_errors = _summarize_events(
        latest_records, latest_parents, latest_call_names
    )

    sessions_rows: list[dict[str, Any]] = []
    for session in latest_sessions:
        session_id = str(session.get("session_id") or "")
        records = [
            record
            for record in latest_records
            if record.get("_session_id") == session_id
        ]
        session_calls = _tool_call_map(records)
        metrics, calls, errors = _summarize_events(
            records, latest_parents, session_calls
        )
        sessions_rows.append(
            {
                "session_id": session_id,
                "parent_id": str(session.get("parent_id") or ""),
                "depth": depths.get(session_id, 0),
                "agent_type": str(session.get("agent_type") or ""),
                "status": str(session.get("status") or ""),
                "current_step": session.get("current_step"),
                "task": str(session.get("task") or ""),
                "created_at": str(session.get("created_at") or ""),
                "status_changed_at": str(session.get("status_changed_at") or ""),
                **dict(metrics),
                "tool_calls_by_name": dict(sorted(calls.items())),
                "tool_errors_by_name": dict(sorted(errors.items())),
            }
        )

    status_counts = Counter(
        str(s.get("status") or "unknown")
        for s in latest_sessions
        if s.get("parent_id")
    )
    total_tokens = total_metrics["total_tokens"]
    child_tokens = total_metrics["child_total_tokens"]
    subagent_sessions = sum(bool(s.get("parent_id")) for s in latest_sessions)
    concluded_subagents = status_counts.get("concluded", 0)
    cancelled_subagents = status_counts.get("cancelled", 0)

    return {
        "run_dir": str(Path(run_dir)),
        "snapshot_rounds": sorted(snapshots),
        "resolved_briefings": latest["run"].get("briefings") or [],
        "summary": {
            "total_sessions": len(latest_sessions),
            "root_sessions": sum(not bool(s.get("parent_id")) for s in latest_sessions),
            "subagent_sessions": subagent_sessions,
            "max_session_depth": max(depths.values(), default=0),
            "subagent_status_counts": dict(sorted(status_counts.items())),
            "subagent_completion_rate": (
                concluded_subagents / subagent_sessions if subagent_sessions else None
            ),
            "subagent_cancel_rate": (
                cancelled_subagents / subagent_sessions if subagent_sessions else None
            ),
            "total_tokens": total_tokens,
            "root_total_tokens": total_metrics["root_total_tokens"],
            "child_total_tokens": child_tokens,
            "child_token_share": child_tokens / total_tokens if total_tokens else None,
            "tool_calls": total_metrics["tool_calls"],
            "root_tool_calls": total_metrics["root_tool_calls"],
            "child_tool_calls": total_metrics["child_tool_calls"],
            "tool_errors": total_metrics["tool_errors"],
            "root_tool_errors": total_metrics["root_tool_errors"],
            "child_tool_errors": total_metrics["child_tool_errors"],
            "invalid_tool_argument_errors": total_metrics["invalid_tool_argument_errors"],
            "length_stop_turns": total_metrics["length_stop_turns"],
            "tool_payload_truncation_turns": total_metrics["tool_payload_truncation_turns"],
            "parent_conclusion_cancellations": total_metrics["parent_conclusion_cancellations"],
            "compactions": total_metrics["compactions"],
            "spawn_agent_calls": total_metrics["spawn_agent_calls"],
            "send_message_calls": total_metrics["send_message_calls"],
            "agent_messages": total_metrics["agent_messages"],
            "child_results": total_metrics["child_results"],
            "child_results_concluded": total_metrics["child_results_concluded"],
            "child_results_crashed": total_metrics["child_results_crashed"],
            "child_results_cancelled": total_metrics["child_results_cancelled"],
            "child_results_with_root_followup": total_metrics["child_results_with_root_followup"],
            "concluded_child_results_with_root_followup": total_metrics["concluded_child_results_with_root_followup"],
            "abnormal_stop_turns": total_metrics["abnormal_stop_turns"],
            "truncated_turns": total_metrics["truncated_turns"],
        },
        "totals": dict(total_metrics),
        "tool_calls_by_name": dict(sorted(tool_calls.items())),
        "tool_errors_by_name": dict(sorted(tool_errors.items())),
        "rounds": round_rows,
        "sessions": sessions_rows,
        "missing_event_sessions": latest["missing_event_sessions"],
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            encoded = {}
            for field in fields:
                value = row.get(field)
                if isinstance(value, dict):
                    value = json.dumps(value, sort_keys=True)
                encoded[field] = value
            writer.writerow(encoded)


def _fmt_share(value: Any) -> str:
    return "-" if value is None else f"{100 * float(value):.1f}%"


def write_agent_metrics(result: dict[str, Any], out_dir: Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "agent_metrics.json").write_text(json.dumps(result, indent=2) + "\n")

    round_fields = [
        "round",
        "new_sessions",
        "new_subagent_sessions",
        "new_subagent_concluded",
        "new_subagent_cancelled",
        "new_subagent_crashed",
        "new_subagent_status_counts",
        "cumulative_sessions",
        "cumulative_subagent_sessions",
        "assistant_turns",
        "root_assistant_turns",
        "child_assistant_turns",
        "tool_calls",
        "root_tool_calls",
        "child_tool_calls",
        "tool_errors",
        "root_tool_errors",
        "child_tool_errors",
        "invalid_tool_argument_errors",
        "length_stop_turns",
        "tool_payload_truncation_turns",
        "parent_conclusion_cancellations",
        "child_results_with_root_followup",
        "concluded_child_results_with_root_followup",
        "spawn_agent_calls",
        "send_message_calls",
        "await_event_calls",
        "session_peek_calls",
        "compactions",
        "agent_messages",
        "environment_messages",
        "child_results",
        "child_results_concluded",
        "child_results_crashed",
        "child_results_cancelled",
        "abnormal_stop_turns",
        "truncated_turns",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "root_total_tokens",
        "child_total_tokens",
        "duration_seconds",
        "missing_event_sessions",
        "tool_calls_by_name",
        "tool_errors_by_name",
    ]
    _write_csv(out / "round_agent_metrics.csv", result["rounds"], round_fields)

    session_fields = [
        "session_id",
        "parent_id",
        "depth",
        "agent_type",
        "status",
        "current_step",
        "task",
        "created_at",
        "status_changed_at",
        "assistant_turns",
        "tool_calls",
        "tool_errors",
        "invalid_tool_argument_errors",
        "length_stop_turns",
        "tool_payload_truncation_turns",
        "parent_conclusion_cancellations",
        "spawn_agent_calls",
        "send_message_calls",
        "await_event_calls",
        "session_peek_calls",
        "compactions",
        "agent_messages",
        "child_results",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "tool_calls_by_name",
        "tool_errors_by_name",
    ]
    _write_csv(out / "sessions.csv", result["sessions"], session_fields)

    summary = result["summary"]
    briefings = result.get("resolved_briefings") or []
    briefing_text = ", ".join(str(x) for x in briefings) if briefings else "none"
    lines = [
        "# Amplio agent telemetry",
        "",
        f"Resolved run briefings: **{briefing_text}**",
        "",
        "Cumulative per-round snapshots are deduplicated by event identity before "
        "token and tool counts are aggregated.",
        "",
        "## Run summary",
        "",
        f"- Sessions: {summary['total_sessions']} total, {summary['subagent_sessions']} subagents",
        f"- Maximum subagent depth: {summary['max_session_depth']}",
        f"- Tool calls: {summary['tool_calls']} ({summary['tool_errors']} errors); root={summary['root_tool_calls']}, child={summary['child_tool_calls']}",
        f"- Tool-transport failures: {summary['tool_payload_truncation_turns']} truncated tool-call turns, {summary['invalid_tool_argument_errors']} invalid-argument errors",
        f"- Compactions: {summary['compactions']}",
        f"- Subagent spawns: {summary['spawn_agent_calls']}",
        f"- Subagent terminal status: {summary['subagent_status_counts']}; completion={_fmt_share(summary['subagent_completion_rate'])}",
        f"- Children cancelled because parent concluded: {summary['parent_conclusion_cancellations']}",
        f"- Agent messages: {summary['agent_messages']}",
        f"- Child results: {summary['child_results']} ({summary['child_results_concluded']} concluded, {summary['child_results_cancelled']} cancelled, {summary['child_results_crashed']} crashed)",
        f"- Concluded child results followed by another root turn: {summary['concluded_child_results_with_root_followup']}",
        f"- Deduplicated total tokens: {summary['total_tokens']}",
        f"- Child-agent token share: {_fmt_share(summary['child_token_share'])}",
        "",
        "## Per benchmark round",
        "",
        "| Round | Tokens | Root tools | Child tools | Errors | Trunc | New child | Child done | Child cancel |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["rounds"]:
        lines.append(
            f"| {row['round']} | {row['total_tokens']} | {row['root_tool_calls']} | "
            f"{row['child_tool_calls']} | {row['tool_errors']} | "
            f"{row['tool_payload_truncation_turns']} | {row['new_subagent_sessions']} | "
            f"{row['new_subagent_concluded']} | {row['new_subagent_cancelled']} |"
        )

    if summary["subagent_sessions"] == 0:
        lines.extend(
            [
                "",
                "No subagent sessions were observed in the captured run. This is a "
                "useful baseline before testing a delegation-oriented harness change.",
            ]
        )

    (out / "summary.md").write_text("\n".join(lines) + "\n")
