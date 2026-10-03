import math
import unittest

from amplio_bench.metrics import RoundMetric, compute_task_metrics, recovery_tokens


class MetricsTest(unittest.TestCase):
    def test_task_metrics_and_regression(self):
        rounds = [
            RoundMetric(1, 1, 10, 10, 1000),
            RoundMetric(2, 0, 8, 10, 2000),
            RoundMetric(3, 1, 10, 10, 3000),
        ]
        m = compute_task_metrics(rounds)
        self.assertAlmostEqual(m.task_score, 2 / 3)
        self.assertAlmostEqual(m.case_score, 28 / 30)
        self.assertEqual(m.regression_count, 1)
        self.assertTrue(m.final_round_passed)
        self.assertFalse(m.perfect_task)
        self.assertIsNotNone(m.progress_auc_tokens)
        self.assertTrue(0 <= m.progress_auc_tokens <= 1)

    def test_recovery_tokens(self):
        rounds = [
            RoundMetric(1, 1, 10, 10, 100),
            RoundMetric(2, 0, 7, 10, 250),
            RoundMetric(3, 0, 9, 10, 400),
            RoundMetric(4, 1, 10, 10, 700),
        ]
        self.assertEqual(
            recovery_tokens(rounds),
            [
                {"failed_round": 2, "recovered_round": 4, "recovery_tokens": 450},
                {"failed_round": 3, "recovered_round": 4, "recovery_tokens": 300},
            ],
        )

    def test_auc_missing_tokens(self):
        m = compute_task_metrics([RoundMetric(1, 1, 1, 1, None)])
        self.assertIsNone(m.progress_auc_tokens)


if __name__ == "__main__":
    unittest.main()
