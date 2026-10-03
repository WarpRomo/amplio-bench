import tempfile
import unittest
from pathlib import Path

from amplio_bench.provenance import tree_hash


class ProvenanceTests(unittest.TestCase):
    def test_hash_is_stable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a").write_text("a")
            self.assertEqual(
                tree_hash(root),
                tree_hash(root),
            )


if __name__ == "__main__":
    unittest.main()
