import tempfile,unittest
from pathlib import Path
from amplio_bench.audit import audit_run,check_harbor_verifier_isolation
class T(unittest.TestCase):
 def test_run(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td)
   for n in (1,2):d=r/f'x/steps/round-{n}/verifier';d.mkdir(parents=True);(d/'reward.txt').write_text('0\n')
   (r/'harbor_rc.txt').write_text('0\n');(r/'run.log').write_text('ok\n');(r/'audit').mkdir();(r/'audit/daytona-postflight.txt').write_text('COUNT_AFTER_CLEANUP = 0\n');self.assertEqual(audit_run(r,2)['validation_status'],'PASS')
 def test_isolation(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'src/harbor/trial/multi_step.py';p.parent.mkdir(parents=True);p.write_text('async def _prepare_step(self):\n    await self._reset_shared_step_verifier_dirs()\n\nasync def other(self):\n    pass\n');self.assertEqual(check_harbor_verifier_isolation(Path(td))['status'],'PASS')
