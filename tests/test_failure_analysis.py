from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from amplio_bench.failure_analysis import analyze_failures, write_failure_analysis


class FailureAnalysisTest(unittest.TestCase):
    def _round(self, root: Path, n: int, cases: list[tuple]) -> None:
        verifier = root / f"steps/round-{n}/verifier"
        verifier.mkdir(parents=True)
        lines = []
        for item in cases:
            case_id, status, req, *rest = item
            scenario = rest[0] if rest else None
            line = (
                f"CASE_RESULT case_id={case_id} status={status} "
                f"requirement_ref={req} origin_step=round-{n}"
            )
            if scenario is not None:
                line += f' scenario="{scenario}"'
            lines.append(line)
        (verifier / "test-stdout.txt").write_text("\n".join(lines) + "\n")
        (verifier / "reward.txt").write_text("0\n")

    def test_exact_failure_decomposition_and_panel_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._round(
                root,
                1,
                [("c1", "success", "base"), ("c2", "fail", "base")],
            )
            self._round(
                root,
                2,
                [
                    ("c1", "fail", "base"),
                    ("c2", "fail", "base"),
                    ("c3", "fail", "new"),
                    ("c4", "success", "new"),
                ],
            )
            self._round(
                root,
                3,
                [
                    ("c1", "success", "base"),
                    ("c2", "fail", "base"),
                    ("c3", "success", "new"),
                    ("c4", "success", "new"),
                ],
            )

            panel = {
                "models": {
                    "m1": {
                        "1": {"total": 2, "fails": []},
                        "2": {
                            "total": 4,
                            "fails": [
                                {
                                    "req": "base",
                                    "type": "core",
                                    "cases": [{"id": "c1", "intent": "old behavior"}],
                                }
                            ],
                        },
                        "3": {
                            "total": 4,
                            "fails": [
                                {
                                    "req": "base",
                                    "type": "core",
                                    "cases": [{"id": "c2", "intent": "hard old behavior"}],
                                }
                            ],
                        },
                    },
                    "m2": {
                        "1": {"total": 2, "fails": []},
                        "2": {"total": 4, "fails": []},
                        "3": {
                            "total": 4,
                            "fails": [
                                {
                                    "req": "base",
                                    "type": "core",
                                    "cases": [{"id": "c2", "intent": "hard old behavior"}],
                                }
                            ],
                        },
                    },
                },
                "common_fail": [],
            }
            panel_path = root / "panel.json"
            panel_path.write_text(json.dumps(panel))

            result = analyze_failures(root, panel_path)
            self.assertEqual(result["summary"]["final_never_solved_failures"], 1)
            self.assertEqual(result["summary"]["final_lost_after_pass_failures"], 0)
            self.assertEqual(result["summary"]["final_panel_zero_target_failures"], 0)

            r2 = result["rounds"][1]
            self.assertEqual(r2["cases_fail"], 3)
            self.assertEqual(r2["inherited_failures"], 1)
            self.assertEqual(r2["regressions"], 1)
            self.assertEqual(r2["adaptation_misses"], 1)
            self.assertEqual(r2["recoveries"], 0)
            self.assertEqual(r2["panel_zero_target_failures"], 2)

            r3 = result["rounds"][2]
            self.assertEqual(r3["cases_fail"], 1)
            self.assertEqual(r3["inherited_failures"], 1)
            self.assertEqual(r3["recoveries"], 2)

            row = next(
                row
                for row in result["target_panel_cases"]
                if row["round"] == 3 and row["case_id"] == "c2"
            )
            self.assertEqual(row["panel_fail_models"], 2)
            self.assertEqual(row["panel_fail_rate"], 1.0)

            out = root / "out"
            write_failure_analysis(result, out)
            self.assertTrue((out / "summary.md").exists())
            self.assertTrue((out / "case_lifecycles.csv").exists())
            self.assertTrue((out / "target_panel_cases.csv").exists())

    def test_panel_case_count_mismatch_is_not_given_a_false_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._round(root, 1, [("c1", "fail", "base")])
            panel_path = root / "panel.json"
            panel_path.write_text(
                json.dumps(
                    {
                        "models": {
                            "m": {"1": {"total": 2, "fails": []}},
                        }
                    }
                )
            )
            result = analyze_failures(root, panel_path)
            row = result["target_panel_cases"][0]
            self.assertIsNone(row["panel_fail_rate"])
            self.assertFalse(result["panel"]["round_compatibility"][0]["case_count_matches"])

    def test_cross_round_decomposition_uses_semantic_case_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._round(
                root,
                1,
                [
                    ("c001", "success", "old", "A"),
                    ("c002", "fail", "old", "B"),
                    ("c003", "success", "old", "C"),
                ],
            )
            self._round(
                root,
                2,
                [
                    ("c001", "success", "old", "A"),
                    ("c002", "fail", "old", "C"),
                    ("c003", "fail", "new", "D"),
                ],
            )

            result = analyze_failures(root)
            r2 = result["rounds"][1]
            self.assertEqual(r2["inherited_failures"], 0)
            self.assertEqual(r2["regressions"], 1)
            self.assertEqual(r2["adaptation_misses"], 1)
            self.assertEqual(r2["recoveries"], 0)
            self.assertEqual(r2["introduced_cases"], 1)
            self.assertEqual(r2["retired_cases"], 1)
            self.assertAlmostEqual(r2["case_churn_rate"], 0.5)

            lifecycle = {row["scenario"]: row for row in result["case_lifecycles"]}
            self.assertEqual(lifecycle["C"]["regressions"], 1)
            self.assertEqual(lifecycle["C"]["first_case_id"], "c003")
            self.assertEqual(lifecycle["C"]["final_case_id"], "c002")
            self.assertEqual(lifecycle["B"]["final_status"], "retired")


if __name__ == "__main__":
    unittest.main()
