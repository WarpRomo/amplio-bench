import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amplio_bench.runner import build_harbor_command, load_config, run_evocode


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
