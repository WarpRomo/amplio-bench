import json
import tempfile
import unittest
from pathlib import Path

from amplio_bench.difficulty import (
    adaptation_difficulty,
    load_panel_directory,
    load_panel_task,
    panel_rounds,
    structural_rounds,
)


class DifficultyTests(unittest.TestCase):
    def _task(self, root: Path):
        task = root / "task"
        task.mkdir()
        (task / "task.toml").write_text("""
schema_version = "1.2"
[metadata]
name = "fixture"
difficulty = "hard"
[metadata.requirement_chain]
num_steps = 2
[[metadata.requirement_chain.steps]]
step = "round-1"
change_types = ["extension"]
[[metadata.requirement_chain.steps]]
step = "round-2"
change_types = ["correction", "conflict"]
[[steps]]
name = "round-1"
[[steps]]
name = "round-2"
""")
        for n in (1, 2):
            step = task / "steps" / f"round-{n}"
            (step / "solution").mkdir(parents=True)
            (step / "tests").mkdir()
            (step / "instruction.md").write_text(
                "add one feature\n"
                if n == 1
                else "correct the feature and preserve behavior\n"
            )
            (step / "solution" / "solve.sh").write_text(
                "echo one\n" if n == 1 else "echo two\necho three\n"
            )
        (task / "steps/round-1/tests/test.sh").write_text("a\nb\n")
        (task / "steps/round-2/tests/test.sh").write_text("a\nc\nd\n")
        return task

    def _run(self, root: Path):
        run = root / "run"
        for n, lines in {
            1: [
                "CASE_RESULT case_id=c1 status=success origin_step=round-1 requirement_ref=req-a case_type=core",
                "CASE_RESULT case_id=c2 status=fail origin_step=round-1 requirement_ref=req-b case_type=core",
            ],
            2: [
                "CASE_RESULT case_id=c2 status=success origin_step=round-1 requirement_ref=req-b case_type=core",
                "CASE_RESULT case_id=c3 status=fail origin_step=round-2 requirement_ref=req-c case_type=core",
            ],
        }.items():
            d = run / "steps" / f"round-{n}" / "verifier"
            d.mkdir(parents=True)
            (d / "test-stdout.txt").write_text("\n".join(lines) + "\n")
            (d / "reward.txt").write_text("0\n")
        return run

    def _panel(self, root: Path, name: str = "task"):
        path = root / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "task": name,
                    "meta": {
                        "name": name,
                        "difficulty": "hard",
                        "category": "fixture",
                    },
                    "n_rounds": 2,
                    "rounds": [
                        {"n": 1, "title": "one", "md": "x"},
                        {"n": 2, "title": "two", "md": "y"},
                    ],
                    "models": {
                        "strong": {
                            "1": {"pass": 9, "total": 10, "fail": 1, "reward": 0, "fails": []},
                            "2": {"pass": 6, "total": 10, "fail": 4, "reward": 0, "fails": []},
                        },
                        "mid": {
                            "1": {"pass": 8, "total": 10, "fail": 2, "reward": 0, "fails": []},
                            "2": {"pass": 4, "total": 10, "fail": 6, "reward": 0, "fails": []},
                        },
                        "weak": {
                            "1": {"pass": 6, "total": 10, "fail": 4, "reward": 0, "fails": []},
                            "2": {"pass": 2, "total": 10, "fail": 8, "reward": 0, "fails": []},
                        },
                    },
                }
            )
        )
        return path

    def test_real_released_schema_parser(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            models = load_panel_task(self._panel(root))
            self.assertEqual(set(models), {"strong", "mid", "weak"})
            self.assertEqual(models["strong"][1]["pass"], 9)

    def test_structural_churn(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = structural_rounds(self._task(root), self._run(root))
            self.assertEqual(rows[1].introduced_cases, 1)
            self.assertEqual(rows[1].retired_cases, 1)
            self.assertEqual(rows[1].retained_cases, 1)
            self.assertAlmostEqual(rows[1].case_churn_rate, 2 / 3)
            self.assertEqual(rows[1].introduced_requirements, 1)
            self.assertEqual(rows[1].retired_requirements, 1)
            self.assertEqual(rows[1].change_types, ("correction", "conflict"))

    def test_case_completion_calibration_resolves_binary_saturation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = panel_rounds(self._panel(root))
            # Every model has reward=0 on both rounds, so binary difficulty
            # cannot distinguish the rounds.
            self.assertAlmostEqual(
                rows[0].panel_binary_1pl_beta,
                rows[1].panel_binary_1pl_beta,
            )
            # Case completion clearly distinguishes the second round as harder.
            self.assertGreater(
                rows[1].panel_case_1pl_beta,
                rows[0].panel_case_1pl_beta,
            )
            self.assertGreater(
                rows[1].panel_case_1pl_percentile,
                rows[0].panel_case_1pl_percentile,
            )

    def test_panel_reach_and_uncertainty(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = self._panel(root)
            data = json.loads(path.read_text())
            del data["models"]["weak"]["2"]
            path.write_text(json.dumps(data))
            rows = panel_rounds(path)
            self.assertEqual(rows[1].panel_models_total, 3)
            self.assertEqual(rows[1].panel_models_reached, 2)
            self.assertAlmostEqual(rows[1].panel_reach_rate, 2 / 3)
            self.assertIsNotNone(rows[1].panel_round_pass_wilson_low_reached)
            self.assertIsNotNone(rows[1].panel_round_pass_wilson_high_reached)

    def test_global_percentile_uses_all_items(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            panel_dir = root / "panel"
            panel_dir.mkdir()
            self._panel(panel_dir, "task")
            second = self._panel(panel_dir, "other")
            data = json.loads(second.read_text())
            # Make the second task much easier in round 2.
            for rounds in data["models"].values():
                rounds["2"]["pass"] = 10
                rounds["2"]["fail"] = 0
                rounds["2"]["reward"] = 1
            second.write_text(json.dumps(data))

            loaded = load_panel_directory(panel_dir)
            self.assertEqual(set(loaded), {"task", "other"})
            rows = panel_rounds(panel_dir=panel_dir, task_key="task")
            self.assertEqual(rows[0].panel_calibration_items_total, 4)
            self.assertIsNotNone(rows[1].panel_case_1pl_percentile)

    def test_combined_output_keeps_axes_separate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = adaptation_difficulty(
                self._task(root),
                self._run(root),
                self._panel(root),
            )
            r2 = result["rounds"][1]
            self.assertEqual(r2["change_types"], "correction+conflict")
            self.assertIn("panel_case_mean_reached", r2)
            self.assertIn("panel_case_1pl_beta", r2)
            self.assertIn("case_churn_rate", r2)
            self.assertNotIn("target_panel_case_gap", r2)
            self.assertIn("preferred_history_control", result["methodology"])
            self.assertEqual(result["summary"]["adaptation_rounds"], 1)

    def test_structural_churn_uses_semantic_case_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task = self._task(root)
            run = root / "run-semantic"
            for n in (1, 2):
                verifier = run / f"steps/round-{n}/verifier"
                verifier.mkdir(parents=True)
                (verifier / "reward.txt").write_text("0\n")
            (run / "steps/round-1/verifier/test-stdout.txt").write_text(
                'CASE_RESULT case_id=c001 status=success scenario="A" requirement_ref=req-a\n'
                'CASE_RESULT case_id=c002 status=success scenario="B" requirement_ref=req-b\n'
                'CASE_RESULT case_id=c003 status=success scenario="C" requirement_ref=req-c\n'
            )
            (run / "steps/round-2/verifier/test-stdout.txt").write_text(
                'CASE_RESULT case_id=c001 status=success scenario="A" requirement_ref=req-a\n'
                'CASE_RESULT case_id=c002 status=success scenario="C" requirement_ref=req-c\n'
                'CASE_RESULT case_id=c003 status=success scenario="D" requirement_ref=req-d\n'
            )
            rows = structural_rounds(task, run)
            self.assertEqual(rows[1].introduced_cases, 1)
            self.assertEqual(rows[1].retired_cases, 1)
            self.assertEqual(rows[1].retained_cases, 2)
            self.assertAlmostEqual(rows[1].case_churn_rate, 0.5)


if __name__ == "__main__":
    unittest.main()
