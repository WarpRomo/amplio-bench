import tempfile
import unittest
from pathlib import Path

from amplio_bench.audit import (
    audit_run,
    check_harbor_verifier_isolation,
)


class AuditTests(unittest.TestCase):
    def test_run(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            for round_number in (1, 2):
                verifier = (
                    run
                    / f"x/steps/round-{round_number}/verifier"
                )
                verifier.mkdir(parents=True)
                (verifier / "reward.txt").write_text(
                    "0\n"
                )

            (run / "harbor_rc.txt").write_text("0\n")
            (run / "run.log").write_text("ok\n")
            (run / "audit").mkdir()
            (
                run
                / "audit/daytona-postflight.txt"
            ).write_text(
                "COUNT_AFTER_CLEANUP = 0\n"
            )

            self.assertEqual(
                audit_run(
                    run,
                    2,
                )["validation_status"],
                "PASS",
            )

    def test_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            source = (
                Path(td)
                / "src/harbor/trial/multi_step.py"
            )
            source.parent.mkdir(parents=True)
            source.write_text(
                "async def _prepare_step(self):\n"
                "    await "
                "self._reset_shared_step_verifier_dirs()\n"
                "\n"
                "async def other(self):\n"
                "    pass\n"
            )

            self.assertEqual(
                check_harbor_verifier_isolation(
                    Path(td)
                )["status"],
                "PASS",
            )


if __name__ == "__main__":
    unittest.main()
