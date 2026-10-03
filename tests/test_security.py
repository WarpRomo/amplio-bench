import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amplio_bench.secrets import scan_tree


class SecurityTests(unittest.TestCase):
    def test_secret_scan_detects_environment_secret(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bad.txt").write_text("prefix test-secret-value suffix")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-secret-value"}):
                hits = scan_tree(root)
            self.assertIn("OPENAI_API_KEY", hits)

    def test_secret_scan_clean_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ok.txt").write_text("no credentials here")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-secret-value"}):
                hits = scan_tree(root)
            self.assertEqual(hits, {})


if __name__ == "__main__":
    unittest.main()
