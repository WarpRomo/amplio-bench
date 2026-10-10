from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from amplio_bench.diagnostics import diagnose_run, write_diagnostics


class DiagnosticsTest(unittest.TestCase):
    def test_round_join_keeps_failure_and_harness_axes_separate(self) -> None:
        failures = {
            "summary": {
                "final_never_solved_failures": 1,
                "final_lost_after_pass_failures": 1,
                "final_panel_zero_target_failures": 1,
            },
            "rounds": [
                {
                    "round": 1,
                    "cases_success": 2,
                    "cases_fail": 3,
                    "inherited_failures": None,
                    "regressions": None,
                    "adaptation_misses": None,
                    "recoveries": None,
                    "introduced_cases": None,
                    "panel_zero_target_failures": 1,
                    "case_churn_rate": None,
                },
                {
                    "round": 2,
                    "cases_success": 3,
                    "cases_fail": 2,
                    "inherited_failures": 1,
                    "regressions": 1,
                    "adaptation_misses": 0,
                    "recoveries": 1,
                    "introduced_cases": 1,
                    "panel_zero_target_failures": 0,
                    "case_churn_rate": 0.2,
                },
            ],
        }
        agent = {
            "resolved_briefings": ["second-opinion"],
            "rounds": [
                {
                    "round": 1,
                    "total_tokens": 100,
                    "prompt_tokens": 80,
                    "assistant_turns": 2,
                    "tool_calls": 3,
                    "tool_errors": 0,
                    "compactions": 0,
                    "new_subagent_sessions": 0,
                    "spawn_agent_calls": 0,
                    "agent_messages": 0,
                    "child_results": 0,
                    "abnormal_stop_turns": 0,
                    "truncated_turns": 0,
                },
                {
                    "round": 2,
                    "total_tokens": 150,
                    "prompt_tokens": 120,
                    "assistant_turns": 3,
                    "tool_calls": 5,
                    "tool_errors": 1,
                    "compactions": 1,
                    "new_subagent_sessions": 1,
                    "spawn_agent_calls": 1,
                    "agent_messages": 1,
                    "child_results": 1,
                    "abnormal_stop_turns": 0,
                    "truncated_turns": 0,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as run_td:
            run_path = Path(run_td)
            (run_path / "run_command.json").write_text(
                '{"require_subagent_from_round": 2}'
            )
            with patch(
                "amplio_bench.diagnostics.analyze_failures", return_value=failures
            ), patch(
                "amplio_bench.diagnostics.analyze_agent_events", return_value=agent
            ):
                result = diagnose_run(run_path)

        self.assertEqual(result["resolved_briefings"], ["second-opinion"])
        self.assertEqual(result["delegation"]["required_rounds"], 1)
        self.assertEqual(result["delegation"]["rounds_with_new_subagent"], 1)
        self.assertEqual(result["delegation"]["adherence"], 1.0)
        self.assertEqual(result["rounds"][1]["regressions"], 1)
        self.assertEqual(result["rounds"][1]["tool_errors"], 1)
        self.assertEqual(result["rounds"][1]["new_subagent_sessions"], 1)

        # Writers are exercised with minimal complete nested structures via mocks.
        with tempfile.TemporaryDirectory() as td, patch(
            "amplio_bench.diagnostics.write_failure_analysis"
        ), patch("amplio_bench.diagnostics.write_agent_metrics"):
            out = Path(td)
            write_diagnostics(result, out)
            self.assertTrue((out / "round_diagnostics.csv").exists())
            self.assertTrue((out / "summary.md").exists())
            self.assertTrue((out / "diagnostics.json").exists())


if __name__ == "__main__":
    unittest.main()
