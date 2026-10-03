import tempfile,unittest
from pathlib import Path
from amplio_bench.case_metrics import analyze_run,parse_case_line
class T(unittest.TestCase):
 def test_parse(self):
  c=parse_case_line('CASE_RESULT case_id=c1 requirement_ref=build status=success');self.assertTrue(c.passed);self.assertEqual(c.requirement,'build')
 def test_transition(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);a=root/'x/steps/round-1/verifier';b=root/'x/steps/round-2/verifier';a.mkdir(parents=True);b.mkdir(parents=True)
   (a/'reward.txt').write_text('0\n');(b/'reward.txt').write_text('0\n');(a/'test-stdout.txt').write_text('CASE_RESULT case_id=a status=success\nCASE_RESULT case_id=b status=fail\n');(b/'test-stdout.txt').write_text('CASE_RESULT case_id=a status=fail\nCASE_RESULT case_id=b status=success\nCASE_RESULT case_id=c status=success\n')
   r=analyze_run(root)['rounds'][1];self.assertEqual((r['regressions'],r['recoveries'],r['new_success']),(1,1,1))
