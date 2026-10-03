import tempfile,unittest
from pathlib import Path
from amplio_bench.provenance import tree_hash
class T(unittest.TestCase):
 def test_hash(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'a').write_text('a');self.assertEqual(tree_hash(p),tree_hash(p))
