import tempfile
import unittest
from pathlib import Path

from amplio_bench.case_metrics import (
    analyze_run,
    parse_case_line,
)


class CaseMetricsTests(unittest.TestCase):
    def test_parse(self):
        case = parse_case_line(
            "CASE_RESULT case_id=c1 "
            "requirement_ref=build status=success"
        )
        self.assertIsNotNone(case)
        assert case is not None
        self.assertTrue(case.passed)
        self.assertEqual(case.requirement, "build")

        case = parse_case_line(
            'CASE_RESULT case_id=c9 requirement_ref=req status=fail '
            'scenario="stable semantic case"'
        )
        self.assertIsNotNone(case)
        assert case is not None
        self.assertEqual(case.scenario, "stable semantic case")
        self.assertEqual(case.stable_key, "scenario:stable semantic case")

    def test_transition(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "x/steps/round-1/verifier"
            second = root / "x/steps/round-2/verifier"
            first.mkdir(parents=True)
            second.mkdir(parents=True)

            (first / "reward.txt").write_text("0\n")
            (second / "reward.txt").write_text("0\n")
            (first / "test-stdout.txt").write_text(
                "CASE_RESULT case_id=a status=success\n"
                "CASE_RESULT case_id=b status=fail\n"
            )
            (second / "test-stdout.txt").write_text(
                "CASE_RESULT case_id=a status=fail\n"
                "CASE_RESULT case_id=b status=success\n"
                "CASE_RESULT case_id=c status=success\n"
            )

            row = analyze_run(root)["rounds"][1]
            self.assertEqual(
                (
                    row["regressions"],
                    row["recoveries"],
                    row["new_success"],
                ),
                (1, 1, 1),
            )
            self.assertEqual(
                (
                    row["retired_cases"],
                    row["retained_cases"],
                ),
                (0, 2),
            )
            self.assertAlmostEqual(
                row["case_churn_rate"],
                1 / 3,
            )

    def test_transition_uses_semantic_identity_when_ordinals_shift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "x/steps/round-1/verifier"
            second = root / "x/steps/round-2/verifier"
            first.mkdir(parents=True)
            second.mkdir(parents=True)

            (first / "reward.txt").write_text("0\n")
            (second / "reward.txt").write_text("0\n")
            (first / "test-stdout.txt").write_text(
                'CASE_RESULT case_id=c001 status=success scenario="A"\n'
                'CASE_RESULT case_id=c002 status=fail scenario="B"\n'
                'CASE_RESULT case_id=c003 status=success scenario="C"\n'
            )
            # B is retired, so retained C shifts from c003 -> c002. D is new.
            (second / "test-stdout.txt").write_text(
                'CASE_RESULT case_id=c001 status=success scenario="A"\n'
                'CASE_RESULT case_id=c002 status=fail scenario="C"\n'
                'CASE_RESULT case_id=c003 status=success scenario="D"\n'
            )

            row = analyze_run(root)["rounds"][1]
            self.assertEqual(row["regressions"], 1)
            self.assertEqual(row["recoveries"], 0)
            self.assertEqual(row["new_cases"], 1)
            self.assertEqual(row["new_success"], 1)
            self.assertEqual(row["retired_cases"], 1)
            self.assertEqual(row["retained_cases"], 2)
            self.assertAlmostEqual(row["case_churn_rate"], 2 / 4)


if __name__ == "__main__":
    unittest.main()
