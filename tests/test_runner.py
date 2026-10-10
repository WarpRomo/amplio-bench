import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amplio_bench.runner import (
    build_harbor_command,
    build_process_env,
    load_config,
    run_evocode,
)


class RunnerTests(unittest.TestCase):
    def _config(self, harbor_bin="/bin/echo"):
        return {
            "run": {
                "harbor_bin": harbor_bin,
                "adapter": "adapters.harbor.amplio_agent:AmplioAgent",
                "environment": "daytona",
                "resume_trajectory": True,
                "n_attempts": 1,
                "n_concurrent": 1,
                "monitor_timeout_sec": 123,
                "briefings": [],
                "briefing_files": [],
            },
            "output": {"jobs_subdir": "harbor"},
        }

    def test_command_includes_persistent_trajectory(self):
        cmd = build_harbor_command(
            self._config(),
            Path("/task"),
            Path("/out"),
            "provider:model",
        )
        self.assertIn("--resume-trajectory", cmd)
        self.assertIn("adapters.harbor.amplio_agent:AmplioAgent", cmd)

    def test_harbor_env_override(self):
        with patch.dict(os.environ, {"AMPLIO_BENCH_HARBOR": "/bin/echo"}):
            cmd = build_harbor_command(
                self._config("/definitely/missing"),
                Path("/task"),
                Path("/out"),
                "provider:model",
            )
        self.assertEqual(cmd[0], "/bin/echo")

    def test_missing_harbor_is_actionable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AMPLIO_BENCH_HARBOR", None)
            with self.assertRaisesRegex(FileNotFoundError, "AMPLIO_BENCH_HARBOR"):
                build_harbor_command(
                    self._config("definitely-not-a-real-harbor-binary"),
                    Path("/task"),
                    Path("/out"),
                    "provider:model",
                )

    def test_load_example_config(self):
        root = Path(__file__).resolve().parents[1]
        cfg = load_config(root / "configs/evocode.example.toml")
        self.assertTrue(cfg["run"]["resume_trajectory"])
        self.assertEqual(cfg["run"]["n_attempts"], 1)
        self.assertEqual(cfg["run"]["briefings"], [])

    def test_process_env_serializes_briefings(self):
        config = self._config()
        config["run"]["briefings"] = ["second-opinion"]
        with patch.dict(os.environ, {}, clear=True):
            env = build_process_env(config)
        self.assertEqual(env["AMPLIO_MONITOR_TIMEOUT_SEC"], "123")
        self.assertEqual(
            env["AMPLIO_BENCH_BRIEFINGS_JSON"],
            '["second-opinion"]',
        )

    def test_process_env_rejects_invalid_briefings(self):
        config = self._config()
        config["run"]["briefings"] = "second-opinion"
        with self.assertRaisesRegex(ValueError, "briefings"):
            build_process_env(config)


    def test_process_env_serializes_intervention_controls(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            briefing = td / "review.md"
            briefing.write_text("---\nname: review\n---\nbody\n")
            config_path = td / "config.toml"
            config_path.write_text("[run]\n")
            config = self._config()
            config["run"]["briefings"] = ["review"]
            config["run"]["briefing_files"] = ["review.md"]
            config["run"]["require_subagent_from_round"] = 2
            config["run"]["subagent_enforcement_message"] = "review round {round}"
            config["run"]["force_subagent_enforcement"] = True
            config["run"]["require_completed_subagent"] = True
            config["run"]["recover_tool_transport_failures"] = True
            with patch.dict(os.environ, {}, clear=True):
                env = build_process_env(config, config_path)
            self.assertEqual(
                env["AMPLIO_BENCH_BRIEFING_FILES_JSON"],
                f'["{briefing.resolve()}"]',
            )
            self.assertEqual(
                env["AMPLIO_BENCH_REQUIRE_SUBAGENT_FROM_ROUND"], "2"
            )
            self.assertEqual(
                env["AMPLIO_BENCH_SUBAGENT_ENFORCEMENT_MESSAGE"],
                "review round {round}",
            )
            self.assertEqual(env["AMPLIO_BENCH_FORCE_SUBAGENT_ENFORCEMENT"], "1")
            self.assertEqual(env["AMPLIO_BENCH_REQUIRE_COMPLETED_SUBAGENT"], "1")
            self.assertEqual(env["AMPLIO_BENCH_RECOVER_TOOL_TRANSPORT_FAILURES"], "1")

    def test_process_env_rejects_nonboolean_intervention_controls(self):
        config = self._config()
        for key in (
            "force_subagent_enforcement",
            "require_completed_subagent",
            "recover_tool_transport_failures",
        ):
            bad = {**config, "run": dict(config["run"])}
            bad["run"][key] = "yes"
            with self.assertRaisesRegex(ValueError, key):
                build_process_env(bad)

    def test_process_env_rejects_missing_briefing_file(self):
        config = self._config()
        config["run"]["briefing_files"] = ["missing.md"]
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "config.toml"
            with self.assertRaisesRegex(FileNotFoundError, "briefing file"):
                build_process_env(config, config_path)

    def test_process_env_rejects_bad_subagent_round(self):
        config = self._config()
        config["run"]["require_subagent_from_round"] = 0
        with self.assertRaisesRegex(ValueError, "require_subagent_from_round"):
            build_process_env(config)

    def test_dry_run_records_command_without_execution(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            task = td / "task"
            out = td / "out"
            task.mkdir()
            config = td / "config.toml"
            config.write_text(
                """
[run]
harbor_bin = "/bin/echo"
adapter = "adapters.harbor.amplio_agent:AmplioAgent"
environment = "daytona"
resume_trajectory = true
n_attempts = 1
n_concurrent = 1
monitor_timeout_sec = 123

[output]
jobs_subdir = "harbor"
"""
            )
            rc = run_evocode(config, task, out, "provider:model", dry_run=True)
            self.assertEqual(rc, 0)
            self.assertTrue((out / "run_command.json").exists())


if __name__ == "__main__":
    unittest.main()
