from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from amplio_bench.agent_metrics import analyze_agent_events, write_agent_metrics


class AgentMetricsTest(unittest.TestCase):
    def _write_snapshot(
        self,
        root: Path,
        round_number: int,
        sessions: list[dict],
        events: dict[str, list[dict]],
        briefings: list[str] | None = None,
    ) -> None:
        prefix = f"amplio-round-{round_number:02d}"
        (root / f"{prefix}-run.json").write_text(
            json.dumps(
                {
                    "run_id": "run",
                    "briefings": briefings or [],
                    "sessions": sessions,
                }
            )
        )
        for session_id, records in events.items():
            safe = "".join(
                c if (c.isalnum() or c in "._-") else "_"
                for c in session_id
            )
            (root / f"{prefix}-session-{safe}-events.json").write_text(
                json.dumps(records)
            )

    @staticmethod
    def _assistant(step: int, at: str, calls=None, tokens=10) -> dict:
        return {
            "step": step,
            "generation": 0,
            "created_at": at,
            "event": {
                "type": "assistant",
                "tool_calls": calls or [],
                "usage": {
                    "prompt_tokens": tokens - 2,
                    "completion_tokens": 2,
                    "total_tokens": tokens,
                    "cache_read_tokens": 1,
                },
            },
        }

    def test_cumulative_snapshots_are_deduplicated_and_subagents_counted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            root_session = {
                "session_id": "main-agent",
                "parent_id": "",
                "agent_type": "standard_agent",
                "status": "ongoing",
                "current_step": 2,
                "task": "root",
                "created_at": "2026-10-01T00:00:00Z",
                "status_changed_at": "2026-10-01T00:00:00Z",
            }
            child = {
                "session_id": "child/1",
                "parent_id": "main-agent",
                "agent_type": "standard_agent",
                "status": "concluded",
                "current_step": 1,
                "task": "inspect tests",
                "created_at": "2026-10-01T00:01:00Z",
                "status_changed_at": "2026-10-01T00:02:00Z",
            }
            r1 = self._assistant(
                1,
                "2026-10-01T00:00:10Z",
                calls=[
                    {
                        "id": "tc1",
                        "name": "spawn_agent",
                        "arguments": '{"task":"inspect"}',
                    }
                ],
                tokens=100,
            )
            self._write_snapshot(
                root,
                1,
                [root_session],
                {"main-agent": [r1]},
                briefings=["second-opinion"],
            )

            r2 = self._assistant(
                2,
                "2026-10-01T00:02:10Z",
                calls=[{"id": "tc2", "name": "await_event", "arguments": "{}"}],
                tokens=120,
            )
            child_evt = self._assistant(
                1,
                "2026-10-01T00:01:20Z",
                calls=[{"id": "ct1", "name": "view_file", "arguments": "{}"}],
                tokens=50,
            )
            child_result = {
                "step": 2,
                "generation": 0,
                "created_at": "2026-10-01T00:02:05Z",
                "event": {
                    "type": "child_result",
                    "child_session_id": "child/1",
                    "verdict": "concluded",
                    "content": "done",
                },
            }
            self._write_snapshot(
                root,
                2,
                [root_session, child],
                {
                    "main-agent": [r1, child_result, r2],
                    "child/1": [child_evt],
                },
                briefings=["second-opinion"],
            )

            result = analyze_agent_events(root)
            self.assertEqual(result["resolved_briefings"], ["second-opinion"])
            self.assertEqual(result["summary"]["subagent_sessions"], 1)
            self.assertEqual(result["summary"]["max_session_depth"], 1)
            self.assertEqual(result["summary"]["total_tokens"], 270)
            self.assertEqual(result["summary"]["child_total_tokens"], 50)
            self.assertEqual(result["summary"]["spawn_agent_calls"], 1)
            self.assertEqual(result["summary"]["child_results"], 1)

            self.assertEqual(result["rounds"][0]["total_tokens"], 100)
            self.assertEqual(result["rounds"][1]["total_tokens"], 170)
            self.assertEqual(result["rounds"][1]["new_subagent_sessions"], 1)
            self.assertEqual(result["rounds"][1]["await_event_calls"], 1)

            out = root / "out"
            write_agent_metrics(result, out)
            self.assertTrue((out / "summary.md").exists())
            self.assertTrue((out / "round_agent_metrics.csv").exists())
            self.assertTrue((out / "sessions.csv").exists())

    def test_identical_nested_snapshot_copies_are_collapsed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            session = {
                "session_id": "main-agent",
                "parent_id": "",
                "status": "concluded",
                "created_at": "2026-10-01T00:00:00Z",
                "status_changed_at": "2026-10-01T00:00:02Z",
            }
            assistant = self._assistant(1, "2026-10-01T00:00:01Z")
            self._write_snapshot(root, 1, [session], {"main-agent": [assistant]})

            nested = root / "later-download" / "agent"
            nested.mkdir(parents=True)
            for source in root.glob("amplio-round-01-*.json"):
                (nested / source.name).write_bytes(source.read_bytes())

            result = analyze_agent_events(root)
            self.assertEqual(len(result["rounds"]), 1)
            self.assertEqual(result["summary"]["total_tokens"], 10)

    def test_conflicting_duplicate_snapshot_copies_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            session = {
                "session_id": "main-agent",
                "parent_id": "",
                "status": "concluded",
            }
            self._write_snapshot(root, 1, [session], {"main-agent": []})

            nested = root / "later-download"
            nested.mkdir()
            (nested / "amplio-round-01-run.json").write_text(
                json.dumps({"run_id": "different", "sessions": [session]})
            )

            with self.assertRaisesRegex(ValueError, "conflicting Amplio run snapshots"):
                analyze_agent_events(root)

    def test_tool_errors_are_attributed_to_call_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            session = {
                "session_id": "main-agent",
                "parent_id": "",
                "status": "concluded",
                "created_at": "2026-10-01T00:00:00Z",
                "status_changed_at": "2026-10-01T00:00:02Z",
            }
            assistant = self._assistant(
                1,
                "2026-10-01T00:00:01Z",
                calls=[{"id": "x", "name": "bash", "arguments": "{}"}],
            )
            result_event = {
                "step": 1,
                "generation": 0,
                "created_at": "2026-10-01T00:00:02Z",
                "event": {
                    "type": "tool_result",
                    "tool_call_id": "x",
                    "content": "failed",
                    "is_error": True,
                },
            }
            self._write_snapshot(root, 1, [session], {"main-agent": [assistant, result_event]})
            result = analyze_agent_events(root)
            self.assertEqual(result["summary"]["tool_errors"], 1)
            self.assertEqual(result["tool_errors_by_name"]["bash"], 1)

    def test_tool_transport_failures_and_parent_child_lifecycle_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            root_session = {
                "session_id": "main-agent",
                "parent_id": "",
                "status": "concluded",
                "created_at": "2026-10-01T00:00:00Z",
                "status_changed_at": "2026-10-01T00:00:05Z",
            }
            child = {
                "session_id": "reviewer",
                "parent_id": "main-agent",
                "status": "cancelled",
                "created_at": "2026-10-01T00:00:02Z",
                "status_changed_at": "2026-10-01T00:00:05Z",
            }
            truncated = self._assistant(
                1,
                "2026-10-01T00:00:01Z",
                calls=[{"id": "bad", "name": "bash", "arguments": "{broken"}],
                tokens=20,
            )
            truncated["event"]["stop_reason"] = "length"
            truncated["stop_notice"] = {"reason": "length", "truncated": True}
            invalid = {
                "step": 1,
                "generation": 0,
                "created_at": "2026-10-01T00:00:01.5Z",
                "event": {
                    "type": "tool_result",
                    "tool_call_id": "bad",
                    "content": "Invalid arguments: unexpected end of JSON input",
                    "is_error": True,
                },
            }
            spawn = self._assistant(
                2,
                "2026-10-01T00:00:02Z",
                calls=[{"id": "spawn", "name": "spawn_agent", "arguments": "{}"}],
                tokens=20,
            )
            cancelled_result = {
                "step": 3,
                "generation": 0,
                "created_at": "2026-10-01T00:00:05Z",
                "event": {
                    "type": "child_result",
                    "child_session_id": "reviewer",
                    "verdict": "cancelled",
                    "content": "parent main-agent concluded",
                },
            }
            child_cancel = {
                "step": 1,
                "generation": 0,
                "created_at": "2026-10-01T00:00:05Z",
                "event": {
                    "type": "system",
                    "marker": "cancelled",
                    "content": "parent main-agent concluded",
                },
            }
            self._write_snapshot(
                root,
                1,
                [root_session, child],
                {
                    "main-agent": [truncated, invalid, spawn, cancelled_result],
                    "reviewer": [child_cancel],
                },
            )
            result = analyze_agent_events(root)
            summary = result["summary"]
            self.assertEqual(summary["tool_payload_truncation_turns"], 1)
            self.assertEqual(summary["invalid_tool_argument_errors"], 1)
            self.assertEqual(summary["parent_conclusion_cancellations"], 1)
            self.assertEqual(summary["subagent_status_counts"], {"cancelled": 1})
            self.assertEqual(summary["subagent_completion_rate"], 0.0)
            self.assertEqual(result["rounds"][0]["new_subagent_cancelled"], 1)

    def test_concluded_child_result_followed_by_root_turn_is_counted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            root_session = {
                "session_id": "main-agent",
                "parent_id": "",
                "status": "concluded",
                "created_at": "2026-10-01T00:00:00Z",
                "status_changed_at": "2026-10-01T00:00:05Z",
            }
            child = {
                "session_id": "reviewer",
                "parent_id": "main-agent",
                "status": "concluded",
                "created_at": "2026-10-01T00:00:01Z",
                "status_changed_at": "2026-10-01T00:00:03Z",
            }
            child_result = {
                "step": 2,
                "generation": 0,
                "created_at": "2026-10-01T00:00:03Z",
                "event": {
                    "type": "child_result",
                    "child_session_id": "reviewer",
                    "verdict": "concluded",
                    "content": "review findings",
                },
            }
            followup = self._assistant(
                3,
                "2026-10-01T00:00:04Z",
                calls=[{"id": "fix", "name": "edit_file", "arguments": "{}"}],
                tokens=20,
            )
            child_turn = self._assistant(
                1,
                "2026-10-01T00:00:02Z",
                calls=[{"id": "inspect", "name": "view_file", "arguments": "{}"}],
                tokens=10,
            )
            self._write_snapshot(
                root,
                1,
                [root_session, child],
                {"main-agent": [child_result, followup], "reviewer": [child_turn]},
            )
            result = analyze_agent_events(root)
            summary = result["summary"]
            self.assertEqual(summary["child_results_concluded"], 1)
            self.assertEqual(summary["concluded_child_results_with_root_followup"], 1)
            self.assertEqual(summary["subagent_completion_rate"], 1.0)
            self.assertEqual(result["rounds"][0]["new_subagent_concluded"], 1)


if __name__ == "__main__":
    unittest.main()
